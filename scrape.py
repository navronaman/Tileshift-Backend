import requests
import json
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random

input_query = "California Fires"

# Number of valid news links required
REQUIRED_NEWS_LINKS = 20
MAX_PAGES = 5  # Page limit before stopping

# Extract Google search links
def get_google_search_links(query):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")  # Running in headless mode
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("user-data-dir=C:/Users/Dhruv/AppData/Local/Google/Chrome/User Data")
    options.add_argument("--profile-directory=Default")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    driver.get("https://www.google.com/")
    
    time.sleep(random.uniform(5, 8))

    search_box = driver.find_element(By.NAME, "q")

    for letter in query:
        search_box.send_keys(letter)
        time.sleep(random.uniform(0.2, 0.4))

    time.sleep(random.uniform(3, 6))
    search_box.send_keys(Keys.RETURN)

    time.sleep(random.uniform(4, 7))

    search_links = set()
    pages_checked = 0

    while len(search_links) < REQUIRED_NEWS_LINKS and pages_checked < MAX_PAGES:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(4, 7))

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@href, 'http')]"))
            )

            results = driver.find_elements(By.XPATH, "//a[contains(@href, 'http')]")
            
            if not results:
                print("No search results found. Retrying...")
            else:
                for result in results:
                    url = result.get_attribute("href")
                    if url and "google.com" not in url:
                        search_links.add(url)

        except Exception as e:
            print(f"Error extracting links: {e}")

        print(f"\nExtracted {len(search_links)} links so far (before filtering):")
        for link in search_links:
            print(link)

        if len(search_links) >= REQUIRED_NEWS_LINKS:
            break

        try:
            next_button = driver.find_element(By.ID, "pnnext")
            next_button.click()
            pages_checked += 1
            time.sleep(random.uniform(4, 8))
        except:
            break  

    driver.quit()

    print(f"\nExtracted {len(search_links)} valid news links:")
    for link in search_links:
        print(link)

    return list(search_links)


# Function to filter non-news articles
def contains_non_news_keywords(text):
    non_news_keywords = [
        "Advertisement", "Supported by", "Subscribe for $1", "Subscribe now", 
        "Click here to subscribe", "Get Started", "Subscribe", 
        "Download Data", "Precinct Map", "Subscribe", "Sign In", "Read More",
        "Follow NBC News", "Profile", "Sections", "More From", "news Alerts"
    ]
    return any(keyword in text for keyword in non_news_keywords)


# Extract text and headline from articles
def scrape_article(url):
    try:
        print(f"Scraping: {url}")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # **Extract Headline**
        headline = None
        if soup.title:
            headline = soup.title.get_text(strip=True)  # First try the <title> tag
        if not headline:
            h1_tag = soup.find("h1")  # If <title> doesn't work, try <h1>
            if h1_tag:
                headline = h1_tag.get_text(strip=True)

        # If still no headline, use "Unknown Title"
        if not headline:
            headline = "Unknown Title"

        # Extract all paragraphs
        paragraphs = soup.find_all("p")
        article_text = "\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])

        if len(article_text) < 200:
            article_body = soup.find("article")
            if article_body:
                paragraphs = article_body.find_all("p")
                article_text = "\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])

        if contains_non_news_keywords(article_text):
            print(f"\nSkipping {url} - Detected as non-news content.\n")
            return None, None  

        article_text = article_text.split("© 2025")[0]

        if len(article_text) < 100:
            print(f"Skipping article: {url} (too little content)")
            return None, None  

        return headline, article_text.strip()

    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None, None  


# Function to filter valid news links
# Dictionary mapping valid domains to their respective news source names
VALID_NEWS_SOURCES = {
    "cnn.com": "CNN",
    "bbc.com": "BBC",
    "nytimes.com": "New York Times",
    "apnews.com": "Associated Press",
    "reuters.com": "Reuters",
    "foxnews.com": "Fox News",
    "nbcnews.com": "NBC News",
    "aljazeera.com": "Al Jazeera",
    "beforeitsnews.com": "Before It's News",
    "mercola.com": "Mercola",
    "hartmannreport.com": "The Hartmann Report",
    "usafacts.org": "USA Facts",
    "wnd.com": "WND",
    "bnonews.com": "BNO News",
    "theguardian.com": "The Guardian",
    "dailymail.co.uk": "Daily Mail",
    "cbsnews.com": "CBS",
    "usnews.com": "US News",
    "thecooldown.com": "The Cooldown",
    "indiatimes.com": "India Times",
    "cnbc.com": "CNBC",
    "msn.com": "MSN",
    
}

# Function to filter valid news links, automatically adding .gov sources
def filter_valid_news_links(links):
    valid_links = []
    
    for link in links:
        matched = False

        # Check if the link belongs to a known source in VALID_NEWS_SOURCES
        for domain, source_name in VALID_NEWS_SOURCES.items():
            if domain in link:
                valid_links.append({"link": link, "Provider": source_name})
                matched = True
                break  

        # Automatically classify .gov domains
        if not matched and ".gov" in link:
            valid_links.append({"link": link, "Provider": "Official Government Source"})

    return valid_links


# Run the scraping process
if __name__ == "__main__":
    query = input_query

    print("\nStarting Search...\n")
    links = get_google_search_links(query)

    filtered_links = filter_valid_news_links(links)

    scraped_data = []

    print("\nExtracting Articles...\n")
    for news_item in filtered_links:
        link = news_item["link"]
        source = news_item["Provider"]
        headline, article_content = scrape_article(link)

        if article_content:
            news_item["headline"] = headline  
            news_item["content"] = article_content
            scraped_data.append(news_item)

            print(json.dumps(news_item, indent=4))
            print("\n" + "=" * 80 + "\n")

    with open("scraped_news.json", "w", encoding="utf-8") as json_file:
        json.dump(scraped_data, json_file, ensure_ascii=False, indent=4)

    print("Scraped news data saved to scraped_news.json")