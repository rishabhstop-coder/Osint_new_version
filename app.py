import streamlit as st
import pandas as pd
import dns.resolver
import smtplib
import socket
import time
from duckduckgo_search import DDGS
from rapidfuzz import fuzz

class FreeOSINTFramework:
    def __init__(self):
        self.timeout = 5
        # Common business email patterns used for permutation [3]
        self.patterns = [
            "{first}.{last}@{domain}",
            "{f}{last}@{domain}",
            "{first}@{domain}",
            "{first}{last}@{domain}",
            "{first}{l}@{domain}"
        ]

    # -------- 1. FREE DISCOVERY (DuckDuckGo Dorking) --------
    def find_leads_free(self, company_name, domain):
        """Uses free search operators to find employees on LinkedIn.[4, 5]"""
        leads =
        # Target decision-maker roles
        roles = '(CEO OR Founder OR Owner OR Director OR Manager OR VP)'
        query = f'site:linkedin.com/in/ "{company_name}" {roles}'
        
        try:
            with DDGS() as ddgs:
                results = ddgs.text(query, max_results=10)
                if results:
                    for r in results:
                        title = r.get("title", "")
                        # RapidFuzz: Must match company name with 80%+ confidence [2, 6]
                        if fuzz.partial_ratio(company_name.lower(), title.lower()) > 80:
                            # Clean the title to extract just the name part
                            name_part = title.split(" - ").split(" | ").strip()
                            leads.append({
                                "Full Name": name_part,
                                "LinkedIn": r.get("href"),
                                "Snippet": r.get("body", "")
                            })
        except Exception as e:
            st.error(f"Search Error: {e}")
            
        return leads

    # -------- 2. FREE VERIFICATION (SMTP Handshake) --------
    def verify_email_local(self, email):
        """Performs a direct SMTP handshake to verify mailbox existence.[7, 1]"""
        try:
            domain = email.split('@')[8]
            # Resolve MX records to find the mail server 
            records = dns.resolver.resolve(domain, 'MX')
            mx_record = sorted(records, key=lambda r: r.preference).exchange.to_text()
            
            # Connect and perform a non-sending probe
            with smtplib.SMTP(mx_record, port=25, timeout=self.timeout) as server:
                server.helo(socket.gethostname())
                server.mail('test@example.com')
                code, message = server.rcpt(email)
                
                # Code 250 means the mailbox exists [1]
                return True if code == 250 else False
        except Exception:
            return False

    # -------- 3. PATTERN PERMUTATION --------
    def guess_and_verify(self, full_name, domain):
        """Generates email permutations and tests them locally."""
        parts = full_name.lower().split()
        if len(parts) < 2: return "Incomplete Name"
        
        first = parts
        last = parts[-1]
        
        for p in self.patterns:
            email = p.format(first=first, last=last, f=first, l=last, domain=domain)
            if self.verify_email_local(email):
                return email
        return "Not Found (Local Probe)"

# ================= STREAMLIT UI =================
st.set_page_config(page_title="Free OSINT Prober", layout="wide")
st.title("🆓 100% Free OSINT Lead Engine")
st.markdown("This tool performs **LinkedIn Dorking** and **SMTP Handshaking** on your own hardware.")

col_in1, col_in2 = st.columns(2)
with col_in1:
    target_company = st.text_input("Company Name", placeholder="e.g. Apple")
with col_in2:
    target_domain = st.text_input("Company Domain", placeholder="e.g. apple.com")

if st.button("Initialize Deep Probe", type="primary"):
    if not target_company or not target_domain:
        st.error("Please provide both a name and a domain.")
    else:
        engine = FreeOSINTFramework()
        
        with st.status("Gathering Intelligence...", expanded=True) as status:
            # Step 1: Search Discovery
            st.write("🔍 Chaining search operators for LinkedIn profiles...")
            raw_leads = engine.find_leads_free(target_company, target_domain)
            
            if not raw_leads:
                st.warning("No profiles found. Try a broader company name.")
                status.update(label="Probe Failed", state="error")
            else:
                st.write(f"🧬 Found {len(raw_leads)} potential profiles. Resolving entities...")
                
                # Step 2: Verification Loop
                results =
                for lead in raw_leads:
                    st.write(f"📡 Probing mail server for: {lead['Full Name']}...")
                    verified_email = engine.guess_and_verify(lead["Full Name"], target_domain)
                    
                    results.append({
                        "Name": lead["Full Name"],
                        "Verified Email": verified_email,
                        "LinkedIn URL": lead["LinkedIn"],
                        "Reliability": "High (SMTP Confirmed)" if "@" in verified_email else "Low (Discovery Only)"
                    })
                    # Delay to avoid firewall triggers
                    time.sleep(1)
                
                status.update(label="Probe Complete!", state="complete", expanded=False)
                
                # Step 3: Dashboard Display
                st.divider()
                st.subheader(f"Results for {target_company}")
                df = pd.DataFrame(results)
                st.dataframe(df, use_container_width=True, hide_index=True)

st.info("⚠️ **Technical Note:** SMTP probing (Port 25) is often blocked by residential ISPs and cloud providers like AWS/GCP to prevent spam.[1] This script works best on local machines or specialized OSINT VPS servers.")
