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
        self.patterns = [
            "{first}.{last}@{domain}",
            "{f}{last}@{domain}",
            "{first}@{domain}",
            "{first}{last}@{domain}",
            "{first}{l}@{domain}"
        ]

    # -------- 1. FREE DISCOVERY --------
    def find_leads_free(self, company_name, domain):
        leads = []  # FIXED

        roles = '(CEO OR Founder OR Owner OR Director OR Manager OR VP)'
        query = f'site:linkedin.com/in/ "{company_name}" {roles}'
        
        try:
            with DDGS() as ddgs:
                results = ddgs.text(query, max_results=10)
                if results:
                    for r in results:
                        title = r.get("title", "")
                        
                        if fuzz.partial_ratio(company_name.lower(), title.lower()) > 80:
                            # FIXED name extraction
                            name_part = title.split(" - ")[0].split(" | ")[0].strip()

                            leads.append({
                                "Full Name": name_part,
                                "LinkedIn": r.get("href"),
                                "Snippet": r.get("body", "")
                            })
        except Exception as e:
            st.error(f"Search Error: {e}")
            
        return leads

    # -------- 2. EMAIL VERIFICATION --------
    def verify_email_local(self, email):
        try:
            domain = email.split('@')[1]  # FIXED
            
            records = dns.resolver.resolve(domain, 'MX')
            mx_record = sorted(records, key=lambda r: r.preference)[0].exchange.to_text()
            
            with smtplib.SMTP(mx_record, port=25, timeout=self.timeout) as server:
                server.helo(socket.gethostname())
                server.mail('test@example.com')
                code, message = server.rcpt(email)
                
                return True if code == 250 else False
        except Exception:
            return False

    # -------- 3. PATTERN PERMUTATION --------
    def guess_and_verify(self, full_name, domain):
        parts = full_name.lower().split()
        if len(parts) < 2:
            return "Incomplete Name"
        
        first = parts[0]  # FIXED
        last = parts[-1]

        for p in self.patterns:
            email = p.format(first=first, last=last, f=first[0], l=last[0], domain=domain)  # FIXED
            
            if self.verify_email_local(email):
                return email
        
        return "Not Found (Local Probe)"

# ================= STREAMLIT UI =================
st.set_page_config(page_title="Free OSINT Prober", layout="wide")
st.title("🆓 100% Free OSINT Lead Engine")
st.markdown("This tool performs **LinkedIn Dorking** and **SMTP Handshaking**.")

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
            st.write("🔍 Searching LinkedIn profiles...")
            raw_leads = engine.find_leads_free(target_company, target_domain)
            
            if not raw_leads:
                st.warning("No profiles found. Try a broader company name.")
                status.update(label="Probe Failed", state="error")
            else:
                st.write(f"🧬 Found {len(raw_leads)} profiles...")
                
                results = []  # FIXED
                
                for lead in raw_leads:
                    st.write(f"📡 Checking: {lead['Full Name']}...")
                    
                    verified_email = engine.guess_and_verify(
                        lead["Full Name"], target_domain
                    )
                    
                    results.append({
                        "Name": lead["Full Name"],
                        "Verified Email": verified_email,
                        "LinkedIn URL": lead["LinkedIn"],
                        "Reliability": "High" if "@" in verified_email else "Low"
                    })
                    
                    time.sleep(1)
                
                status.update(label="Probe Complete!", state="complete", expanded=False)
                
                st.divider()
                st.subheader(f"Results for {target_company}")
                
                df = pd.DataFrame(results)
                st.dataframe(df, use_container_width=True, hide_index=True)

st.info("⚠️ SMTP probing may fail due to ISP blocking (port 25).") 
