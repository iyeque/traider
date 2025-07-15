import pandas as pd

def load_historical_sentiment(csv_file: str) -> pd.DataFrame:
    """
    Loads historical sentiment data from a CSV file and sets the timestamp as the index.
    """
    df = pd.read_csv(csv_file)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)
    return df