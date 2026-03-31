import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
import time
from rapidfuzz import fuzz

# ================= CONFIG =================
st.set_page_config(page_title="OSINT Lead Finder", layout="wide")


# ================= ENGINE =================
class LeadFinder:

    # -------- INPUT --------
    def parse_input(self, query):
        query = query.strip()

        if "." in query:
            domain = self.clean_domain(query)
            company = domain.split(".")[0].replace("-", " ").title()
        else:
            company = query
            domain = ""

        return company, domain

    def clean_domain(self, domain):
        return (domain.lower()
                .replace("https://", "")
                .replace("http://", "")
                .replace("www.", "")
                .strip("/"))

    # -------- GOOGLE SEARCH --------
    def google_search(self, query):
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&num=10"

        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        results = []

        for g in soup.find_all("div", class_="tF2Cxc"):
            title_tag = g.find("h3")
            link_tag = g.find("a")
            snippet_tag = g.find("span", class_="aCOpRe")

            results.append({
                "title": title_tag.get_text() if title_tag else "",
                "link": link_tag["href"] if link_tag else "",
                "snippet": snippet_tag.get_text() if snippet_tag else ""
            })

        return results

    # -------- DUCKDUCKGO FALLBACK --------
    def ddg_search(self, query):
        url = "https://html.duckduckgo.com/html/"
        headers = {"User-Agent": "Mozilla/5.0"}

        response = requests.post(url, headers=headers, data={"q": query})
        soup = BeautifulSoup(response.text, "html.parser")

        results = []

        for r in soup.find_all("div", class_="result"):
            a = r.find("a", class_="result__a")
            snippet = r.find("a", class_="result__snippet")

            results.append({
                "title": a.get_text() if a else "",
                "link": a["href"] if a else "",
                "snippet": snippet.get_text() if snippet else ""
            })

        return results

    # -------- SMART SEARCH --------
    def search(self, query):
        try:
            results = self.google_search(query)
            if results:
                return results
        except:
            pass

        return self.ddg_search(query)

    # -------- NAME EXTRACTION --------
    def extract_name(self, text):
        text = re.sub(r'\|.*', '', text)
        text = re.sub(r'-.*', '', text)

        match = re.findall(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)', text)

        return match[0] if match else None

    # -------- ROLE DETECTION --------
    def extract_role(self, text):
        text = text.lower()

        roles = ["ceo", "founder", "cto", "director", "vp", "head", "chief"]

        for r in roles:
            if r in text:
                return r.upper()

        return "Decision Maker"

    # -------- EMAIL GENERATION --------
    def generate_emails(self, name, domain):
        if not domain:
            return ["No domain"]

        parts = name.lower().split()
        if len(parts) < 2:
            return ["Invalid"]

        first = parts[0]
        last = parts[-1]
        f = first[0]

        return [
            f"{first}.{last}@{domain}",
            f"{first}{last}@{domain}",
            f"{f}{last}@{domain}",
            f"{first}@{domain}"
        ]

    # -------- MAIN LOGIC --------
    def find_leads(self, company):
        leads = []

        dorks = [
            f'site:linkedin.com/in "{company}" CEO',
            f'site:linkedin.com/in "{company}" founder',
            f'site:linkedin.com/in "{company}" CTO',
            f'site:linkedin.com/in "{company}" director',
            f'site:linkedin.com/in "{company}" "head of"',
            f'site:linkedin.com/in "{company}" VP',
            f'site:linkedin.com/in "{company}" "chief"',
            f'"CEO of {company}"',
            f'"Founder of {company}"',
            f'{company} leadership team',
            f'{company} executives',
            f'{company} management team',
        ]

        for dork in dorks:
            results = self.search(dork)

            for r in results:
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                link = r.get("link", "")

                combined = f"{title} {snippet}".lower()

                if fuzz.partial_ratio(company.lower(), combined) < 5:
                    continue

                name = self.extract_name(title)
                if not name:
                    continue

                role = self.extract_role(combined)

                leads.append({
                    "Name": name,
                    "Role": role,
                    "Source": link
                })

            time.sleep(2)

        # fallback (so you NEVER get empty screen again)
        if not leads:
            leads.append({
                "Name": "Try Manual Search",
                "Role": "N/A",
                "Source": f"https://www.google.com/search?q={company}+CEO"
            })

        # remove duplicates
        unique = {}
        for lead in leads:
            if lead["Name"] not in unique:
                unique[lead["Name"]] = lead

        return list(unique.values())


# ================= UI =================
st.title("🚀 OSINT Lead Finder (No API, Multi-Dork)")

query = st.text_input("Company Name or Domain")

if st.button("Search"):

    if not query:
        st.error("Enter company name or domain")
        st.stop()

    engine = LeadFinder()
    company, domain = engine.parse_input(query)

    st.write(f"Searching for: {company}")

    with st.spinner("Digging through the internet..."):
        leads = engine.find_leads(company)

    if leads:
        rows = []

        for lead in leads:
            emails = engine.generate_emails(lead["Name"], domain)

            rows.append({
                "Name": lead["Name"],
                "Role": lead["Role"],
                "Emails": ", ".join(emails),
                "Source": lead["Source"]
            })

        df = pd.DataFrame(rows)

        st.success(f"Found {len(df)} leads")
        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode()
        st.download_button("Download CSV", csv, "leads.csv")

    else:
        st.warning("Still nothing. Internet wins this round.")
