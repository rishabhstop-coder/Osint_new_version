import streamlit as st
import pandas as pd
import re
import time
import random
from duckduckgo_search import DDGS
from rapidfuzz import fuzz

class SimpleLeadFinder:
    def __init__(self):
        self.email_patterns = [
            "{first}.{last}@{domain}",
            "{first}{last}@{domain}",
            "{f}{last}@{domain}",
            "{first}@{domain}",
            "{first}_{last}@{domain}",
            "{last}.{first}@{domain}",
        ]

    def parse_input(self, query):
        query = query.strip()
        if not query:
            return "", ""
        
        if re.search(r'\.(com|in|net|org|io|co)$', query.lower()) or "://" in query:
            domain = self.clean_domain(query)
            company = domain.split(".")[0].replace("-", " ").title()
        else:
            company = query
            domain = ""
        return company, domain.lower()

    def clean_domain(self, domain):
        return (domain.lower()
                .replace("https://", "").replace("http://", "")
                .replace("www.", "").strip("/"))

    def extract_name(self, title):
        title = re.sub(r'\s*\|\s*.*', '', title)
        title = re.sub(r' at .*', '', title, flags=re.I)
        title = re.sub(r'[-–—|]', ' ', title).strip()
        parts = title.split()[:4]
        name = " ".join(parts).title()
        return name if len(parts) >= 2 else None

    def extract_role(self, text):
        text_lower = text.lower()
        if "ceo" in text_lower or "chief executive" in text_lower:
            return "CEO"
        if "cto" in text_lower or "chief technology" in text_lower:
            return "CTO"
        if "founder" in text_lower:
            return "Founder / Co-Founder"
        if "director" in text_lower:
            return "Director"
        return "Decision Maker"

    def find_leads(self, company, domain):
        leads = []
        queries = [
            f'"{company}" CEO OR Founder OR CTO',
            f'{company} (CEO OR Founder OR CTO) Ahmedabad',
            f'site:in.linkedin.com/in "{company}"',
            f'site:linkedin.com/in "{company}"',
            f'"{company}" linkedin'
        ]

        with DDGS() as ddgs:
            for q in queries:
                try:
                    results = list(ddgs.text(q, max_results=12))
                    for r in results:
                        link = r.get("href", "")
                        title = r.get("title", "")
                        snippet = r.get("body", "")

                        if "linkedin.com/in" not in link:
                            continue

                        name = self.extract_name(title)
                        if not name:
                            continue

                        combined = (title + " " + snippet).lower()
                        score = fuzz.token_set_ratio(company.lower(), combined)

                        if score > 35 or company.lower() in combined:
                            role = self.extract_role(combined)
                            leads.append({
                                "Full Name": name,
                                "Role": role,
                                "Source": link,
                                "Score": score
                            })
                    time.sleep(random.uniform(0.7, 1.4))
                except:
                    continue

        # Remove duplicates
        unique = {}
        for lead in leads:
            n = lead["Full Name"]
            if n not in unique or lead["Score"] > unique[n]["Score"]:
                unique[n] = lead

        return sorted(unique.values(), key=lambda x: x["Score"], reverse=True)

    def generate_emails(self, full_name, domain):
        if not domain:
            return ["No domain"]
        parts = full_name.lower().split()
        if len(parts) < 2:
            return ["Invalid name"]
        first = parts[0]
        last = parts[-1]
        f = first[0]
        return [p.format(first=first, last=last, f=f, domain=domain) for p in self.email_patterns][:3]


# ====================== STREAMLIT APP ======================
st.set_page_config(page_title="Simple OSINT Finder", layout="wide")
st.title("🚀 Simple OSINT Decision-Maker Finder")

st.markdown("**Super simplified version** — specially for small Indian companies like Briskstar")

query = st.text_input("Company Name or Domain", 
                      placeholder="briskstar.com or Briskstar Technologies",
                      help="Try domain first → briskstar.com")

if st.button("🔍 Run Search", type="primary"):
    if not query:
        st.error("Please enter something")
    else:
        engine = SimpleLeadFinder()
        company, domain = engine.parse_input(query)

        st.write(f"**Scanning:** {company} | Domain: {domain or 'N/A'}")

        with st.spinner("Searching public sources... (DDGS is slow)"):
            leads = engine.find_leads(company, domain)

        if leads:
            results = []
            for lead in leads:
                emails = engine.generate_emails(lead["Full Name"], domain)
                results.append({
                    "Name": lead["Full Name"],
                    "Role": lead["Role"],
                    "Email Guesses": ", ".join(emails),
                    "Source": lead["Source"]
                })

            df = pd.DataFrame(results)
            st.success(f"✅ Found {len(df)} leads")
            st.dataframe(df, use_container_width=True, hide_index=True)

            csv = df.to_csv(index=False).encode()
            st.download_button("📥 Download as CSV", csv, f"{company}_leads.csv", "text/csv")
        else:
            st.warning("No leads found from search. Try the domain or use manual paste below.")

# ====================== MANUAL PASTE SECTION ======================
st.divider()
st.subheader("Manual LinkedIn Links (Best when search fails)")

manual = st.text_area("Paste LinkedIn profile URLs (one per line)", height=180,
                      placeholder="https://in.linkedin.com/in/bhavesh-sanghani\nhttps://in.linkedin.com/in/keyur-soni-b7a1169")

if st.button("Process Manual Links"):
    if manual.strip():
        st.success("Links received. In real use, we can parse them better. For now, you can open them directly.")
        st.info("Known good links for Briskstar:\n• https://in.linkedin.com/in/bhavesh-sanghani (CEO & Co-Founder)\n• Bijal Soni is also a Co-Founder & CTO")
    else:
        st.warning("Paste at least one link")

st.caption("⚠️ This tool is for educational/OSINT use only. Emails are guesses only. DDGS is weak — that's why manual paste option is there.")
