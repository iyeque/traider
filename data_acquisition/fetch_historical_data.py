import os
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
import logging
import sys
import feedparser
from dotenv import load_dotenv

# Add bot directory to sys.path to import sentiment_engine
sys.path.append(os.path.join(os.path.dirname(__file__), '..')) # Add project root to path
from bot.sentiment_engine import analyze_text_sentiment

load_dotenv() # Load environment variables

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_cryptopanic_news(api_key: str, page: int = 1, filter_currency: str = 'BTC', public_only: bool = True) -> list:
    """
    Fetches news from CryptoPanic API.
    Note: Free tier usually limits historical data to 20 items.
    """
    url = "https://cryptopanic.com/api/v1/posts/"
    params = {
        'auth_token': api_key,
        'currencies': filter_currency,
        'public': 'true' if public_only else 'false',
        'page': page
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status() # Raise an exception for HTTP errors
        return response.json().get('results', [])
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching CryptoPanic news: {e}")
        return []

def fetch_newsapi_news(api_key: str, query: str = 'cryptocurrency', language: str = 'en', from_date: str = None, to_date: str = None) -> list:
    """
    Fetches news from NewsAPI.
    Note: Free tier usually limits historical data to 30 days.
    """
    url = "https://newsapi.org/v2/everything"
    params = {
        'q': query,
        'language': language,
        'apiKey': api_key,
        'sortBy': 'relevancy',
        'from': from_date,
        'to': to_date
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status() # Raise an exception for HTTP errors
        return response.json().get('articles', [])
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching NewsAPI news: {e}")
        return []

def fetch_rss_feed(url: str) -> list:
    """
    Fetches and parses an RSS feed.
    """
    try:
        feed = feedparser.parse(url)
        return feed.entries
    except Exception as e:
        logging.error(f"Error fetching RSS feed from {url}: {e}")
        return []

def process_articles_for_sentiment(articles: list, source_type: str) -> pd.DataFrame:
    """
    Processes a list of articles (from various sources) to extract sentiment.
    """
    sentiments = []
    for article in articles:
        title = ""
        published_at = None

        if source_type == 'cryptopanic':
            title = article.get('title', '')
            published_at = article.get('published_at')
        elif source_type == 'newsapi':
            title = article.get('title', '')
            published_at = article.get('publishedAt')
        elif source_type == 'rss':
            title = article.get('title', '')
            published_at = article.get('published')
        
        if title and published_at:
            sentiment_score = analyze_text_sentiment(title) # Use your existing sentiment analyzer
            sentiments.append({
                'timestamp': pd.to_datetime(published_at, utc=True),
                'sentiment_score': sentiment_score,
                'source': source_type
            })
    return pd.DataFrame(sentiments)

def aggregate_hourly_sentiment(sentiment_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates sentiment scores to an hourly average.
    """
    if sentiment_df.empty:
        return pd.DataFrame(columns=['timestamp', 'sentiment_score'])
    
    sentiment_df['timestamp'] = pd.to_datetime(sentiment_df['timestamp'])
    sentiment_df = sentiment_df.set_index('timestamp')
    # Resample to hourly and take the mean sentiment
    hourly_sentiment = sentiment_df['sentiment_score'].resample('1h').mean().reset_index()
    hourly_sentiment.rename(columns={'timestamp': 'timestamp', 'sentiment_score': 'sentiment_score'}, inplace=True)
    return hourly_sentiment

def main(output_csv: str = 'historical_sentiment.csv', days_to_fetch: int = 30):
    cryptopanic_api_key = os.getenv("CRYPTOPANIC_API_KEY")
    newsapi_key = os.getenv("NEWSAPI_KEY")
    
    # Example RSS Feeds - Add/Remove as needed
    rss_feeds = [
        "https://cointelegraph.com/rss",
        "https://www.coindesk.com/feed/"
    ]

    all_processed_sentiments = []

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days_to_fetch)

    # Ensure start_date is timezone-aware (UTC)
    start_date = start_date.replace(tzinfo=timezone.utc)

    # --- Fetch from CryptoPanic ---
    if cryptopanic_api_key:
        logging.info(f"Fetching CryptoPanic news for last {days_to_fetch} days...")
        logging.warning("CryptoPanic free tier is limited to 20 most recent articles. For extensive historical data, consider a paid plan.")
        cryptopanic_articles = []
        page = 1
        while True:
            news = fetch_cryptopanic_news(cryptopanic_api_key, page=page)
            if not news:
                break
            cryptopanic_articles.extend(news)
            logging.info(f"Fetched CryptoPanic page {page} with {len(news)} articles.")
            page += 1
            time.sleep(1) # Respect rate limits
        all_processed_sentiments.append(process_articles_for_sentiment(cryptopanic_articles, 'cryptopanic'))
    else:
        logging.warning("CRYPTOPANIC_API_KEY not found. Skipping CryptoPanic news fetch.")

    # --- Fetch from NewsAPI ---
    if newsapi_key:
        logging.info(f"Fetching NewsAPI news for last {days_to_fetch} days...")
        newsapi_articles = fetch_newsapi_news(
            newsapi_key,
            from_date=start_date.strftime('%Y-%m-%d'),
            to_date=end_date.strftime('%Y-%m-%d')
        )
        logging.info(f"Fetched {len(newsapi_articles)} articles from NewsAPI.")
        all_processed_sentiments.append(process_articles_for_sentiment(newsapi_articles, 'newsapi'))
    else:
        logging.warning("NEWSAPI_KEY not found. Skipping NewsAPI news fetch.")

    # --- Fetch from RSS Feeds ---
    logging.info("Fetching RSS feed news...")
    for rss_url in rss_feeds:
        rss_articles = fetch_rss_feed(rss_url)
        logging.info(f"Fetched {len(rss_articles)} articles from {rss_url}.")
        all_processed_sentiments.append(process_articles_for_sentiment(rss_articles, 'rss'))
        time.sleep(0.5) # Be respectful

    # Combine all sentiments
    if not all_processed_sentiments:
        logging.error("No sentiment data fetched from any source. Exiting.")
        return

    combined_sentiment_df = pd.concat(all_processed_sentiments, ignore_index=True)
    
    # Filter by date range after fetching to ensure we get all relevant data
    combined_sentiment_df = combined_sentiment_df[(combined_sentiment_df['timestamp'] >= start_date) & (combined_sentiment_df['timestamp'] <= end_date)]

    hourly_sentiment_df = aggregate_hourly_sentiment(combined_sentiment_df)
    
    # Ensure output directory exists
    output_dir = "data_acquisition"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_csv)

    hourly_sentiment_df.to_csv(output_path, index=False)
    logging.info(f"Combined historical sentiment data saved to {output_path}")

if __name__ == "__main__":
    main()
