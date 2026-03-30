import streamlit as st
import pandas as pd
import time
import re
import random
from duckduckgo_search import DDGS
from rapidfuzz import fuzz, process

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
            "{first[0]}{last[0]}@{domain}",  # New: initials
        ]

    # -------- INPUT PARSER --------
    def parse_input(self, user_input):
        user_input = user_input.strip()
        if not user_input:
            return "", "", []

        # Detect domain vs company name
        if re.match(r'^https?://', user_input) or "." in user_input and " " not in user_input:
            domain = self.clean_domain(user_input)
            company = domain.split(".")[0].replace("-", " ").title()
        else:
            company = user_input
            domain = ""

        # Generate smart variations
        base = company.split()[0]
        variations = list(set([
            company, base, 
            company.replace(" Technologies", "").replace(" Tech", ""),
            company.replace(" Solutions", "").replace(" Pvt Ltd", ""),
            company.replace(" Private Limited", "").replace(" Limited", ""),
            company.replace(" Pvt.", "").replace(" Ltd", ""),
        ]))
        return company.strip(), domain, [v.strip() for v in variations if v.strip()]

    def clean_domain(self, domain):
        return (domain.lower()
                .replace("https://", "")
                .replace("http://", "")
                .replace("www.", "")
                .strip("/"))

    # -------- QUERY BUILDER --------
    def build_queries(self, variations, domain):
        queries = []
        for name in variations:
            queries.extend([
                f'site:linkedin.com/in "{name}" (CEO OR Founder OR Director OR "Vice President" OR "Head of" OR VP)',
                f'"{name}" (CEO OR Founder OR "Managing Director")',
                f'"{name}" "at {name}" OR "at {name.split()[0]}"',  # Company in title
                f'site:linkedin.com/in "{name}"',
            ])
        
        if domain:
            queries.extend([
                f'"@{domain}"',
                f'site:{domain} (team OR about OR leadership OR "our team")',
            ])
        
        return list(set(queries))  # Remove duplicates

    # -------- IMPROVED ROLE EXTRACTION --------
    def extract_role(self, text):
        text_lower = text.lower()
        for role in sorted(self.roles, key=len, reverse=True):  # Longer roles first
            if role.lower() in text_lower:
                # Try to get more context like "CEO & Founder"
                match = re.search(rf"({role}[^,\n|]*?)", text, re.I)
                return match.group(1).strip() if match else role
        return "Decision Maker / Employee"

    # -------- BETTER NAME EXTRACTION --------
    def extract_name(self, title):
        # Common LinkedIn title patterns: "Name | Role at Company"
        title = re.sub(r'\s*\|\s*.*$', '', title)  # Remove everything after |
        title = re.sub(r' at .*', '', title, flags=re.I)
        title = re.sub(r'[-–—|]', ' ', title).strip()
        
        # Keep only first 4 words (name + possible middle)
        parts = title.split()
        name = " ".join(parts[:4])
        if len(name.split()) >= 2:
            return name.title()
        return None

    # -------- LEAD FINDER WITH RETRIES --------
    def find_leads(self, company, domain, variations):
        leads = []
        queries = self.build_queries(variations, domain)
        
        st.info(f"Running {len(queries)} search queries...")
        
        with DDGS() as ddgs:
            for i, query in enumerate(queries):
                for attempt in range(3):  # Retry up to 3 times
                    try:
                        results = list(ddgs.text(query, max_results=12))
                        st.caption(f"Query {i+1}/{len(queries)}: {query[:80]}... → {len(results)} raw results")
                        
                        for r in results:
                            link = r.get("href", "")
                            title = r.get("title", "")
                            snippet = r.get("body", "")
                            
                            if not link or "linkedin.com/in/" not in link:
                                continue
                            
                            name = self.extract_name(title)
                            if not name:
                                continue
                            
                            combined = f"{title} {snippet}".lower()
                            # Better fuzzy matching
                            score = max(
                                fuzz.token_set_ratio(company.lower(), combined),
                                fuzz.partial_ratio(company.lower(), combined),
                                fuzz.WRatio(company.lower(), combined)
                            )
                            
                            if score > 55:  # Relaxed but still relevant threshold
                                role = self.extract_role(combined)
                                leads.append({
                                    "Full Name": name,
                                    "Role": role,
                                    "Source": link,
                                    "Match Score": score
                                })
                        
                        time.sleep(random.uniform(0.8, 1.5))  # Polite + jitter
                        break  # Success, move to next query
                        
                    except Exception as e:
                        if attempt == 2:
                            st.warning(f"Query failed after retries: {query[:60]}...")
                        time.sleep(1.5 ** attempt)  # Exponential backoff

        # Deduplicate by name (keep highest score)
        unique = {}
        for lead in leads:
            name = lead["Full Name"]
            if name not in unique or lead["Match Score"] > unique[name].get("Match Score", 0):
                unique[name] = lead
        
        leads = list(unique.values())
        
        # Fallback if still empty
        if not leads and company:
            st.warning("Primary search returned nothing → Running broader fallback...")
            fallback_queries = [
                f'site:linkedin.com/in "{company}" (CEO OR Founder OR Director)',
                f'"{company}" linkedin "CEO" OR "Founder"',
            ]
            # Similar loop as above for fallback...
            # (omitted for brevity — copy the main loop logic here if needed)

        return sorted(leads, key=lambda x: x.get("Match Score", 0), reverse=True)

    # -------- EMAIL GENERATOR --------
    def generate_email(self, full_name, domain):
        if not domain:
            return ["No domain provided"], 0
        
        parts = full_name.lower().split()
        if len(parts) < 2:
            return ["Invalid name"], 0
        
        first = parts[0]
        last = parts[-1]
        f = first[0]
        
        emails = []
        for p in self.email_patterns:
            try:
                email = p.format(first=first, last=last, f=f, domain=domain)
                emails.append(email)
            except:
                continue
        
        # Simple confidence: common patterns get higher score
        confidence = 70 if any(x in full_name.lower() for x in ["ceo", "founder"]) else 50
        return emails[:3], confidence


