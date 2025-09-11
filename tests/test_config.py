import unittest
import os
import sys
import logging
from unittest.mock import patch, MagicMock

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the Config class and config instance
from config import Config, config

class TestConfig(unittest.TestCase):
    """Test suite for the Config class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Reset the Config singleton instance for each test
        Config._instance = None
        # Store original environment variables
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Clean up after each test."""
        # Restore original environment variables
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def test_singleton_pattern(self):
        """Test that Config implements the singleton pattern correctly."""
        config1 = Config()
        config2 = Config()
        self.assertIs(config1, config2, "Config should implement singleton pattern")
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        test_config = Config()
        self.assertEqual(test_config.get('TRADE_SYMBOL'), 'BTCUSDT')
        self.assertEqual(test_config.get('INTERVAL'), '15m')
        self.assertEqual(test_config.get('TRADE_INTERVAL_SECONDS'), 900)
        self.assertEqual(test_config.get('RISK_PER_TRADE_PERCENT'), 1.0)
    
    def test_environment_override(self):
        """Test that environment variables override default values."""
        # Set environment variables
        os.environ['TRADE_SYMBOL'] = 'ETHUSDT'
        os.environ['INTERVAL'] = '5m'
        os.environ['TRADE_INTERVAL_SECONDS'] = '300'
        os.environ['RISK_PER_TRADE_PERCENT'] = '2.5'
        
        # Create a new Config instance
        test_config = Config()
        
        # Check that environment values are used
        self.assertEqual(test_config.get('TRADE_SYMBOL'), 'ETHUSDT')
        self.assertEqual(test_config.get('INTERVAL'), '5m')
        self.assertEqual(test_config.get('TRADE_INTERVAL_SECONDS'), 300)
        self.assertEqual(test_config.get('RISK_PER_TRADE_PERCENT'), 2.5)
    
    def test_type_conversion(self):
        """Test that type conversion methods work correctly."""
        # Set environment variables with string values
        os.environ['GRID_LEVELS'] = '5'
        os.environ['GRID_STEP_PERCENT'] = '1.5'
        os.environ['USE_BOLLINGER_BANDS'] = 'true'
        
        # Create a new Config instance
        test_config = Config()
        
        # Test integer conversion
        self.assertEqual(test_config.get_int('GRID_LEVELS'), 5)
        self.assertIsInstance(test_config.get_int('GRID_LEVELS'), int)
        
        # Test float conversion
        self.assertEqual(test_config.get_float('GRID_STEP_PERCENT'), 1.5)
        self.assertIsInstance(test_config.get_float('GRID_STEP_PERCENT'), float)
        
        # Test boolean conversion
        self.assertEqual(test_config.get_bool('USE_BOLLINGER_BANDS'), True)
        self.assertIsInstance(test_config.get_bool('USE_BOLLINGER_BANDS'), bool)
    
    def test_nonexistent_key(self):
        """Test behavior when accessing a nonexistent key."""
        test_config = Config()
        # Default value should be returned for nonexistent key
        self.assertIsNone(test_config.get('NONEXISTENT_KEY'))
        # Custom default value should be returned
        self.assertEqual(test_config.get('NONEXISTENT_KEY', 'default'), 'default')
    
    def test_set_value(self):
        """Test setting a configuration value."""
        test_config = Config()
        test_config.set('NEW_KEY', 'new_value')
        self.assertEqual(test_config.get('NEW_KEY'), 'new_value')
        
        # Override existing value
        test_config.set('TRADE_SYMBOL', 'DOGEUSDT')
        self.assertEqual(test_config.get('TRADE_SYMBOL'), 'DOGEUSDT')
    
    @patch('logging.basicConfig')
    def test_logging_configuration(self, mock_logging_config):
        """Test that logging is configured correctly."""
        os.environ['LOG_LEVEL'] = 'DEBUG'
        test_config = Config()
        
        # Check that logging.basicConfig was called with the right level
        mock_logging_config.assert_called_once()
        call_args = mock_logging_config.call_args[1]
        self.assertEqual(call_args['level'], logging.DEBUG)
    
    def test_get_list(self):
        """Test the get_list method."""
        # Set the value directly instead of using environment variables
        test_config = Config()
        test_config.set('TEST_LIST', 'item1,item2,item3')
        
        # Test list conversion from comma-separated string
        self.assertEqual(test_config.get_list('TEST_LIST'), ['item1', 'item2', 'item3'])
        
        # Test with default value
        self.assertEqual(test_config.get_list('NONEXISTENT_LIST', ['default']), ['default'])
        
        # Test with non-string, non-list value
        test_config.set('NUMBER_VALUE', 42)
        self.assertEqual(test_config.get_list('NUMBER_VALUE'), [42])

if __name__ == '__main__':
    unittest.main()