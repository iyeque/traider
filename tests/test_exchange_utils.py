import unittest
import sys
import os
from unittest.mock import patch, MagicMock

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.exchange_utils import (
    get_symbol_info_sync,
    get_min_notional_sync,
    format_quantity_sync
)

class TestExchangeUtils(unittest.TestCase):
    
    def setUp(self):
        # Setup mock data for testing
        self.mock_symbol_info = {
            'baseAssetPrecision': 8,
            'quoteAssetPrecision': 8,
            'filters': [
                {
                    'filterType': 'LOT_SIZE',
                    'minQty': '0.00100000',
                    'maxQty': '9000.00000000',
                    'stepSize': '0.00100000'
                },
                {
                    'filterType': 'MIN_NOTIONAL',
                    'minNotional': '10.00000000'
                }
            ]
        }
        self.mock_client = MagicMock()
    
    @patch('backtest.exchange_utils.logging')
    def test_get_symbol_info_sync(self, mock_logging):
        """Test retrieving symbol information synchronously."""
        # Setup mock client response
        self.mock_client.get_exchange_info.return_value = {
            'symbols': [
                {'symbol': 'BTCUSDT', 'baseAssetPrecision': 8, 'quoteAssetPrecision': 8, 
                 'filters': [{'filterType': 'LOT_SIZE'}, {'filterType': 'MIN_NOTIONAL'}]}
            ]
        }
        
        # Test successful retrieval
        result = get_symbol_info_sync(self.mock_client, 'BTCUSDT')
        self.assertEqual(result['symbol'], 'BTCUSDT')
        self.mock_client.get_exchange_info.assert_called_once()
        
        # Test symbol not found
        self.mock_client.get_exchange_info.reset_mock()
        result = get_symbol_info_sync(self.mock_client, 'NONEXISTENT')
        self.assertEqual(result, {})
        mock_logging.error.assert_called_once()
        
        # Test exception handling
        self.mock_client.get_exchange_info.reset_mock()
        mock_logging.error.reset_mock()
        self.mock_client.get_exchange_info.side_effect = Exception('Test error')
        result = get_symbol_info_sync(self.mock_client, 'BTCUSDT')
        self.assertEqual(result, {})
        mock_logging.error.assert_called_once()
    
    @patch('backtest.exchange_utils.get_symbol_info_sync')
    @patch('backtest.exchange_utils.logging')
    def test_get_min_notional_sync(self, mock_logging, mock_get_symbol_info):
        """Test retrieving minimum notional value synchronously."""
        # Test successful retrieval
        mock_get_symbol_info.return_value = self.mock_symbol_info
        result = get_min_notional_sync(self.mock_client, 'BTCUSDT')
        self.assertEqual(result, 10.0)
        
        # Test with empty symbol_info
        mock_get_symbol_info.return_value = {}
        result = get_min_notional_sync(self.mock_client, 'BTCUSDT')
        self.assertEqual(result, 10.0)  # Default value
        mock_logging.warning.assert_called_once()
        
        # Test with missing MIN_NOTIONAL filter
        mock_logging.warning.reset_mock()
        mock_get_symbol_info.return_value = {
            'filters': [
                {'filterType': 'LOT_SIZE'}
            ]
        }
        result = get_min_notional_sync(self.mock_client, 'BTCUSDT')
        self.assertEqual(result, 10.0)  # Default value
        mock_logging.warning.assert_called_once()
        
        # Test exception handling
        mock_logging.warning.reset_mock()
        mock_logging.error.reset_mock()
        mock_get_symbol_info.side_effect = Exception('Test error')
        result = get_min_notional_sync(self.mock_client, 'BTCUSDT')
        self.assertEqual(result, 10.0)  # Default value
        mock_logging.error.assert_called_once()
    
    @patch('backtest.exchange_utils.get_symbol_info_sync')
    @patch('backtest.exchange_utils.logging')
    def test_format_quantity_sync(self, mock_logging, mock_get_symbol_info):
        """Test formatting quantity synchronously."""
        # Test successful formatting
        mock_get_symbol_info.return_value = self.mock_symbol_info
        result = format_quantity_sync(self.mock_client, 'BTCUSDT', 1.23456789)
        self.assertEqual(result, 1.234)
        
        # Test with empty symbol_info
        mock_get_symbol_info.return_value = {}
        result = format_quantity_sync(self.mock_client, 'BTCUSDT', 1.23456789)
        self.assertEqual(result, 1.23456789)  # Rounded to 8 decimal places
        mock_logging.warning.assert_called_once()
        
        # Test with missing LOT_SIZE filter
        mock_logging.warning.reset_mock()
        mock_get_symbol_info.return_value = {
            'filters': [
                {'filterType': 'MIN_NOTIONAL'}
            ]
        }
        result = format_quantity_sync(self.mock_client, 'BTCUSDT', 1.23456789)
        self.assertEqual(result, 1.23456789)  # Rounded to 8 decimal places
        mock_logging.warning.assert_called_once()
        
        # Test exception handling
        mock_logging.warning.reset_mock()
        mock_logging.error.reset_mock()
        mock_get_symbol_info.side_effect = Exception('Test error')
        result = format_quantity_sync(self.mock_client, 'BTCUSDT', 1.23456789)
        self.assertEqual(result, 1.23456789)  # Rounded to 8 decimal places
        mock_logging.error.assert_called_once()

if __name__ == '__main__':
    unittest.main()