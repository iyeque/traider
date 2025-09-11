#!/usr/bin/env python3

import unittest
import sys
import os
import argparse

def run_tests(test_pattern=None, verbose=False):
    """Run the test suite with optional pattern matching and verbosity.
    
    Args:
        test_pattern: Optional pattern to filter test cases
        verbose: Whether to show verbose output
    
    Returns:
        True if all tests pass, False otherwise
    """
    # Discover and load all tests in the tests directory
    loader = unittest.TestLoader()
    if test_pattern:
        suite = loader.loadTestsFromName(f'tests.{test_pattern}')
    else:
        start_dir = os.path.join(os.path.dirname(__file__), 'tests')
        suite = loader.discover(start_dir)
    
    # Run the tests
    verbosity = 2 if verbose else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    # Return True if successful, False otherwise
    return result.wasSuccessful()

def main():
    """Parse command line arguments and run tests."""
    parser = argparse.ArgumentParser(description='Run Traider test suite')
    parser.add_argument('-p', '--pattern', help='Pattern to filter test cases (e.g., test_config)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show verbose output')
    args = parser.parse_args()
    
    success = run_tests(args.pattern, args.verbose)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()