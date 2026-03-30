import streamlit as st
import pandas as pd
import time
import re
from duckduckgo_search import DDGS
from rapidfuzz import fuzz

# ================= CORE ENGINE =================
class OSINTLeadEngine:
    def __init__(self):

        # Expanded decision-maker roles
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

        # Expanded email patterns
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

    # -------- CLEAN INPUT --------
    def clean_domain(self, domain):
        return (
            domain.replace("https://", "")
            .replace("http://", "")
            .replace("www.", "")
            .strip("/")
        )

    def clean_name(self, name):
        return name.strip()

    # -------- BUILD SEARCH QUERIES --------
    def build_queries(self, company_name, domain):
        role_query = " OR ".join([f'"{r}"' for r in self.roles])

        return [
            # LinkedIn (primary)
            f'site:linkedin.com/in ("{company_name}" OR "{domain}") ({role_query})',
            f'site:linkedin.com/in "{company_name}" ("CEO" OR "Founder" OR "Director")',
            f'site:linkedin.com/in "{company_name}" ("marketing" OR "growth" OR "head")',

            # General Google
            f'"{company_name}" ("CEO" OR "Founder" OR "Managing Director")',

            # Website pages
            f'site:{domain} ("team" OR "about" OR "leadership")',

            # Emails exposed
            f'"@{domain}" ("CEO" OR "Founder" OR "Director")',

            # PDFs (hidden goldmine)
            f'site:{domain} filetype:pdf ("CEO" OR "Director")',

            # News mentions
            f'"{company_name}" "CEO said"',

            # Crunchbase / profiles
            f'site:crunchbase.com "{company_name}"',

            # Social bios
            f'site:twitter.com "{company_name}" ("founder" OR "ceo")'
        ]

    # -------- EXTRACT ROLE --------
    def extract_role(self, text):
        match = re.findall(
            r"(CEO|Founder|Director|Head|Manager|VP|Chief|Owner)",
            text,
            re.I
        )
        return match[0] if match else "N/A"

    # -------- FIND LEADS --------
    def find_leads(self, company_name, domain):
        leads = []
        queries = self.build_queries(company_name, domain)

        try:
            with DDGS() as ddgs:
                for query in queries:
                    results = ddgs.text(query, max_results=10)

                    for r in results:
                        title = r.get("title", "")
                        snippet = r.get("body", "")
                        link = r.get("href")

                        combined = f"{title} {snippet}".lower()

                        # Fuzzy match company relevance
                        if fuzz.partial_ratio(company_name.lower(), combined) > 55:

                            name = re.split(r"[-|,]", title)[0].strip()

                            if 2 <= len(name.split()) <= 4:
                                role = self.extract_role(combined)

                                leads.append({
                                    "Full Name": name,
                                    "Role": role,
                                    "Source": link,
                                    "Snippet": snippet
                                })

        except Exception as e:
            st.error(f"Search Error: {e}")

        # Remove duplicates
        unique = {l["Full Name"]: l for l in leads}

        # Prioritize decision-makers
        priority = {"CEO": 1, "Founder": 1, "Owner": 1, "Chief": 1,
                    "Director": 2, "VP": 3, "Head": 3, "Manager": 4}

        sorted_leads = sorted(
            unique.values(),
            key=lambda x: priority.get(x["Role"], 5)
        )

        return sorted_leads

    # -------- EMAIL GUESSING --------
    def generate_email(self, full_name, domain):
        parts = full_name.lower().split()

        if len(parts) < 2:
            return ["Invalid Name"]

        first = parts[0]
        last = parts[-1]

        emails = [
            p.format(
                first=first,
                last=last,
                f=first[0],
                l=last[0],
                domain=domain
            )
            for p in self.patterns
        ]

        return emails


# ================= STREAMLIT UI =================
st.set_page_config(page_title="OSINT Lead Engine PRO", layout="wide")

st.title("🚀 OSINT Decision-Maker Finder")
st.markdown("Find CEOs, founders, and key decision-makers using advanced dorking.")

col1, col2 = st.columns(2)

with col1:
    company_name = st.text_input("Company Name", placeholder="e.g. Tesla")

with col2:
    company_domain = st.text_input("Company Domain", placeholder="e.g. tesla.com")

if st.button("Run Scan", type="primary"):

    if not company_name or not company_domain:
        st.error("Enter both fields.")
    else:
        engine = OSINTLeadEngine()

        company_name = engine.clean_name(company_name)
        company_domain = engine.clean_domain(company_domain)

        with st.status("Running OSINT Scan...", expanded=True):

            leads = engine.find_leads(company_name, company_domain)

            if not leads:
                st.warning("No leads found. Try broader keywords.")
            else:
                results = []

                for lead in leads:
                    emails = engine.generate_email(
                        lead["Full Name"],
                        company_domain
                    )

                    results.append({
                        "Name": lead["Full Name"],
                        "Role": lead["Role"],
                        "Source": lead["Source"],
                        "Top Email Guesses": ", ".join(emails[:3])
                    })

                    time.sleep(0.3)

                df = pd.DataFrame(results)

                st.success(f"Found {len(df)} decision-makers")
                st.dataframe(df, use_container_width=True, hide_index=True)


# ================= FOOTER =================
st.info(
    "⚠️ Emails are pattern-based guesses. Use verification tools for accuracy."
)
