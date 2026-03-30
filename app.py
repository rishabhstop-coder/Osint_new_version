import streamlit as st
import pandas as pd
import re
import time
import random
from duckduckgo_search import DDGS
from rapidfuzz import fuzz

class SimpleOSINTLeadEngine:
    def __init__(self):
        self.email_patterns = [
            "{first}.{last}@{domain}",
            "{first}{last}@{domain}",
            "{f}{last}@{domain}",
            "{first}@{domain}",
            "{first}_{last}@{domain}",
        ]

    def parse_input(self, user_input):
        user_input = user_input.strip()
        if not user_input:
            return "", ""

        if re.search(r'\.(com|in|net|org|io|co|tech)$', user_input.lower()) or "://" in user_input:
            domain = self.clean_domain(user_input)
            company = domain.split(".")[0].replace("-", " ").title()
        else:
            company = user_input
            domain = ""
        return company.strip(), domain.lower()

    def clean_domain(self, domain):
        return (domain.lower()
                .replace("https://", "")
                .replace("http://", "")
                .replace("www.", "")
                .strip("/"))

    def extract_name(self, title):
        title = re.sub(r'\s*\|\s*.*', '', title)
        title = re.sub(r'\s*at .*', '', title, flags=re.I)
        title = re.sub(r'[-–—|]', ' ', title).strip()
        parts = title.split()[:4]
        name = " ".join(parts).title()
        return name if len(parts) >= 2 else None

    def extract_role(self, text):
        text = text.lower()
        roles = ["ceo", "founder", "co-founder", "cto", "director", "owner", "head of", "vp"]
        for role in roles:
            if role in text:
                return role.upper()
        return "Decision Maker"

    def find_leads(self, company, domain):
        leads = []
        queries = [
            f'"{company}" (CEO OR Founder OR "Co-Founder" OR CTO OR Director)',
            f'{company} CEO OR Founder OR Director',
            f'site:in.linkedin.com/in "{company}"',
            f'site:linkedin.com/in "{company}"',
            f'"{company}" linkedin'
        ]

        with DDGS() as ddgs:
            for query in queries:
                try:
                    results = list(ddgs.text(query, max_results=10))
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

                        if score > 40 or company.lower() in combined:
                            role = self.extract_role(combined)
                            leads.append({
                                "Full Name": name,
                                "Role": role,
                                "Source": link,
                                "Score": score
                            })
                    time.sleep(random.uniform(0.8, 1.5))
                except:
                    continue

        # Deduplicate
        seen = {}
        for lead in leads:
            n = lead["Full Name"]
            if n not in seen or lead["Score"] > seen[n]["Score"]:
                seen[n] = lead

        return sorted(seen.values(), key=lambda x: x["Score"], reverse=True)

    def generate_emails(self, full_name, domain):
        if not domain:
            return ["No domain provided"]
        parts = full_name.lower().split()
        if len(parts) < 2:
            return ["Invalid name"]
        first, last = parts[0], parts[-1]
        f = first[0]
        return [p.format(first=first, last=last, f=f, domain=domain) for p in self.email_patterns][:3]


# ================= SIMPLE UI =================
st.set_page_config(page_title="OSINT Lead Finder", layout="wide")
st.title("🚀 Simple OSINT Decision-Maker Finder")

st.markdown("**Made simple for Indian companies like Briskstar**")

query = st.text_input("Enter Company Name or Domain", 
                      placeholder="briskstar.com or Briskstar Technologies",
                      help="Tip: Using domain usually gives better results")

col1, col2 = st.columns([3,1])
with col1:
    if st.button("🔍 Run Search", type="primary", use_container_width=True):
        if not query:
            st.error("Enter company name or domain")
        else:
            engine = SimpleOSINTLeadEngine()
            company, domain = engine.parse_input(query)

            st.write(f"**Company:** {company} | **Domain:** {domain or 'Not detected'}")

            with st.spinner("Searching... (DDGS is slow, please wait)"):
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
                st.success(f"Found {len(df)} potential leads")
                st.dataframe(df, use_container_width=True, hide_index=True)

                csv = df.to_csv(index=False).encode()
                st.download_button("📥 Download CSV", csv, f"{company}_leads.csv", "text/csv")
            else:
                st.error("No leads found from search.")

# Manual paste section (very useful when DDGS fails)
st.divider()
st.subheader("Manual Paste (Recommended when search fails)")
manual_links = st.text_area("Paste LinkedIn profile links here (one per line)", height=150,
                            placeholder="https://in.linkedin.com/in/bhavesh-sanghani\nhttps://in.linkedin.com/in/keyur-soni-b7a1169")

if st.button("Process Manual Links"):
    if manual_links.strip():
        st.success("Manual links processed (add your own parsing logic if needed)")
        st.info("For now, copy the links and check manually. I can improve this part if you want.")
    else:
        st.warning("Paste some links first")

st.caption("⚠️ Emails are only guesses. DDGS is not as strong as Google. For best results, try domain first (briskstar.com).")
