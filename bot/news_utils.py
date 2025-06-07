import os
import requests
from textblob import TextBlob

def get_news_sentiment(query="bitcoin OR crypto", max_articles=10):
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        print("❌ NEWSAPI_KEY not found in .env")
        return 0

    url = (
        f"https://newsapi.org/v2/everything?q={query}"
        f"&language=en&sortBy=publishedAt&pageSize={max_articles}&apiKey={api_key}"
    )

    try:
        r = requests.get(url)
        r.raise_for_status()
        headlines = [article["title"] for article in r.json().get("articles", [])]
        if not headlines:
            print("⚠️ No headlines returned.")
            return 0
        score = sum(TextBlob(h).sentiment.polarity for h in headlines) # type: ignore
        avg_score = score / len(headlines)
        print(f"📰 Avg News Sentiment Score: {avg_score:.2f}")
        return avg_score

    except Exception as e:
        print(f"❌ NewsAPI Error: {e}")
        return 0
