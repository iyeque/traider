import requests
import logging

def get_social_sentiment(symbol='BTC'):
    # Only use Alternative.me Fear & Greed Index (free, no API key required)
    try:
        fg_url = 'https://api.alternative.me/fng/'
        fg_r = requests.get(fg_url)
        fg_r.raise_for_status()
        fg_data = fg_r.json()
        fear_greed = int(fg_data['data'][0]['value'])
    except Exception as e:
        logging.error(f"Alternative.me FNG API Error: {str(e)}")
        fear_greed = None

    return {
        'fear_greed_index': fear_greed
    } 