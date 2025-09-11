import unittest
from bot.strategy import generate_signal

class TestStrategy(unittest.TestCase):
    def test_generate_signal_basic(self):
        # Test case 1: Basic buy signal
        signal = generate_signal(
            rsi=25, macd=0.5, macd_signal=0.4,
            sentiment=0.2, sentiment_threshold_positive=0.1, sentiment_threshold_negative=-0.1,
            base_rsi_oversold=30, base_rsi_overbought=70,
            use_bollinger_bands=False, bb_bbl=None, bb_bbh=None, current_close=100.0
        )
        self.assertEqual(signal, 'buy')

        # Test case 2: Basic sell signal
        signal = generate_signal(
            rsi=75, macd=-0.5, macd_signal=-0.4,
            sentiment=-0.2, sentiment_threshold_positive=0.1, sentiment_threshold_negative=-0.1,
            base_rsi_oversold=30, base_rsi_overbought=70,
            use_bollinger_bands=False, bb_bbl=None, bb_bbh=None, current_close=100.0
        )
        self.assertEqual(signal, 'sell')

        # Test case 3: No signal
        signal = generate_signal(
            rsi=50, macd=0.1, macd_signal=0.1,
            sentiment=0.0, sentiment_threshold_positive=0.1, sentiment_threshold_negative=-0.1,
            base_rsi_oversold=30, base_rsi_overbought=70,
            use_bollinger_bands=False, bb_bbl=None, bb_bbh=None, current_close=100.0
        )
        self.assertIsNone(signal)

if __name__ == '__main__':
    unittest.main()
