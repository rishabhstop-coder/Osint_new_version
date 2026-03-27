import streamlit as st
import pandas as pd
import dns.resolver
import smtplib
import socket
import asyncio
from duckduckgo_search import DDGS
from rapidfuzz import fuzz

class FreeOSINTFramework:
    def __init__(self):
        self.timeout = 10
        # Common business email patterns
        self.patterns = [
            "{first}.{last}@{domain}",
            "{f}{last}@{domain}",
            "{first}@{domain}",
            "{first}{last}@{domain}",
            "{first}{l}@{domain}"
        ]

    # -------- 1. FREE DISCOVERY (DuckDuckGo) --------
    def find_leads_free(self, company_name, domain):
        """Uses free search operators to find employees on LinkedIn.[4]"""
        leads =
        roles = '(CEO OR Founder OR Owner OR Director OR Manager OR VP)'
        query = f'site:linkedin.com/in/ "{company_name}" {roles}'
        
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=10)
            for r in results:
                title = r.get("title", "")
                # RapidFuzz validation: Profile must match company name 
                if fuzz.partial_ratio(company_name.lower(), title.lower()) > 80:
                    name_part = title.split(" - ").split(" | ")
                    leads.append({
                        "Full Name": name_part,
                        "LinkedIn": r.get("href"),
                        "Snippet": r.get("body")
                    })
        return leads

    # -------- 2. FREE VERIFICATION (SMTP Handshake) --------
    def verify_email_local(self, email):
        """Performs a direct SMTP handshake to verify existence."""
        try:
            domain = email.split('@')[1]
            # Resolve MX records 
            records = dns.resolver.resolve(domain, 'MX')
            mx_record = str(records.exchange)
            
            # Connect and simulate sending
            server = smtplib.SMTP(timeout=self.timeout)
            server.connect(mx_record)
            server.helo(socket.gethostname())
            server.mail('test@example.com')
            code, message = server.rcpt(email)
            server.quit()
            
            # 250 is the success code for a valid mailbox
            return True if code == 250 else False
        except Exception:
            return False

    # -------- 3. PATTERN GUESSING --------
    def guess_and_verify(self, full_name, domain):
        """Generates and tests email permutations locally."""
        parts = full_name.lower().split()
        if len(parts) < 2: return None
        
        first, last = parts, parts[-1]
        for p in self.patterns:
            email = p.format(first=first, last=last, f=first, l=last, domain=domain)
            if self.verify_email_local(email):
                return email
        return "Not Found (Free)"

# ================= STREAMLIT UI =================
st.title("🆓 100% Free OSINT Lead Engine")
st.markdown("Uses **Local SMTP Probing** and **DDGS Discovery** (No API Keys Required).")

target_company = st.text_input("Enter Company Name (e.g., Apple)")
target_domain = st.text_input("Enter Company Domain (e.g., apple.com)")

if st.button("Run Fully Free Scan", type="primary"):
    if not target_company or not target_domain:
        st.error("Please provide both name and domain.")
    else:
        engine = FreeOSINTFramework()
        
        with st.status("Performing local discovery...", expanded=True) as status:
            # Step 1: Discovery
            raw_leads = engine.find_leads_free(target_company, target_domain)
            st.write(f"🔍 Found {len(raw_leads)} potential profiles via DuckDuckGo.")
            
            # Step 2: Guessing & Verification
            results =
            for lead in raw_leads:
                st.write(f"📡 Probing email for {lead['Full Name']}...")
                verified_email = engine.guess_and_verify(lead["Full Name"], target_domain)
                results.append({
                    "Name": lead["Full Name"],
                    "Email": verified_email,
                    "LinkedIn": lead["LinkedIn"],
                    "Status": "Verified" if "@" in verified_email else "Unverified"
                })
            
            status.update(label="Local Scan Complete!", state="complete")

        st.table(pd.DataFrame(results))

st.info("⚠️ Note: Local SMTP verification success depends on your IP reputation and whether the target uses a 'Catch-All' server.")
