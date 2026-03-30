import streamlit as st
import pandas as pd
import re
import time
import random
from duckduckgo_search import DDGS
from rapidfuzz import fuzz

# ====================== ENGINE ======================
class LeadFinder:
    def __init__(self):
        self.email_patterns = [
            "{first}.{last}@{domain}",
            "{first}{last}@{domain}",
            "{f}{last}@{domain}",
            "{first}@{domain}",
        ]

    # ---------------- PARSE INPUT ----------------
    def parse_input(self, query):
        query = query.strip()

        if not query:
            return "", ""

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

    # ---------------- NAME EXTRACTION ----------------
    def extract_name(self, text):
        text = re.sub(r'\|.*', '', text)
        text = re.sub(r'at .*', '', text, flags=re.I)

        words = text.split()
        words = [w for w in words if w.isalpha()]

        if len(words) >= 2:
            return f"{words[0].title()} {words[1].title()}"

        return None

    # ---------------- ROLE DETECTION ----------------
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

    # ---------------- SEARCH ----------------
    def find_leads(self, company):
        leads = []

        queries = [
            f"{company} CEO",
            f"{company} founder",
            f"{company} leadership team",
            f"{company} linkedin",
            f'site:linkedin.com "{company}"',
        ]

        with DDGS() as ddgs:
            for q in queries:
                try:
                    results = list(ddgs.text(q, max_results=15))

                    for r in results:
                        title = r.get("title", "")
                        snippet = r.get("body", "")
                        link = r.get("href", "")

                        combined = f"{title} {snippet}".lower()

                        # relaxed filtering
                        score = fuzz.partial_ratio(company.lower(), combined)

                        if score < 25:
                            continue

                        name = self.extract_name(title)
                        if not name:
                            continue

                        role = self.extract_role(combined)

                        leads.append({
                            "Name": name,
                            "Role": role,
                            "Source": link,
                            "Score": score
                        })

                    time.sleep(random.uniform(0.5, 1.2))

                except Exception:
                    continue

        # remove duplicates
        unique = {}
        for l in leads:
            if l["Name"] not in unique:
                unique[l["Name"]] = l

        return list(unique.values())

    # ---------------- EMAIL ----------------
    def generate_email(self, name, domain):
        if not domain:
            return ["No domain"]

        parts = name.lower().split()
        if len(parts) < 2:
            return ["Invalid name"]

        first, last = parts[0], parts[-1]
        f = first[0]

        return [
            p.format(first=first, last=last, f=f, domain=domain)
            for p in self.email_patterns
        ]

    # ---------------- MANUAL LINK PARSER ----------------
    def parse_linkedin(self, url):
        slug = url.split("/in/")[-1].strip("/")

        parts = re.split(r'[-_]', slug)
        parts = [p for p in parts if p.isalpha()]

        if len(parts) >= 2:
            return f"{parts[0].title()} {parts[1].title()}"

        return None


# ====================== UI ======================
st.set_page_config(page_title="OSINT Lead Finder", layout="wide")
st.title("🚀 OSINT Lead Finder (Fixed Version)")

query = st.text_input("Company or Domain")

engine = LeadFinder()

if st.button("Search"):
    company, domain = engine.parse_input(query)

    st.write(f"Searching for: {company}")

    with st.spinner("Searching..."):
        leads = engine.find_leads(company)

    if leads:
        results = []

        for l in leads:
            emails = engine.generate_email(l["Name"], domain)

            results.append({
                "Name": l["Name"],
                "Role": l["Role"],
                "Emails": ", ".join(emails),
                "Source": l["Source"]
            })

        df = pd.DataFrame(results)
        st.success(f"Found {len(df)} leads")
        st.dataframe(df)

    else:
        st.warning("No leads found. Try manual links below.")


# ====================== MANUAL ======================
st.divider()
st.subheader("Manual LinkedIn Input")

manual = st.text_area("Paste LinkedIn URLs")

if st.button("Process Links"):
    if manual.strip():
        rows = []

        for url in manual.split("\n"):
            name = engine.parse_linkedin(url.strip())

            if name:
                rows.append({
                    "Name": name,
                    "Source": url
                })

        if rows:
            df = pd.DataFrame(rows)
            st.success("Extracted names from links")
            st.dataframe(df)
        else:
            st.error("Could not extract names")
    else:
        st.warning("Paste links first")
