from bot.news_utils import get_news_sentiment
from bot.lunarcrush_utils import get_galaxy_score

def is_market_safe(min_sentiment=0.1, min_galaxy_score=65):
    sentiment = get_news_sentiment("bitcoin OR crypto OR rugpull")
    galaxy = get_galaxy_score()

    print(f"🧠 News Sentiment Score: {sentiment:.2f}")
    print(f"🌌 LunarCrush Galaxy Score: {galaxy}")

    if sentiment < min_sentiment:
        print("🚨 News sentiment too bearish — skipping trade.")
        return False

    if galaxy < min_galaxy_score:
        print("🚨 Social metrics weak — skipping trade.")
        return False

    print("✅ Market sentiment is positive — trade allowed.")
    return True
