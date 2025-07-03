from bot.news_utils import get_news_sentiment
from bot.rss_utils import get_rss_sentiment
from bot.social_utils import get_social_sentiment
from bot.trading_stats import LiveTradingStats

def is_market_safe(min_sentiment: float = 0.1, min_fear_greed: int = 50) -> bool:
    """
    Checks if the market conditions are safe based on sentiment analysis and social signals.
    Fallbacks to RSS-based sentiment if NewsAPI fails.
    """

    # Try NewsAPI first
    sentiment = get_news_sentiment("bitcoin OR crypto OR rugpull")

    # Fallback to RSS if NewsAPI fails or returns 0
    if sentiment == 0:
        print("⚠️ NewsAPI returned no sentiment — falling back to RSS...")
        sentiment = get_rss_sentiment("https://nitter.net/WatcherGuru/rss")

    # Get social confidence via CryptoCompare and Alternative.me
    social_data = get_social_sentiment()
    fear_greed = social_data.get('fear_greed_index', 50)

    # Store in central stats
    LiveTradingStats().set_sentiment(sentiment, fear_greed)

    # Display current readings
    print(f"🧠 Final Sentiment Score: {sentiment:.2f}")
    print(f"📊 Fear & Greed Index: {fear_greed}")

    # Apply safety filters
    if sentiment < min_sentiment:
        print("🚨 Sentiment too bearish — skipping trade.")
        return False

    if fear_greed is None or fear_greed < min_fear_greed:
        print("🚨 Fear & Greed Index too low — skipping trade.")
        return False

    print("✅ Market sentiment is positive — trade allowed.")
    return True
