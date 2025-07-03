# bot/rss_utils.py

import feedparser
from textblob import TextBlob
import logging

def get_rss_sentiment(feed_url: str, max_items: int = 10) -> float:
    try:
        feed = feedparser.parse(feed_url)
        entries = feed.entries[:max_items]
        headlines = [entry.title for entry in entries if hasattr(entry, "title")]

        if not headlines:
            logging.warning("No RSS headlines found.")
            return 0.0

        score = sum(TextBlob(title).sentiment.polarity for title in headlines)  # type: ignore
        avg_score = score / len(headlines)
        logging.info(f"RSS Sentiment Score: {avg_score:.2f}")
        return avg_score

    except Exception as e:
        logging.error(f"RSS error: {e}")
        return 0.0
