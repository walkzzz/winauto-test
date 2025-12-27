#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify the enhanced find_control function
"""

import logging
import time
from winauto_helper import WinAuto

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(name)s %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

def test_find_control():
    """Test the enhanced find_control function"""
    logger.info("=== Starting find_control test ===")
    
    # Create WinAuto instance
    winauto = WinAuto(r"D:\Program Files\CBIM\modulelogin.exe")
    
    # Start the application
    app = winauto.start()
    if not app:
        logger.error("Failed to start application")
        return False
    
    # Give application time to start
    time.sleep(2)
    
    try:
        # Get the login window
        login_window = winauto.get_window(class_name='LoginDialog')
        if not login_window:
            logger.error("Failed to get login window")
            return False
        
        logger.info("=== Test 1: Exact match with default depth ===")
        # Test 1: Exact match with default depth
        login_btn = winauto.find_control(
            login_window,
            title='登 录',
            control_type='Button',
            enable_debug_log=True
        )
        if login_btn:
            logger.info("✓ Test 1 passed: Found login button with exact match")
        else:
            logger.error("✗ Test 1 failed: Could not find login button")
        
        logger.info("=== Test 2: Fuzzy match ===")
        # Test 2: Fuzzy match
        login_btn_fuzzy = winauto.find_control(
            login_window,
            title='登录',  # Partial match
            control_type='Button',
            match_strategy='fuzzy',
            enable_debug_log=True
        )
        if login_btn_fuzzy:
            logger.info("✓ Test 2 passed: Found login button with fuzzy match")
        else:
            logger.error("✗ Test 2 failed: Could not find login button with fuzzy match")
        
        logger.info("=== Test 3: Best match with multiple candidates ===")
        # Test 3: Best match with multiple candidates
        edit_control = winauto.find_control(
            login_window,
            class_name='Edit',
            best_match=True,
            enable_debug_log=True
        )
        if edit_control:
            logger.info("✓ Test 3 passed: Found best matching Edit control")
        else:
            logger.error("✗ Test 3 failed: Could not find best matching Edit control")
        
        logger.info("=== Test 4: Adaptive depth ===")
        # Test 4: Adaptive depth (start with low depth, should automatically increase)
        deep_control = winauto.find_control(
            login_window,
            class_name='Edit',
            depth=2,  # Start with low depth
            adaptive_depth=True,
            enable_debug_log=True
        )
        if deep_control:
            logger.info("✓ Test 4 passed: Found control with adaptive depth")
        else:
            logger.error("✗ Test 4 failed: Could not find control with adaptive depth")
        
        logger.info("=== Test 5: Regex match ===")
        # Test 5: Regex match
        login_btn_regex = winauto.find_control(
            login_window,
            title=r'.*登.*录.*',
            control_type='Button',
            match_strategy='regex',
            enable_debug_log=True
        )
        if login_btn_regex:
            logger.info("✓ Test 5 passed: Found login button with regex match")
        else:
            logger.error("✗ Test 5 failed: Could not find login button with regex match")
        
        logger.info("=== All tests completed ===")
        return True
        
    finally:
        # Close the application
        winauto.close_app()

if __name__ == "__main__":
    test_find_control()