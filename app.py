import streamlit as st
import pandas as pd
import time
import re
from duckduckgo_search import DDGS
from rapidfuzz import fuzz

# ================= CORE ENGINE =================
class OSINTLeadEngine:
    def __init__(self):

        self.roles = [
            "CEO", "Founder", "Owner",
            "Managing Director", "Director",
            "Head", "VP", "Chief"
        ]

        self.patterns = [
            "{first}.{last}@{domain}",
            "{first}{last}@{domain}",
            "{f}{last}@{domain}",
            "{first}@{domain}",
            "{first}_{last}@{domain}",
        ]

    # -------- INPUT PARSER --------
    def parse_input(self, user_input):
        user_input = user_input.strip().lower()

        if "." in user_input and " " not in user_input:
            domain = self.clean_domain(user_input)
            company = domain.split(".")[0]
        else:
            company = user_input
            domain = ""

        base = company.split()[0]

        variations = list(set([
            company,
            base,
            company.replace(" technologies", ""),
            company.replace(" tech", ""),
            company.replace(" solutions", ""),
            company.replace(" pvt ltd", ""),
            company.replace(" private limited", ""),
        ]))

        return company, domain, variations

    def clean_domain(self, domain):
        return (
            domain.replace("https://", "")
            .replace("http://", "")
            .replace("www.", "")
            .strip("/")
        )

    # -------- QUERY BUILDER --------
    def build_queries(self, variations, domain):
        queries = []

        for name in variations:
            queries.extend([
                f'site:linkedin.com/in "{name}" ("CEO" OR "Founder" OR "Director")',
                f'site:linkedin.com/in "{name}"',
                f'"{name}" CEO',
                f'"{name}" founder',
                f'"{name}" director',
                f'"{name}" "our team"',
                f'"{name}" company',
            ])

        if domain:
            queries.extend([
                f'"@{domain}"',
                f'site:{domain} ("team" OR "about")',
            ])

        return list(set(queries))

    # -------- ROLE EXTRACTION --------
    def extract_role(self, text):
        match = re.findall(
            r"(CEO|Founder|Director|Head|VP|Chief|Owner)",
            text,
            re.I
        )
        return match[0] if match else "N/A"

    # -------- LEAD FINDER --------
    def find_leads(self, company, domain, variations):
        leads = []
        queries = self.build_queries(variations, domain)

        with DDGS() as ddgs:
            for query in queries:
                try:
                    results = ddgs.text(query, max_results=10)

                    for r in results:
                        link = r.get("href")
                        title = r.get("title", "")
                        snippet = r.get("body", "")

                        if not link or "linkedin.com/in" not in link:
                            continue

                        combined = f"{title} {snippet}".lower()

                        if fuzz.partial_ratio(company, combined) > 40:

                            name = re.split(r"[-|,]", title)[0].strip()

                            if 2 <= len(name.split()) <= 4:
                                role = self.extract_role(combined)

                                leads.append({
                                    "Full Name": name,
                                    "Role": role,
                                    "Source": link
                                })

                    time.sleep(0.3)

                except:
                    continue

        # ===== FALLBACK (CRITICAL FIX) =====
        if not leads:
            st.warning("No decision-makers found → switching to employee discovery")

            fallback_queries = [
                f'site:linkedin.com/in "{company}"',
                f'"{company}" linkedin',
            ]

            with DDGS() as ddgs:
                for query in fallback_queries:
                    try:
                        results = ddgs.text(query, max_results=15)

                        for r in results:
                            link = r.get("href")
                            title = r.get("title", "")

                            if not link or "linkedin.com/in" not in link:
                                continue

                            name = re.split(r"[-|,]", title)[0].strip()

                            if 2 <= len(name.split()) <= 4:
                                leads.append({
                                    "Full Name": name,
                                    "Role": "Employee",
                                    "Source": link
                                })

                    except:
                        continue

        # Deduplicate
        unique = {l["Full Name"]: l for l in leads}

        return list(unique.values())

    # -------- EMAIL GENERATOR --------
    def generate_email(self, full_name, domain):
        if not domain:
            return ["No domain"]

        parts = full_name.lower().split()

        if len(parts) < 2:
            return ["Invalid name"]

        first = parts[0]
        last = parts[-1]

        return [
            p.format(first=first, last=last, f=first[0], domain=domain)
            for p in self.patterns
        ]


# ================= STREAMLIT UI =================
st.set_page_config(layout="wide")
st.title("🚀 OSINT Decision-Maker Finder")

query = st.text_input("Company Name or Domain")

if st.button("Run Scan"):

    if not query:
        st.error("Enter something useful.")
    else:
        engine = OSINTLeadEngine()

        company, domain, variations = engine.parse_input(query)

        with st.spinner("Scanning internet like a responsible stalker..."):
            leads = engine.find_leads(company, domain, variations)

        if not leads:
            st.error("Still nothing found. Either ultra-small company or invisible online.")
        else:
            results = []

            for lead in leads:
                emails = engine.generate_email(lead["Full Name"], domain)

                results.append({
                    "Name": lead["Full Name"],
                    "Role": lead["Role"],
                    "Source": lead["Source"],
                    "Email Guess": ", ".join(emails[:2])
                })

            df = pd.DataFrame(results)

            st.success(f"Found {len(df)} leads")
            st.dataframe(df, use_container_width=True, hide_index=True)

st.info("⚠️ Emails are guesses. Verify before using.")
