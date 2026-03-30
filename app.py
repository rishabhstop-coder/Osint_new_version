import streamlit as st
import pandas as pd
import time
import re
import random
from duckduckgo_search import DDGS
from rapidfuzz import fuzz

# ================= CORE ENGINE =================
class OSINTLeadEngine:
    def __init__(self):
        self.roles = [
            "CEO", "Founder", "Co-Founder", "Owner", "Managing Director", "Director",
            "Head of", "VP", "Vice President", "Chief", "CFO", "CTO", "CMO", "COO"
        ]
        
        self.email_patterns = [
            "{first}.{last}@{domain}",
            "{first}{last}@{domain}",
            "{f}{last}@{domain}",
            "{first}@{domain}",
            "{first}_{last}@{domain}",
            "{last}.{first}@{domain}",
            "{f}{last[0]}@{domain}",
            "{first[0]}{last}@{domain}",
        ]

    # -------- INPUT PARSER --------
    def parse_input(self, user_input):
        user_input = user_input.strip()
        if not user_input:
            return "", "", []

        # Auto-detect domain vs company name
        if re.search(r'\.(com|in|net|org|io|co|ai|tech)$', user_input.lower()) or "://" in user_input:
            domain = self.clean_domain(user_input)
            company = domain.split(".")[0].replace("-", " ").title()
        else:
            company = user_input
            domain = ""

        # Smart variations (removes common suffixes)
        base = company.split()[0]
        variations = list(set([
            company,
            base,
            company.replace(" Technologies", "").replace(" Tech", ""),
            company.replace(" Solutions", "").replace(" Pvt Ltd", ""),
            company.replace(" Private Limited", "").replace(" Limited", ""),
            company.replace(" Pvt.", "").replace(" LLP", "").replace(" Ltd", ""),
        ]))
        return company.strip(), domain.lower(), [v.strip() for v in variations if v.strip()]

    def clean_domain(self, domain):
        return (domain.lower()
                .replace("https://", "")
                .replace("http://", "")
                .replace("www.", "")
                .strip("/"))

    # -------- QUERY BUILDER (OPTIMIZED FOR INDIAN COMPANIES) --------
    def build_queries(self, variations, domain):
        queries = []
        for name in variations:
            name_clean = name.replace(" Technologies", "").replace(" Tech", "").strip()
            
            queries.extend([
                f'"{name}" (CEO OR Founder OR "Co-Founder" OR Director OR CTO OR "Managing Director")',
                f'"{name_clean}" (CEO OR Founder OR Director)',
                f'site:linkedin.com/in "{name}"',
                f'site:in.linkedin.com/in "{name}"',           # Critical for Indian companies
                f'site:linkedin.com/in "{name}" (CEO OR Founder)',
                f'"{name}" "CEO" OR "Founder" OR "Director"',
            ])
        
        # Domain-based queries
        if domain:
            queries.extend([
                f'"@{domain}"',
                f'site:{domain} (team OR leadership OR "our team" OR about)',
            ])
        
        # Extra broad queries (helps when DDGS is weak)
        queries.extend([
            f'"{variations[0]}" linkedin',
            f'{variations[0]} CEO OR Founder OR Director site:linkedin.com',
        ])
        
        return list(set(queries))  # Remove duplicates

    # -------- SMART NAME EXTRACTION --------
    def extract_name(self, title):
        # Clean common LinkedIn title junk
        title = re.sub(r'\s*\|\s*.*$', '', title)           # Remove " | Role at Company"
        title = re.sub(r'\s*at .*', '', title, flags=re.I)  # Remove "at Company"
        title = re.sub(r'[-–—|]', ' ', title).strip()
        
        # Take first 4 words max
        parts = title.split()[:4]
        name = " ".join(parts).title()
        
        if len(name.split()) >= 2:
            return name
        return None

    # -------- ROLE EXTRACTION --------
    def extract_role(self, text):
        text_lower = text.lower()
        for role in sorted(self.roles, key=len, reverse=True):
            if role.lower() in text_lower:
                match = re.search(rf"({role}[^,\n|]*)", text, re.I)
                return match.group(1).strip() if match else role
        return "Decision Maker"

    # -------- LEAD FINDER (ROBUST + RETRIES) --------
    def find_leads(self, company, domain, variations):
        leads = []
        queries = self.build_queries(variations, domain)
        
        st.info(f"🔎 Running {len(queries)} smart search queries...")
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        with DDGS() as ddgs:
            for i, query in enumerate(queries):
                status_text.text(f"Query {i+1}/{len(queries)} → {query[:75]}...")
                progress_bar.progress((i + 1) / len(queries))
                
                for attempt in range(4):  # up to 4 retries
                    try:
                        results = list(ddgs.text(query, max_results=15, safesearch="off"))
                        
                        for r in results:
                            link = r.get("href", "")
                            title = r.get("title", "")
                            snippet = r.get("body", "")
                            
                            if not link or "linkedin.com/in" not in link:
                                continue
                            
                            name = self.extract_name(title)
                            if not name:
                                continue
                            
                            combined = (title + " " + snippet).lower()
                            score = max(
                                fuzz.token_set_ratio(company.lower(), combined),
                                fuzz.partial_ratio(company.lower(), combined)
                            )
                            
                            # Lower threshold for small/Indian companies
                            if score > 45 or company.lower() in combined:
                                role = self.extract_role(combined)
                                leads.append({
                                    "Full Name": name,
                                    "Role": role,
                                    "Source": link,
                                    "Match Score": score
                                })
                        
                        # Random polite delay
                        time.sleep(random.uniform(1.0, 2.2))
                        break
                        
                    except Exception:
                        if attempt == 3:
                            st.caption(f"⚠️ Query failed: {query[:60]}...")
                        time.sleep(1.5 ** attempt)  # exponential backoff
        
        # Deduplicate (keep best match)
        unique = {}
        for lead in leads:
            n = lead["Full Name"]
            if n not in unique or lead["Match Score"] > unique[n].get("Match Score", 0):
                unique[n] = lead
        
        return sorted(unique.values(), key=lambda x: x.get("Match Score", 0), reverse=True)

    # -------- EMAIL GENERATOR --------
    def generate_email(self, full_name, domain):
        if not domain:
            return ["No domain → manual check needed"], 0
        
        parts = full_name.lower().split()
        if len(parts) < 2:
            return ["Invalid name"], 0
        
        first = parts[0]
        last = parts[-1]
        f = first[0]
        
        emails = [p.format(first=first, last=last, f=f, domain=domain) for p in self.email_patterns]
        return emails[:3], 65  # confidence


