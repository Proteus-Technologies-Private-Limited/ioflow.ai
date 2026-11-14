"""
Run all pricing and billing tests
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import argparse
from datetime import datetime

# Import all test modules
from test_pricing_models import TestPricingModels
from test_cost_calculator import TestCostCalculator
from test_pricing_api import TestPricingAPI
from test_billing_api import TestBillingAPI
from test_pricing_integration import TestPricingIntegration
from test_razorpay_service import TestRazorpayService
from test_billing_service import TestBillingService


def run_all_tests(verbose=2):
    """Run all pricing tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test cases
    test_cases = [
        TestPricingModels,
        TestCostCalculator,
        TestRazorpayService,
        TestBillingService,
        TestPricingAPI,
        TestBillingAPI,
        TestPricingIntegration
    ]
    
    for test_case in test_cases:
        tests = loader.loadTestsFromTestCase(test_case)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=verbose)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def run_specific_test(test_name, verbose=2):
    """Run a specific test module"""
    test_mapping = {
        'models': TestPricingModels,
        'calculator': TestCostCalculator,
        'razorpay': TestRazorpayService,
        'billing': TestBillingService,
        'pricing-api': TestPricingAPI,
        'billing-api': TestBillingAPI,
        'integration': TestPricingIntegration
    }
    
    if test_name not in test_mapping:
        print(f"Unknown test: {test_name}")
        print(f"Available tests: {', '.join(test_mapping.keys())}")
        return False
    
    # Create test suite for specific test
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(test_mapping[test_name])
    
    # Run test
    runner = unittest.TextTestRunner(verbosity=verbose)
    result = runner.run(suite)
    
    return result.wasSuccessful()


def setup_test_data():
    """Set up test data using the setup script"""
    try:
        from setup_test_data import TestDataSetup
        setup = TestDataSetup()
        test_ids = setup.setup_all()
        return True
    except Exception as e:
        print(f"Error setting up test data: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Run pricing and billing tests')
    parser.add_argument(
        'test',
        nargs='?',
        default='all',
        choices=['all', 'models', 'calculator', 'razorpay', 'billing', 'pricing-api', 'billing-api', 'integration', 'setup'],
        help='Which test to run (default: all)'
    )
    parser.add_argument(
        '-v', '--verbose',
        type=int,
        default=2,
        choices=[0, 1, 2],
        help='Verbosity level (0=quiet, 1=normal, 2=verbose)'
    )
    parser.add_argument(
        '--with-setup',
        action='store_true',
        help='Set up test data before running tests'
    )
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"IOFlow Pricing System Test Runner")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # Set up test data if requested
    if args.with_setup or args.test == 'setup':
        print("Setting up test data...")
        if setup_test_data():
            print("✓ Test data setup completed\n")
        else:
            print("✗ Test data setup failed\n")
            if args.test == 'setup':
                return
    
    # Run tests
    if args.test == 'setup':
        # Already handled above
        return
    elif args.test == 'all':
        print("Running all pricing tests...\n")
        success = run_all_tests(args.verbose)
    else:
        print(f"Running {args.test} tests...\n")
        success = run_specific_test(args.test, args.verbose)
    
    # Print summary
    print(f"\n{'='*60}")
    if success:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()