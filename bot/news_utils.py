import os
import requests
from textblob import TextBlob
import logging

def get_news_sentiment(query: str = "bitcoin OR crypto", max_articles: int = 10) -> float:
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        logging.error("NEWSAPI_KEY not found in .env")
        return 0.0

    url = (
        f"https://newsapi.org/v2/everything?q={query}"
        f"&language=en&sortBy=publishedAt&pageSize={max_articles}&apiKey={api_key}"
    )

    try:
        r = requests.get(url)
        r.raise_for_status()
        headlines = [article["title"] for article in r.json().get("articles", [])]
        if not headlines:
            logging.warning("No headlines returned.")
            return 0.0
        score = sum(TextBlob(h).sentiment.polarity for h in headlines) # type: ignore
        avg_score = score / len(headlines)
        logging.info(f"Avg News Sentiment Score: {avg_score:.2f}")
        return avg_score

    except Exception as e:
        logging.error(f"NewsAPI Error: {e}")
        return 0.0
