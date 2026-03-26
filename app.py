import time
import requests
import pandas as pd
import streamlit as st
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup


# ================= HELPER =================
def clean_domain(url):
    return url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]


def google_search(query):
    headers = {"User-Agent": "Mozilla/5.0"}
    url = "https://www.google.com/search"
    params = {"q": query}

    res = requests.get(url, headers=headers, params=params)
    soup = BeautifulSoup(res.text, "html.parser")

    links = []
    for a in soup.select("a"):
        href = a.get("href")
        if href and "/url?q=" in href:
            clean = href.split("/url?q=")[1].split("&")[0]
            links.append(clean)

    return links


# ================= ENGINE =================
class OSINTEngine:

    def __init__(self):
        self.session = requests.Session()

    # -------- 1. CLEARBIT --------
    def enrich_company(self, query):
        clean_query = clean_domain(query)

        try:
            url = f"https://autocomplete.clearbit.com/v1/companies/suggest?query={clean_query}"
            res = self.session.get(url)

            if res.status_code == 200 and len(res.json()) > 0:
                data = res.json()[0]
                return {
                    "Name": data.get("name"),
                    "Domain": data.get("domain"),
                    "Logo": data.get("logo")
                }
        except:
            pass

        return {"Name": query.title(), "Domain": clean_query, "Logo": None}

    # -------- 2. ROWS SCRAPER (FIXED TEXTAREA) --------
    def get_linkedin_from_rows(self, domain):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"]
                )

                context = browser.new_context(
                    user_agent="Mozilla/5.0"
                )

                page = context.new_page()

                page.goto("https://rows.com/tools/company-enricher", timeout=60000)

                # ✅ Correct selector (textarea)
                page.wait_for_selector("textarea[placeholder='Type here...']", timeout=10000)

                textarea = page.locator("textarea[placeholder='Type here...']")

                textarea.fill("")
                textarea.type(domain, delay=120)

                page.keyboard.press("Enter")

                # Wait for results
                page.wait_for_timeout(7000)

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

    # -------- 3. BACKUP LINKEDIN FINDER --------
    def find_company_linkedin(self, name, domain):
        queries = [
            f'site:linkedin.com/company "{domain}"',
            f'site:linkedin.com/company "{name}"'
        ]

        for query in queries:
            links = google_search(query)

            for link in links:
                if "linkedin.com/company" in link:
                    return link

        return None

    # -------- 4. EXTRACT SLUG --------
    def extract_slug(self, linkedin_url):
        if not linkedin_url:
            return None
        return linkedin_url.split("/company/")[-1].strip("/")

    # -------- 5. FIND PEOPLE --------
    def find_people(self, name):
        roles = ["CEO", "Founder", "Owner", "Director", "Manager"]
        people = []

        for role in roles:
            query = f'site:linkedin.com/in "{name}" "{role}"'
            links = google_search(query)

            for link in links:
                if "linkedin.com/in" in link:
                    people.append({
                        "LinkedIn": link,
                        "Role": role
                    })

            time.sleep(1)

        return list({p["LinkedIn"]: p for p in people}.values())


# ================= UI =================
st.set_page_config(page_title="OSINT Finder", layout="wide")

st.title("🔍 OSINT LinkedIn Finder (Working Version)")

company_input = st.text_input("Enter Company Name or URL")

if st.button("Run Scan"):
    if not company_input:
        st.error("Enter input")
    else:
        engine = OSINTEngine()

        with st.spinner("Running..."):

            company = engine.enrich_company(company_input)
            name = company["Name"]
            domain = company["Domain"]

            cleaned_domain = clean_domain(domain)

            # STEP 1: ROWS
            linkedin_url = engine.get_linkedin_from_rows(cleaned_domain)

            # STEP 2: BACKUP
            if not linkedin_url:
                st.warning("Rows failed → Trying backup")
                linkedin_url = engine.find_company_linkedin(name, cleaned_domain)

            # STEP 3: PEOPLE
            if linkedin_url:
                st.success("LinkedIn Found")
                people = engine.find_people(name)
            else:
                st.warning("No LinkedIn → fallback people search")
                people = engine.find_people(name)

        # OUTPUT
        st.subheader("Company Info")
        st.write(f"**Name:** {name}")
        st.write(f"**Domain:** {domain}")
        st.write(f"**LinkedIn:** {linkedin_url}")

        st.subheader("Decision Makers")

        df = pd.DataFrame(people)

        if not df.empty:
            st.dataframe(df)
        else:
            st.warning("No people found")
