import time
import requests
import pandas as pd
import streamlit as st
from duckduckgo_search import DDGS
from playwright.sync_api import sync_playwright


# ================= ENGINE =================
class OSINTEngine:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    # -------- 1. CLEARBIT --------
    def enrich_company(self, query):
        clean_query = query.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]

        try:
            url = f"https://autocomplete.clearbit.com/v1/companies/suggest?query={clean_query}"
            res = self.session.get(url, timeout=5)

            if res.status_code == 200 and len(res.json()) > 0:
                data = res.json()[0]
                return {
                    "Name": data.get("name"),
                    "Domain": data.get("domain"),
                    "Logo": data.get("logo")
                }
        except:
            pass

        return {"Name": query.title(), "Domain": None, "Logo": None}

    # -------- 2. ROWS SCRAPER (FIXED) --------
    def get_linkedin_from_rows(self, company):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                page.goto("https://rows.com/tools/company-enricher")

                page.fill("input", company)
                page.keyboard.press("Enter")

                # Wait for LinkedIn result properly
                page.wait_for_selector("a[href*='linkedin.com/company']", timeout=10000)

                links = page.locator("a[href*='linkedin.com/company']").all()

                for link in links:
                    href = link.get_attribute("href")
                    if href:
                        browser.close()
                        return href

                browser.close()

        except Exception as e:
            print("Rows failed:", e)

        return None

    # -------- 3. BACKUP: FIND LINKEDIN VIA DORK --------
    def find_company_linkedin_backup(self, exact_name):
        query = f'site:linkedin.com/company "{exact_name}"'

        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=5)

            for r in results:
                url = r.get("href", "")
                if "linkedin.com/company" in url:
                    return url

        return None

    # -------- 4. EXTRACT SLUG --------
    def extract_slug(self, linkedin_url):
        if not linkedin_url:
            return None
        return linkedin_url.split("/company/")[-1].strip("/")

    # -------- 5. STRICT DORK --------
    def dork_strict(self, exact_name, slug):
        people = []
        roles = ["CEO", "Founder", "Owner", "Director", "Partner", "Manager"]

        with DDGS() as ddgs:
            for role in roles:
                query = f'site:linkedin.com/in "{exact_name}" "{role}"'

                try:
                    results = ddgs.text(query, max_results=10)

                    for r in results:
                        title = r.get("title", "")
                        href = r.get("href", "")
                        body = r.get("body", "")

                        combined = (title + body).lower()

                        if exact_name.lower() not in combined:
                            continue

                        if slug and slug not in href:
                            if exact_name.lower() not in combined:
                                continue

                        if "/company/" in href or "/dir/" in href:
                            continue

                        people.append({
                            "Name & Title": title.split(" - ")[0],
                            "Role": role,
                            "LinkedIn": href,
                            "Source": "Strict Mode"
                        })

                except:
                    continue

                time.sleep(1)

        return list({p["LinkedIn"]: p for p in people}.values())

    # -------- 6. FALLBACK DORK --------
    def dork_fallback(self, exact_name, domain):
        people = []

        roles = '(CEO OR Founder OR Owner OR Director OR Partner OR Manager)'
        query = f'site:linkedin.com/in "{exact_name}" {roles}'

        with DDGS() as ddgs:
            try:
                results = ddgs.text(query, max_results=20)

                for r in results:
                    title = r.get("title", "")
                    href = r.get("href", "")
                    body = r.get("body", "")

                    combined = (title + body).lower()

                    if exact_name.lower() not in combined:
                        continue

                    if domain and domain.split('.')[0] not in combined:
                        continue

                    if "/company/" in href or "/dir/" in href:
                        continue

                    people.append({
                        "Name & Title": title.split(" - ")[0],
                        "LinkedIn": href,
                        "Source": "Fallback Mode"
                    })

            except:
                pass

        return list({p["LinkedIn"]: p for p in people}.values())


# ================= UI =================
st.set_page_config(page_title="OSINT LinkedIn Finder", layout="wide")

st.title("🔍 OSINT LinkedIn Finder (Robust Version)")

company_input = st.text_input("Enter Company Name or URL")

if st.button("Run Scan"):
    if not company_input:
        st.error("Enter company first")
    else:
        engine = OSINTEngine()

        with st.spinner("Running OSINT Scan..."):

            # Step 1: Enrich
            company = engine.enrich_company(company_input)
            name = company["Name"]
            domain = company["Domain"]

            # Step 2: Try Rows
            linkedin_url = engine.get_linkedin_from_rows(name)

            # Step 3: Backup if Rows fails
            if not linkedin_url:
                st.warning("Rows failed → Trying backup LinkedIn search...")
                linkedin_url = engine.find_company_linkedin_backup(name)

            # Step 4: Decide dork strategy
            if linkedin_url:
                st.success("LinkedIn company found")
                slug = engine.extract_slug(linkedin_url)
                people = engine.dork_strict(name, slug)
            else:
                st.warning("No LinkedIn found → Using fallback dork")
                people = engine.dork_fallback(name, domain)

        # ================= RESULTS =================
        st.subheader("Company Info")

        col1, col2 = st.columns([1, 4])

        with col1:
            if company["Logo"]:
                st.image(company["Logo"], width=100)

        with col2:
            st.write(f"**Name:** {name}")
            st.write(f"**Domain:** {domain}")
            st.write(f"**LinkedIn:** {linkedin_url}")

        st.divider()

        st.subheader("Decision Makers")

        df = pd.DataFrame(people)

        if not df.empty:
            st.dataframe(df, use_container_width=True)

            st.download_button(
                "Download CSV",
                df.to_csv(index=False),
                file_name="leads.csv"
            )
        else:
            st.warning("No people found")