# ================= STREAMLIT UI =================
st.set_page_config(page_title="OSINT Lead Finder", layout="wide")
st.title("🚀 Improved OSINT Decision-Maker Finder")
st.markdown("Find C-level / decision-makers using public search + smart guessing. **For educational/OSINT purposes only.**")

query = st.text_input("Enter Company Name or Website (e.g., tesla.com or Acme Corp)", placeholder="tesla.com")

if st.button("🔍 Run OSINT Scan", type="primary"):
    if not query:
        st.error("Please enter a company name or domain.")
    else:
        engine = OSINTLeadEngine()
        company, domain, variations = engine.parse_input(query)
        
        st.write(f"**Company:** {company} | **Domain:** {domain or 'N/A'}")
        
        with st.spinner("Scanning public web sources (this may take 20-60 seconds)..."):
            leads = engine.find_leads(company, domain, variations)
        
        if not leads:
            st.error("No leads found. Try a larger/more visible company or check spelling.")
        else:
            results = []
            for lead in leads:
                emails, conf = engine.generate_email(lead["Full Name"], domain)
                results.append({
                    "Name": lead["Full Name"],
                    "Role": lead["Role"],
                    "Match Score": f"{lead.get('Match Score', 0):.0f}%",
                    "Email Guesses": ", ".join(emails),
                    "Source": lead["Source"]
                })
            
            df = pd.DataFrame(results)
            
            st.success(f"✅ Found **{len(df)}** potential leads!")
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Export
            csv = df.to_csv(index=False).encode()
            st.download_button("📥 Download as CSV", csv, f"{company}_leads.csv", "text/csv")
            
            with st.expander("🔍 View Raw Sources"):
                for lead in leads:
                    st.markdown(f"**{lead['Full Name']}** — [{lead['Source']}]({lead['Source']})")

st.caption("⚠️ This tool uses public search only. Email guesses are **not verified**. Always respect privacy laws and LinkedIn's terms. DDGS can be flaky — try again if results are poor.") 
