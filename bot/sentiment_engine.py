from bot.news_utils import get_news_sentiment
from bot.rss_utils import get_rss_sentiment
from bot.lunarcrush_utils import get_galaxy_score

def is_market_safe(min_sentiment: float = 0.1, min_galaxy_score: int = 65) -> bool:
    """
    Checks if the market conditions are safe based on sentiment analysis and social signals.
    Fallbacks to RSS-based sentiment if NewsAPI fails.
    """

    # Try NewsAPI first
    sentiment = get_news_sentiment("bitcoin OR crypto OR rugpull")

    # Fallback to RSS if NewsAPI fails or returns 0
    if sentiment == 0:
        print("⚠️ NewsAPI returned no sentiment — falling back to RSS...")
        rss_url = "https://nitter.net/WatcherGuru/rss"  # You can rotate between trusted sources
        sentiment = get_rss_sentiment(rss_url)

    # Get social confidence via LunarCrush
    galaxy = get_galaxy_score()

    # Display current readings
    print(f"🧠 Final Sentiment Score: {sentiment:.2f}")
    print(f"🌌 LunarCrush Galaxy Score: {galaxy}")

    # Apply safety filters
    if sentiment < min_sentiment:
        print("🚨 Sentiment too bearish — skipping trade.")
        return False

    if galaxy < min_galaxy_score:
        print("🚨 Social metrics weak — skipping trade.")
        return False

    print("✅ Market sentiment is positive — trade allowed.")
    return True
