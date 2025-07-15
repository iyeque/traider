from .news_utils import get_news_sentiment
from .rss_utils import get_rss_sentiment
import logging
import requests # Added for Fear & Greed Index fetching
from .trading_stats import LiveTradingStats
from textblob import TextBlob

def analyze_text_sentiment(text: str) -> float:
    """
    Analyzes the sentiment of a given text using TextBlob.
    """
    return TextBlob(text).sentiment.polarity




def is_market_safe(min_sentiment: float, min_fear_greed: int) -> bool:
    """
    Checks if the market conditions are safe based on sentiment analysis and social signals.
    Fallbacks to RSS-based sentiment if NewsAPI fails.
    """

    # Try NewsAPI first
    sentiment = get_news_sentiment("bitcoin OR crypto OR rugpull")

    # Fallback to RSS if NewsAPI fails or returns 0
    if sentiment == 0:
        logging.warning("⚠️ NewsAPI returned no sentiment — falling back to RSS...")
        sentiment = get_rss_sentiment("https://nitter.net/WatcherGuru/rss")

    # Get social confidence via CryptoCompare and Alternative.me
    # Fetch Fear & Greed Index directly
    fear_greed = 50 # Default value
    try:
        fg_url = 'https://api.alternative.me/fng/'
        fg_r = requests.get(fg_url)
        fg_r.raise_for_status()
        fg_data = fg_r.json()
        fear_greed = int(fg_data['data'][0]['value'])
    except Exception as e:
        logging.error(f"Error fetching Fear & Greed Index: {e}")

    # Store in central stats
    LiveTradingStats().set_sentiment(sentiment, fear_greed)

    # Display current readings
    logging.info(f"🧠 Final Sentiment Score: {sentiment:.2f}")
    logging.info(f"📊 Fear & Greed Index: {fear_greed}")

    # Apply safety filters
    if sentiment < min_sentiment:
        logging.warning("🚨 Sentiment too bearish — skipping trade.")
        return False

    if fear_greed is None or fear_greed < min_fear_greed:
        logging.warning("🚨 Fear & Greed Index too low — skipping trade.")
        return False

    logging.info("✅ Market sentiment is positive — trade allowed.")
    return True
