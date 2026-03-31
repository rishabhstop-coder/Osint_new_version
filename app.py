import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
import time
from rapidfuzz import fuzz

# ================= CONFIG =================
st.set_page_config(page_title="Precision Lead Finder", layout="wide")


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
        variations = [
            company,
            company.replace("realestate", "real estate"),
            company.replace("realestate", "realty"),
            company.replace("realestate", ""),
        ]
        return list(set([v.strip() for v in variations if v.strip()]))

    # -------- SEARCH (Google + fallback) --------
    def search(self, query):
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&num=10"

        try:
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

            if results:
                return results
        except:
            pass

        # fallback DDG
        url = "https://html.duckduckgo.com/html/"
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

    # -------- NAME --------
    def extract_name(self, text):
        text = re.sub(r'\|.*', '', text)
        text = re.sub(r'-.*', '', text)

        match = re.findall(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)', text)

        if match:
            name = match[0]

            blacklist = ["Real Estate", "Team", "Profile", "Services", "Homes", "About"]
            if any(b.lower() in name.lower() for b in blacklist):
                return None

            if len(name.split()) < 2:
                return None

            return name

        return None

    # -------- ROLE --------
    def extract_role(self, text):
        text = text.lower()

        valid_roles = ["ceo", "founder", "owner", "director", "principal", "broker"]

        for r in valid_roles:
            if r in text:
                return r.upper()

        return None

    # -------- MAIN --------
    def find_leads(self, company):
        leads = []

        variations = self.generate_company_variations(company)

        dorks = []
        for v in variations:
            dorks.extend([
                f'site:linkedin.com/in "{v}" ("CEO" OR "Founder" OR "Owner")',
                f'site:linkedin.com/in "{v}" ("Director" OR "Broker")',
                f'{v} CEO',
                f'{v} founder',
                f'{v} broker',
                f'{v} leadership'
            ])

        blacklist_words = [
            "wikipedia", "news", "timeline", "history",
            "article", "press", "school", "encyclopedia"
        ]

        for dork in dorks:
            results = self.search(dork)

            for r in results:
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                link = r.get("link", "")

                combined = f"{title} {snippet}".lower()

                # ❌ remove junk pages
                if any(b in combined for b in blacklist_words):
                    continue

                # ✅ must match company variation
                if not any(v.lower() in combined for v in variations):
                    continue

                name = self.extract_name(title)
                if not name:
                    continue

                role = self.extract_role(combined)
                if not role:
                    continue

                source_type = "LinkedIn" if "linkedin.com/in" in link else "Other"

                leads.append({
                    "Name": name,
                    "Role": role,
                    "Type": source_type,
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
st.title("🎯 Precision Lead Finder (No Garbage Edition)")

query = st.text_input("Company Name or Domain")

if st.button("Search"):

    if not query:
        st.error("Enter company name")
        st.stop()

    engine = LeadFinder()
    company, domain = engine.parse_input(query)

    st.write(f"Searching for: {company}")

    with st.spinner("Filtering out nonsense..."):
        leads = engine.find_leads(company)

    rows = []
    for lead in leads:
        rows.append({
            "Name": lead["Name"],
            "Role": lead["Role"],
            "Type": lead["Type"],
            "Source": lead["Source"]
        })

    df = pd.DataFrame(rows)

    st.success(f"Found {len(df)} relevant leads")
    st.dataframe(df, use_container_width=True)
