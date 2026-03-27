import streamlit as st
import pandas as pd
import time
import re
from duckduckgo_search import DDGS
from rapidfuzz import fuzz

# ================= CORE ENGINE =================
class FreeOSINTFramework:
    def __init__(self):
        self.patterns = [
            "{first}.{last}@{domain}",
            "{f}{last}@{domain}",
            "{first}@{domain}",
            "{first}{last}@{domain}",
            "{first}{l}@{domain}"
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

    # -------- SEARCH LEADS --------
    def find_leads(self, company_name, domain):
        leads = []

        roles = "(CEO OR Founder OR Owner OR Director OR Manager OR VP)"
        query = f'site:linkedin.com/in/ ("{company_name}" OR "{domain}") {roles}'

        try:
            with DDGS() as ddgs:
                results = ddgs.text(query, max_results=15)

                for r in results:
                    title = r.get("title", "")

                    # Relaxed matching
                    if fuzz.partial_ratio(company_name.lower(), title.lower()) > 60:
                        
                        # Extract clean name
                        name = re.split(r"[-|]", title)[0].strip()

                        # Basic validation
                        if len(name.split()) >= 2:
                            leads.append({
                                "Full Name": name,
                                "LinkedIn": r.get("href"),
                                "Snippet": r.get("body", "")
                            })

        except Exception as e:
            st.error(f"Search Error: {e}")

        return leads

    # -------- EMAIL GUESSING ONLY --------
    def generate_email(self, full_name, domain):
        parts = full_name.lower().split()
        if len(parts) < 2:
            return "Invalid Name"

        first = parts[0]
        last = parts[-1]

        emails = []
        for p in self.patterns:
            emails.append(
                p.format(
                    first=first,
                    last=last,
                    f=first[0],
                    l=last[0],
                    domain=domain
                )
            )

        return emails


# ================= STREAMLIT UI =================
st.set_page_config(page_title="OSINT Lead Engine", layout="wide")

st.title("🧠 OSINT Lead Finder (Actually Works Version)")
st.markdown("Find decision-makers using LinkedIn dorking + smart email guessing.")

col1, col2 = st.columns(2)

with col1:
    company_name = st.text_input("Company Name", placeholder="e.g. Tesla")

with col2:
    company_domain = st.text_input("Company Domain", placeholder="e.g. tesla.com")

if st.button("Run OSINT Scan", type="primary"):
    if not company_name or not company_domain:
        st.error("Enter both company name and domain.")
    else:
        engine = FreeOSINTFramework()

        # Clean inputs
        company_name = engine.clean_name(company_name)
        company_domain = engine.clean_domain(company_domain)

        with st.status("Running OSINT Scan...", expanded=True) as status:
            st.write("🔍 Searching LinkedIn profiles...")
            
            leads = engine.find_leads(company_name, company_domain)

            if not leads:
                st.warning("No leads found. Try broader company name.")
                status.update(label="No Results", state="error")
            else:
                st.write(f"✅ Found {len(leads)} profiles")

                results = []

                for lead in leads:
                    st.write(f"Processing: {lead['Full Name']}")

                    emails = engine.generate_email(
                        lead["Full Name"], company_domain
                    )

                    results.append({
                        "Name": lead["Full Name"],
                        "LinkedIn": lead["LinkedIn"],
                        "Email Guesses": ", ".join(emails[:3]),
                        "Confidence": "Medium (Pattern-Based)"
                    })

                    time.sleep(0.5)

                status.update(label="Scan Complete", state="complete", expanded=False)

                st.divider()
                st.subheader(f"Results for {company_name}")

                df = pd.DataFrame(results)
                st.dataframe(df, use_container_width=True, hide_index=True)


# ================= FOOTER =================
st.info(
    "⚠️ Note: Email verification via SMTP is disabled on cloud environments. "
    "Results are based on common corporate email patterns."
)
