import streamlit as st
import pandas as pd
import time
import re
from duckduckgo_search import DDGS
from rapidfuzz import fuzz

# ================= CORE ENGINE =================
class OSINTLeadEngine:

    def __init__(self):
        self.roles = ["CEO", "Founder", "Director", "Owner", "Head", "VP", "Chief"]

        self.patterns = [
            "{first}.{last}@{domain}",
            "{first}{last}@{domain}",
            "{f}{last}@{domain}",
            "{first}@{domain}",
        ]

    # -------- INPUT PARSER --------
    def parse_input(self, user_input):
        user_input = user_input.strip().lower()

        # 🔥 LinkedIn company detection
        if "linkedin.com/company/" in user_input:
            slug = user_input.split("company/")[1].split("/")[0]
            company = slug.replace("-", " ")
            return company, "", [company], slug

        # Domain detection
        if "." in user_input and " " not in user_input:
            domain = user_input.replace("https://", "").replace("http://", "").replace("www.", "")
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
        ]))

        return company, domain, variations, None

    # -------- QUERY BUILDER --------
    def build_queries(self, variations, domain, slug):

        queries = []

        # 🔥 LinkedIn COMPANY MODE (best results)
        if slug:
            base = slug.replace("-", " ")

            queries.extend([
                f'site:linkedin.com/in "{slug}"',
                f'site:linkedin.com/in "{base}"',
                f'site:linkedin.com/in "{base}" CEO',
                f'site:linkedin.com/in "{base}" founder',
            ])
            return queries

        # 🔥 Normal mode
        for name in variations:
            queries.extend([
                f'site:linkedin.com/in "{name}" ("CEO" OR "Founder" OR "Director")',
                f'site:linkedin.com/in "{name}"',
                f'"{name}" CEO',
                f'"{name}" founder',
                f'"{name}" "our team"',
            ])

        if domain:
            queries.append(f'"@{domain}"')

        return list(set(queries))

    # -------- ROLE EXTRACTION --------
    def extract_role(self, text):
        match = re.findall(r"(CEO|Founder|Director|Head|VP|Chief|Owner)", text, re.I)
        return match[0] if match else "Employee"

    # -------- LEAD FINDER --------
    def find_leads(self, company, domain, variations, slug):

        leads = []
        queries = self.build_queries(variations, domain, slug)

        with DDGS() as ddgs:
            for query in queries:
                try:
                    results = ddgs.text(query, max_results=12)

                    for r in results:
                        link = r.get("href")
                        title = r.get("title", "")
                        snippet = r.get("body", "")

                        if not link or "linkedin.com/in" not in link:
                            continue

                        combined = f"{title} {snippet}".lower()

                        # 🔥 smarter match threshold
                        if fuzz.partial_ratio(company, combined) > 35:

                            name = re.split(r"[-|,]", title)[0].strip()

                            if 2 <= len(name.split()) <= 4:
                                leads.append({
                                    "Full Name": name,
                                    "Role": self.extract_role(combined),
                                    "Source": link
                                })

                    time.sleep(0.3)

                except:
                    continue

        # 🔥 FALLBACK (never empty again)
        if not leads:
            st.warning("No decision-makers found → switching to employee discovery")

            fallback_queries = [
                f'site:linkedin.com/in "{company}"',
                f'"{company}" linkedin'
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

        # Remove duplicates
        unique = {l["Full Name"]: l for l in leads}

        return list(unique.values())

    # -------- EMAIL GENERATOR --------
    def generate_email(self, name, domain):
        if not domain:
            return ["No domain"]

        parts = name.lower().split()
        if len(parts) < 2:
            return ["Invalid"]

        first, last = parts[0], parts[-1]

        return [
            p.format(first=first, last=last, f=first[0], domain=domain)
            for p in self.patterns
        ]


# ================= UI =================
st.set_page_config(layout="wide")
st.title("🚀 OSINT Decision-Maker Finder")

query = st.text_input("Company Name / Domain / LinkedIn URL")

if st.button("Run Scan"):

    if not query:
        st.error("Enter something.")
    else:
        engine = OSINTLeadEngine()
        company, domain, variations, slug = engine.parse_input(query)

        with st.spinner("Running OSINT scan..."):
            leads = engine.find_leads(company, domain, variations, slug)

        if not leads:
            st.error("Still nothing found. Company likely has no public footprint.")
        else:
            data = []

            for l in leads:
                emails = engine.generate_email(l["Full Name"], domain)

                data.append({
                    "Name": l["Full Name"],
                    "Role": l["Role"],
                    "Source": l["Source"],
                    "Email Guess": ", ".join(emails[:2])
                })

            df = pd.DataFrame(data)

            st.success(f"Found {len(df)} people")
            st.dataframe(df, use_container_width=True, hide_index=True)

st.info("⚠️ Email guesses are not verified. Use validation tools.")
