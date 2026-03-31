import streamlit as st
import pandas as pd
import re
import time
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz

# ================= CONFIG =================
st.set_page_config(page_title="OSINT Lead Finder", layout="wide")

# ================= ENGINE =================
class LeadFinder:

    def __init__(self):
        pass

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

    # -------- SEARCH (NO API) --------
    def search_duckduckgo(self, query):
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        data = {"q": query}

        response = requests.post(url, headers=headers, data=data, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        results = []

        for result in soup.find_all("div", class_="result"):
            title_tag = result.find("a", class_="result__a")
            snippet_tag = result.find("a", class_="result__snippet")

            title = title_tag.get_text() if title_tag else ""
            link = title_tag["href"] if title_tag else ""
            snippet = snippet_tag.get_text() if snippet_tag else ""

            results.append({
                "title": title,
                "link": link,
                "snippet": snippet
            })

        return results

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
            results = self.search_duckduckgo(query)

            for r in results:
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                link = r.get("link", "")

                combined = f"{title} {snippet}".lower()

                # relaxed filtering
                score = fuzz.partial_ratio(company.lower(), combined)
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

            time.sleep(1)  # avoid getting blocked

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
st.title("🚀 OSINT Lead Finder (No API, No Tears)")

query = st.text_input("Company Name or Domain")

if st.button("Search"):

    if not query:
        st.error("Enter company name or domain")
        st.stop()

    engine = LeadFinder()

    company, domain = engine.parse_input(query)

    st.write(f"Searching for: {company}")

    with st.spinner("Scraping the internet like a responsible adult..."):
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
        st.warning("No leads found. Try a different company.")
