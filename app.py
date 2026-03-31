import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
import time
from rapidfuzz import fuzz

# ================= CONFIG =================
st.set_page_config(page_title="LinkedIn Lead Finder", layout="wide")


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

    # -------- COMPANY VARIATIONS --------
    def generate_company_variations(self, company):
        base = company.lower()

        variations = [
            company,
            company.replace("realestate", "real estate"),
            company.replace("realestate", "realty"),
            company.replace("realestate", ""),
        ]

        return list(set([v.strip() for v in variations if v.strip()]))

    # -------- GOOGLE SEARCH --------
    def google_search(self, query):
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&num=10"

        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        results = []

        for g in soup.find_all("div", class_="tF2Cxc"):
            title = g.find("h3")
            link = g.find("a")
            snippet = g.find("span", class_="aCOpRe")

            results.append({
                "title": title.get_text() if title else "",
                "link": link["href"] if link else "",
                "snippet": snippet.get_text() if snippet else ""
            })

        return results

    # -------- DUCKDUCKGO --------
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

    # -------- SEARCH --------
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

        if match:
            name = match[0]

            # remove fake names
            blacklist = ["Real Estate", "Team", "Profile", "Services", "Homes"]
            if any(b.lower() in name.lower() for b in blacklist):
                return None

            return name

        return None

    # -------- ROLE --------
    def extract_role(self, text):
        text = text.lower()
        roles = ["ceo", "founder", "cto", "director", "vp", "head", "chief", "owner"]

        for r in roles:
            if r in text:
                return r.upper()

        return "Decision Maker"

    # -------- EMAIL --------
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

    # -------- MAIN --------
    def find_leads(self, company):
        leads = []

        variations = self.generate_company_variations(company)

        dorks = []
        for v in variations:
            dorks.extend([
                f'site:linkedin.com/in "{v}" ("CEO" OR "Founder" OR "Owner")',
                f'site:linkedin.com/in "{v}" ("Director" OR "VP" OR "Head")',
                f'site:linkedin.com/in "{v}"'
            ])

        for dork in dorks:
            results = self.search(dork)

            for r in results:
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                link = r.get("link", "")

                # STRICT LinkedIn only
                if "linkedin.com/in" not in link:
                    continue

                combined = f"{title} {snippet}".lower()

                name = self.extract_name(title)
                if not name:
                    continue

                role = self.extract_role(combined)

                leads.append({
                    "Name": name,
                    "Role": role,
                    "Type": "LinkedIn",
                    "Source": link
                })

            time.sleep(2)

        # -------- DEDUP --------
        unique = {}
        for lead in leads:
            if lead["Name"] not in unique:
                unique[lead["Name"]] = lead

        leads = list(unique.values())

        # -------- FALLBACK --------
        if not leads:
            leads.append({
                "Name": "Manual Search Required",
                "Role": "N/A",
                "Type": "Other",
                "Source": f"https://www.google.com/search?q={company}+linkedin"
            })

        return leads


# ================= UI =================
st.title(" LinkedIn Lead Finder)")

query = st.text_input("Company Name or Domain")

if st.button("Search"):

    if not query:
        st.error("Enter company name or domain")
        st.stop()

    engine = LeadFinder()
    company, domain = engine.parse_input(query)

    st.write(f"Searching for: {company}")

    with st.spinner("Finding actual humans (not fake entries)..."):
        leads = engine.find_leads(company)

    rows = []

    for lead in leads:
        emails = engine.generate_emails(lead["Name"], domain)

        rows.append({
            "Name": lead["Name"],
            "Role": lead["Role"],
            "Type": lead["Type"],
            "Emails": ", ".join(emails),
            "Source": lead["Source"]
        })

    df = pd.DataFrame(rows)

    st.success(f"Found {len(df)} real leads")
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode()
    st.download_button("Download CSV", csv, "leads.csv")
