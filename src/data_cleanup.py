import pandas as pd
import requests
import re
import unicodedata
from bs4 import BeautifulSoup
import time

def rename(text):
    # Normalize all the accented characters to get correct links
    # é → e, ™ → tm, ® → r
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'\s+', '-', text.strip())
    text = re.sub(r'-+', '-', text)
    return text

def make_url(brand, name):
    return f"https://incidecoder.com/products/{rename(brand)}-{rename(name)}"

def scrape_ingredients(url):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    if r.status_code == 404:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    
    # Each ingredient is an <a class="ingred-link ..."> tag
    ingredient_tags = soup.select("a.ingred-link")
    
    if not ingredient_tags:
        return None
    
    ingredients = [tag.get_text(strip=True) for tag in ingredient_tags]
    return ", ".join(ingredients)

df = pd.read_csv("../data/raw/cosmetics.csv")

bad_mask = df['Ingredients'].str.contains('Visit the|No Info|#NAME?', regex=True, na=False)

review_log = []

for idx, row in df[bad_mask].iterrows():
    url = make_url(row['Brand'], row['Name'])
    ingredients = scrape_ingredients(url)

    if ingredients:
        df.at[idx, 'Ingredients'] = ingredients
        print(f"{row['Name']} printed correctly.")
    else:
        review_log.append({**row, 'tried_url': url})
        print(f"{row['Name']} needs manual check.")
    time.sleep(2)

df.to_csv("../data/interim/cleaned_cosmetics.csv", index=False)
pd.DataFrame(review_log).to_csv("../data/interim/manual_review.csv", index=False)