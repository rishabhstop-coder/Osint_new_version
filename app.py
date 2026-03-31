import requests
from bs4 import BeautifulSoup

# -------- SEARCH WITHOUT API --------
def google_search(self, query):
    url = "https://html.duckduckgo.com/html/"
    
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    data = {
        "q": query
    }

    response = requests.post(url, headers=headers, data=data)
    soup = BeautifulSoup(response.text, "html.parser")

    results = []

    for result in soup.find_all("div", class_="result"):
        title_tag = result.find("a", class_="result__a")
        snippet_tag = result.find("a", class_="result__snippet")

        title = title_tag.get_text() if title_tag else ""
        link = title_tag["href"] if title_tag else ""
        snippet = snippet_tag.get_text() if snippet_tag else ""

        results.append({
            "title": title,
            "link": link,
            "snippet": snippet
        })

    return results
