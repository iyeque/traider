import unittest
from bot.strategy import generate_signal

class TestStrategy(unittest.TestCase):
    def test_generate_signal_basic(self):
        # Example test: should return a signal for valid input
        signal = generate_signal(
            price=50000,
            atr=200,
            rsi=55,
            sentiment=0.2,
            bb_upper=51000,
            bb_lower=49000,
            params={
                'ATR_TREND_THRESHOLD': 150,
                'BREAKOUT_RR_RATIO': 2.0,
                'sentiment_threshold_positive': 0.1,
                'sentiment_threshold_negative': -0.1,
                'base_rsi_oversold': 30,
                'base_rsi_overbought': 70,
                'use_bollinger_bands': True
            }
        )
        self.assertIn(signal, ['buy', 'sell', 'hold'])

if __name__ == '__main__':
    unittest.main()
