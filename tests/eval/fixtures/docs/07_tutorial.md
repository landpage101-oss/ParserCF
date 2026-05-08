# Building a Web Scraper with Python

A practical step-by-step guide to fetching and parsing web pages using the
Python standard library and a lightweight HTML parser.

## Prerequisites

Basic familiarity with Python 3.10+ and the `requests` library is assumed.
You will also need `beautifulsoup4` installed in your virtual environment.

## Step 1: Set Up Your Environment

Create an isolated virtual environment to keep dependencies contained.

### Installing Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install requests beautifulsoup4
```

All subsequent commands assume the virtual environment is active.

## Step 2: Fetch a Page

Use `requests.get()` to retrieve the HTML source of a target URL.

### Handling Timeouts and Retries

Always specify a timeout to avoid hanging indefinitely:

```python
import requests

response = requests.get(
    "https://example.com/data",
    timeout=10,
    headers={"User-Agent": "scraper/1.0"},
)
response.raise_for_status()
html = response.text
```

### Respecting robots.txt

Check `robots.txt` before scraping any domain. The `urllib.robotparser`
module in the standard library handles this with no extra dependencies.

## Step 3: Parse the Content

Pass the HTML string to `BeautifulSoup` and select elements with CSS selectors.

### Finding Structured Data

```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(html, "html.parser")
articles = soup.select("article.post")
for article in articles:
    title = article.select_one("h2.title").get_text(strip=True)
    link = article.select_one("a")["href"]
    print(title, link)
```

#### Handling Missing Elements

Wrap element access in a guard to avoid `AttributeError` on pages that
do not always include every field:

```python
title_el = article.select_one("h2.title")
title = title_el.get_text(strip=True) if title_el else "Unknown"
```

## Step 4: Persist the Results

Write extracted records to a CSV file for downstream analysis.

```python
import csv

with open("results.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["title", "url"])
    writer.writeheader()
    for row in records:
        writer.writerow(row)
```

## Summary

A minimal scraper follows four steps: environment setup, HTTP fetch,
HTML parsing, and persistence. Add rate-limiting (`time.sleep`) and
error handling before running against any production site.
