import streamlit as st
import pandas as pd
import re
import time
from serpapi import GoogleSearch
from rapidfuzz import fuzz

# ================= CONFIG =================
st.set_page_config(page_title="OSINT Lead Finder", layout="wide")


# ================= ENGINE =================
class LeadFinder:

    def __init__(self, api_key):
        self.api_key = api_key

    # -------- INPUT PARSING --------
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
        params = {
            "engine": "google",
            "q": query,
            "api_key": self.api_key,
            "num": 10
        }

        search = GoogleSearch(params)
        results = search.get_dict()

        return results.get("organic_results", [])

    # -------- NAME EXTRACTION --------
    def extract_name(self, text):
        text = re.sub(r'\|.*', '', text)
        text = re.sub(r'at .*', '', text, flags=re.I)

        words = [w for w in text.split() if w.isalpha()]

        if len(words) >= 2:
            return f"{words[0].title()} {words[1].title()}"

        return None

    # -------- ROLE DETECTION --------
    def extract_role(self, text):
        text = text.lower()

        if "ceo" in text:
            return "CEO"
        if "founder" in text:
            return "Founder"
        if "cto" in text:
            return "CTO"
        if "director" in text:
            return "Director"

        return "Decision Maker"

    # -------- MAIN LOGIC --------
    def find_leads(self, company):
        leads = []

        queries = [
            f"{company} CEO linkedin",
            f"{company} founder linkedin",
            f"{company} CTO linkedin",
            f"{company} director linkedin",
        ]

        for query in queries:
            results = self.google_search(query)

            for r in results:
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                link = r.get("link", "")

                combined = f"{title} {snippet}".lower()

                score = fuzz.partial_ratio(company.lower(), combined)

                # relaxed filtering
                if score < 20:
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

            time.sleep(0.5)

        # remove duplicates
        unique = {}
        for lead in leads:
            if lead["Name"] not in unique:
                unique[lead["Name"]] = lead

        return list(unique.values())

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

        patterns = [
            f"{first}.{last}@{domain}",
            f"{first}{last}@{domain}",
            f"{f}{last}@{domain}",
            f"{first}@{domain}"
        ]

        return patterns


# ================= UI =================
st.title("🚀 OSINT Lead Finder (Google Powered)")

api_key = st.text_input("SerpAPI Key", type="password")
query = st.text_input("Company Name or Domain")

if st.button("Search"):

    if not api_key:
        st.error("Enter your SerpAPI key")
        st.stop()

    if not query:
        st.error("Enter company name or domain")
        st.stop()

    engine = LeadFinder(api_key)

    company, domain = engine.parse_input(query)

    st.write(f"Searching for: {company}")

    with st.spinner("Fetching data from Google..."):
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
        st.warning("No leads found. Try a different company or use LinkedIn manually.")