# ================= STREAMLIT UI =================
st.set_page_config(page_title="🚀 OSINT Decision-Maker Finder", layout="wide")
st.title("🚀 OSINT Decision-Maker Finder")
st.markdown("**Now optimized for Indian companies** (Briskstar, etc.) — better LinkedIn coverage + smarter dorks")

query = st.text_input(
    "Company Name or Website",
    placeholder="briskstar.com or Briskstar Technologies",
    help="Tip: Use domain (briskstar.com) for better email guessing"
)

if st.button("🔍 Run OSINT Scan", type="primary", use_container_width=True):
    if not query:
        st.error("Please enter a company name or domain.")
    else:
        engine = OSINTLeadEngine()
        company, domain, variations = engine.parse_input(query)
        
        st.subheader(f"**Scanning:** {company}")
        if domain:
            st.caption(f"Domain detected: **{domain}**")
        
        with st.spinner("Searching public sources (20–60 seconds)... DDGS can be slow — be patient"):
            leads = engine.find_leads(company, domain, variations)
        
        if not leads:
            st.error("❌ No leads found. Try entering the **domain** instead (e.g. briskstar.com) or a larger company.")
            st.info("💡 For very small Indian companies, DDGS is limited. Consider using Google manually and paste links here later.")
        else:
            results = []
            for lead in leads:
                emails, conf = engine.generate_email(lead["Full Name"], domain)
                results.append({
                    "Name": lead["Full Name"],
                    "Role": lead["Role"],
                    "Match %": f"{lead.get('Match Score', 0):.0f}%",
                    "Email Guesses": ", ".join(emails),
                    "Source": lead["Source"]
                })
            
            df = pd.DataFrame(results)
            
            st.success(f"✅ Found **{len(df)}** potential decision-makers!")
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Export CSV
            csv = df.to_csv(index=False).encode()
            st.download_button(
                label="📥 Download Leads as CSV",
                data=csv,
                file_name=f"{company.replace(' ', '_')}_leads.csv",
                mime="text/csv"
            )
            
            with st.expander("🔍 View Raw LinkedIn Links"):
                for lead in leads:
                    st.markdown(f"**{lead['Full Name']}** — [{lead['Source']}]({lead['Source']})")

st.caption("""
⚠️ This tool uses only public DuckDuckGo search.  
• Emails are **guesses only** — verify before use.  
• For best results with Indian companies, always try the **.com** domain.  
• DDGS can be flaky — if you get zero results, try again or use Google manually.
""")
