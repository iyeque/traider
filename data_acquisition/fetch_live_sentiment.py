import os
import requests
import logging
import feedparser
from typing import Dict, Any, Optional, Tuple
from textblob import TextBlob

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _extract_polarity(text: Any) -> float:
    """
    Safely extract polarity from TextBlob.sentiment with typing-friendly access.
    Returns 0.0 on any failure.
    """
    try:
        sentiment: Any = TextBlob(str(text)).sentiment  # sentiment is a NamedTuple at runtime
        polarity_val = getattr(sentiment, "polarity", 0.0)
        return float(polarity_val)
    except Exception:
        return 0.0

def fetch_cryptopanic_sentiment() -> float:
    """
    Fetches real-time sentiment from CryptoPanic API.
    Returns a sentiment score between -1.0 and 1.0.
    """
    api_key = os.getenv("CRYPTOPANIC_API_KEY")
    if not api_key:
        logging.error("CRYPTOPANIC_API_KEY not found in .env")
        return 0.0

    url = "https://cryptopanic.com/api/v1/posts/"
    params = {
        'auth_token': api_key,
        'currencies': 'BTC',  # Focus on Bitcoin news
        'public': 'true',
        'page': 1
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        news_items = response.json().get('results', [])
        
        if not news_items:
            logging.warning("No news items returned from CryptoPanic API.")
            return 0.0
        
        # Calculate sentiment from news titles
        sentiments = []
        for item in news_items:
            title = item.get('title', '')
            if title:
                sentiments.append(_extract_polarity(title))
        
        if not sentiments:
            return 0.0
            
        avg_sentiment = sum(sentiments) / len(sentiments)
        logging.info(f"CryptoPanic Sentiment Score: {avg_sentiment:.2f}")
        return avg_sentiment

    except Exception as e:
        logging.error(f"CryptoPanic API Error: {e}")
        return 0.0

def fetch_newsapi_sentiment(query: str = "bitcoin OR crypto", max_articles: int = 10) -> float:
    """
    Fetches real-time sentiment from NewsAPI.
    Returns a sentiment score between -1.0 and 1.0.
    """
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
            logging.warning("No headlines returned from NewsAPI.")
            return 0.0
            
        sentiments = [_extract_polarity(h) for h in headlines]
        avg_score = sum(sentiments) / len(sentiments)
        logging.info(f"NewsAPI Sentiment Score: {avg_score:.2f}")
        return avg_score

    except Exception as e:
        logging.error(f"NewsAPI Error: {e}")
        return 0.0

def fetch_rss_sentiment(feed_url: str, max_items: int = 10) -> float:
    """
    Fetches real-time sentiment from an RSS feed.
    Returns a sentiment score between -1.0 and 1.0.
    """
    try:
        # Add headers to avoid bot detection
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Fetch the feed with headers
        response = requests.get(feed_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse the feed content
        feed = feedparser.parse(response.content)
        
        # Check if feed parsing was successful
        if feed.bozo:
            logging.warning(f"RSS feed parsing issues for {feed_url}: {feed.bozo_exception}")
        
        entries = feed.entries[:max_items]
        headlines = [entry.title for entry in entries if hasattr(entry, "title") and entry.title]

        if not headlines:
            logging.warning(f"No headlines found in RSS feed: {feed_url} (entries: {len(entries)}, feed status: {feed.status})")
            return 0.0

        sentiments = [_extract_polarity(title) for title in headlines]
        avg_score = sum(sentiments) / len(sentiments)
        logging.info(f"RSS Sentiment Score from {feed_url}: {avg_score:.2f}")
        return avg_score

    except Exception as e:
        logging.error(f"RSS feed error for {feed_url}: {e}")
        return 0.0

def fetch_fear_greed_index() -> int:
    """
    Fetches the current Fear & Greed Index.
    Returns a value between 0 (extreme fear) and 100 (extreme greed).
    """
    try:
        fg_url = 'https://api.alternative.me/fng/'
        fg_r = requests.get(fg_url)
        fg_r.raise_for_status()
        fg_data = fg_r.json()
        fear_greed = int(fg_data['data'][0]['value'])
        logging.info(f"Fear & Greed Index: {fear_greed}")
        return fear_greed
    except Exception as e:
        logging.error(f"Error fetching Fear & Greed Index: {e}")
        return 50  # Default neutral value

def get_live_sentiment() -> Tuple[float, int]:
    """
    Fetches and aggregates live sentiment from multiple sources.
    Returns a tuple of (sentiment_score, fear_greed_index).
    """
    sentiments = []
    
    # Try CryptoPanic first
    cryptopanic_sentiment = fetch_cryptopanic_sentiment()
    if cryptopanic_sentiment != 0.0:
        sentiments.append(cryptopanic_sentiment)
        logging.info(f"CryptoPanic sentiment: {cryptopanic_sentiment:.3f}")
    else:
        logging.info("CryptoPanic failed or returned neutral, trying NewsAPI...")
    
    # Always try NewsAPI as backup/enhancement
    newsapi_sentiment = fetch_newsapi_sentiment()
    if newsapi_sentiment != 0.0:
        sentiments.append(newsapi_sentiment)
        logging.info(f"NewsAPI sentiment: {newsapi_sentiment:.3f}")
    
    # If we have few/no sentiments, try RSS feeds for additional data
    if len(sentiments) < 2:
        logging.info("Trying RSS feeds for additional sentiment data...")
        rss_feeds = [
            "https://cointelegraph.com/rss",
            "https://www.coindesk.com/arc/outboundfeeds/rss/?outputType=xml",
            "https://feeds.feedburner.com/CoinDesk",
            "https://bitcoinmagazine.com/feed"
        ]
        
        for feed_url in rss_feeds:
            score = fetch_rss_sentiment(feed_url)
            if score != 0.0:
                sentiments.append(score)
                logging.info(f"RSS sentiment from {feed_url}: {score:.3f}")
    
    # Calculate final sentiment
    if sentiments:
        sentiment = sum(sentiments) / len(sentiments)
        logging.info(f"Aggregated sentiment from {len(sentiments)} sources: {sentiment:.3f}")
    else:
        sentiment = 0.0
        logging.warning("No sentiment data available from any source")
    
    # Get Fear & Greed Index
    fear_greed = fetch_fear_greed_index()
    
    return sentiment, fear_greed

# For testing
if __name__ == "__main__":
    sentiment, fear_greed = get_live_sentiment()
    print(f"Final Sentiment Score: {sentiment:.2f}")
    print(f"Fear & Greed Index: {fear_greed}")