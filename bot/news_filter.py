import requests
import os
from dotenv import load_dotenv

load_dotenv()
CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY")

def is_market_safe():
    """
    Checks recent news headlines for negative sentiment.
    Returns False if negative sentiment is detected.
    """
    url = f"https://cryptopanic.com/api/v1/posts/?auth_token={CRYPTOPANIC_API_KEY}&public=true"
    bad_keywords = ['crash', 'hack', 'regulation', 'ban', 'lawsuit', 'dump', 'fud']

    try:
        response = requests.get(url)
        data = response.json()

        for article in data.get("results", []):
            title = article["title"].lower()
            if any(keyword in title for keyword in bad_keywords):
                print(f"🚨 Negative Sentiment Detected: {title}")
                return False
    except Exception as e:
        print("⚠️ Error checking news sentiment:", e)
        return False

    return True
