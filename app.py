import streamlit as st
import requests
from bs4 import BeautifulSoup
import time


# -------- BING SEARCH --------
def bing_search(query):
    url = "https://www.bing.com/search"
    headers = {"User-Agent": "Mozilla/5.0"}
    params = {"q": query}

    res = requests.get(url, headers=headers, params=params)
    soup = BeautifulSoup(res.text, "html.parser")

    links = []
    for a in soup.select("li.b_algo h2 a"):
        href = a.get("href")
        if href:
            links.append(href)

    return links


# -------- FIND PEOPLE --------
def find_decision_makers(company_name):
    roles = ["CEO", "Founder", "Owner", "Director", "Manager"]
    results = []

    for role in roles:
        query = f'site:linkedin.com/in "{company_name}" "{role}"'
        links = bing_search(query)

        for link in links:
            if "linkedin.com/in" in link:
                results.append({
                    "Role": role,
                    "LinkedIn": link
                })

        time.sleep(1)

    return list({p["LinkedIn"]: p for p in results}.values())


# ================= UI =================
st.set_page_config(page_title="OSINT Finder", layout="wide")

st.title("🔍 OSINT LinkedIn Finder (Working with Rows)")

domain_input = st.text_input("Enter Company Domain (e.g. apple.com)")

if domain_input:
    st.info("👉 Step 1: Open Rows and get LinkedIn company profile")

    rows_url = f"https://rows.com/tools/company-enricher"
    st.markdown(f"[🔗 Open Rows Tool]({rows_url})")

    st.info("👉 Step 2: Copy LinkedIn URL from Rows and paste below")


linkedin_url = st.text_input("Paste LinkedIn Company URL here")

if st.button("Find Decision Makers"):
    if not linkedin_url:
        st.error("Please paste LinkedIn URL from Rows")
    else:
        # Extract company name from URL
        company_name = linkedin_url.split("/company/")[-1].replace("-", " ")

        with st.spinner("Finding decision makers..."):
            people = find_decision_makers(company_name)

        st.subheader("Decision Makers")

        if people:
            st.dataframe(people)
        else:
            st.warning("No people found")
