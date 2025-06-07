# bot/lunarcrush_utils.py
import os
import requests

def get_galaxy_score(symbol="BTC"):
    key = os.getenv("LUNARCRUSH_KEY")
    url = f"https://api.lunarcrush.com/v2?data=assets&key={key}&symbol={symbol}"

    try:
        r = requests.get(url)
        score = r.json()["data"][0]["galaxy_score"]
        print(f"🌌 LunarCrush Galaxy Score: {score}")
        return score
    except:
        print("LunarCrush API error.")
        return 50  # Neutral fallback
