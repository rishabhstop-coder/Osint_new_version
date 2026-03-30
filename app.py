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
            "CEO", "Chief Executive Officer",
            "Founder", "Co-Founder", "Owner",
            "Managing Director", "Director",
            "Head", "Head of Marketing", "Head of Growth",
            "CMO", "CTO", "CIO",
            "VP", "Vice President",
            "Marketing Manager", "Growth Manager",
            "Product Manager", "Business Development"
        ]

        self.patterns = [
            "{first}.{last}@{domain}",
            "{first}{last}@{domain}",
            "{f}{last}@{domain}",
            "{first}@{domain}",
            "{first}_{last}@{domain}",
            "{last}.{first}@{domain}",
            "{first}{l}@{domain}",
            "{f}.{last}@{domain}"
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

        variations = list(set([
            company,
            company.replace(" technologies", ""),
            company.replace(" tech", ""),
            company.replace(" solutions", ""),
            company.replace(" pvt ltd", ""),
            company.replace(" private limited", "")
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
    def build_queries(self, company, domain, variations):
        role_query = " OR ".join([f'"{r}"' for r in self.roles])
        queries = []

        for name in variations:
            queries.extend([
                f'site:linkedin.com/in "{name}" ({role_query})',
                f'site:linkedin.com/in "{name}"',
                f'"{name}" ("CEO" OR "Founder" OR "Director")',
                f'"{name}" "our team"',
                f'"{name}" "leadership"',
                f'"{name}" "CEO said"',
            ])

        if domain:
            queries.extend([
                f'site:{domain} ("team" OR "about")',
                f'"@{domain}" ("CEO" OR "Founder")',
                f'site:{domain} filetype:pdf ("CEO" OR "Director")'
            ])

        return queries

    # -------- ROLE EXTRACTION --------
    def extract_role(self, text):
        match = re.findall(
            r"(CEO|Founder|Director|Head|Manager|VP|Chief|Owner)",
            text,
            re.I
        )
        return match[0] if match else "N/A"

    # -------- LEAD FINDER --------
    def find_leads(self, company, domain, variations):
        leads = []
        queries = self.build_queries(company, domain, variations)

        try:
            with DDGS() as ddgs:
                for query in queries:
                    results = ddgs.text(query, max_results=10)

                    for r in results:
                        title = r.get("title", "")
                        snippet = r.get("body", "")
                        link = r.get("href")

                        if not link or "linkedin.com/in" not in link:
                            continue

                        combined = f"{title} {snippet}".lower()

                        if fuzz.partial_ratio(company, combined) > 50:

                            name = re.split(r"[-|,]", title)[0].strip()

                            if 2 <= len(name.split()) <= 4:
                                role = self.extract_role(combined)

                                leads.append({
                                    "Full Name": name,
                                    "Role": role,
                                    "Source": link,
                                    "Snippet": snippet
                                })

                    time.sleep(0.5)

        except Exception as e:
            st.error(f"Search Error: {e}")

        # Deduplicate
        unique = {l["Full Name"]: l for l in leads}

        priority = {
            "CEO": 1, "Founder": 1, "Owner": 1, "Chief": 1,
            "Director": 2, "VP": 3, "Head": 3, "Manager": 4
        }

        sorted_leads = sorted(
            unique.values(),
            key=lambda x: priority.get(x["Role"], 5)
        )

        return sorted_leads

    # -------- EMAIL GENERATOR --------
    def generate_email(self, full_name, domain):
        parts = full_name.lower().split()

        if len(parts) < 2 or not domain:
            return ["Not enough data"]

        first = parts[0]
        last = parts[-1]

        return [
            p.format(
                first=first,
                last=last,
                f=first[0],
                l=last[0],
                domain=domain
            )
            for p in self.patterns
        ]


# ================= STREAMLIT UI =================
st.set_page_config(page_title="OSINT Lead Engine PRO", layout="wide")

st.title("🚀 OSINT Decision-Maker Finder")
st.markdown("Find CEOs, founders, and key decision-makers using advanced dorking.")

query_input = st.text_input(
    "Company Name or Domain",
    placeholder="e.g. tesla OR tesla.com"
)

if st.button("Run Scan", type="primary"):

    if not query_input:
        st.error("Enter a company or domain.")
    else:
        engine = OSINTLeadEngine()

        company, domain, variations = engine.parse_input(query_input)

        with st.status("Running OSINT Scan...", expanded=True):

            leads = engine.find_leads(company, domain, variations)

            if not leads:
                st.warning("No leads found. Try broader keywords.")
            else:
                results = []

                for lead in leads:
                    emails = engine.generate_email(
                        lead["Full Name"],
                        domain
                    )

                    results.append({
                        "Name": lead["Full Name"],
                        "Role": lead["Role"],
                        "Source": lead["Source"],
                        "Top Email Guesses": ", ".join(emails[:3])
                    })

                df = pd.DataFrame(results)

                st.success(f"Found {len(df)} decision-makers")
                st.dataframe(df, use_container_width=True, hide_index=True)

# ================= FOOTER =================
st.info("⚠️ Emails are pattern-based guesses. Verify before use.")
