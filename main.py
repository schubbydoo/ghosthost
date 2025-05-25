#!/usr/bin/env python3
"""
Ghost Host Main Application
==========================
Main entry point for the Ghost Host animatronic system.
"""

import sys
import signal
import logging
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.core.config_manager import config
from src.core.event_handler import EventHandler

# Global event handler instance for cleanup
event_handler = None

def setup_logging():
    """Setup logging configuration"""
    log_config = config.get('logging', {})
    log_level = log_config.get('level', 'INFO')
    log_file = log_config.get('file', 'logs/ghosthost.log')
    
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Logging configured")
    return logger

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signum}, shutting down...")
    
    if event_handler:
        event_handler.cleanup()
    
    logger.info("Ghost Host shutdown complete")
    sys.exit(0)

def main():
    """Main application entry point"""
    global event_handler
    
    # Setup logging
    logger = setup_logging()
    logger.info("Starting Ghost Host application")
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize event handler (this sets up all hardware)
        logger.info("Initializing hardware systems...")
        event_handler = EventHandler(config)
        
        # Flash eyes to indicate system ready
        event_handler.led_controller.flash_eyes(3, 0.2)
        
        logger.info("Ghost Host system ready! Waiting for sensor triggers...")
        logger.info("Press Ctrl+C to shutdown")
        
        # Main loop - just keep the application running
        # All functionality is event-driven through the sensor manager
        while True:
            time.sleep(1)
            
            # Optional: log system status periodically
            # This could be helpful for debugging
            # status = event_handler.get_system_status()
            # logger.debug(f"System status: {status}")
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}")
        
    finally:
        # Cleanup
        if event_handler:
            event_handler.cleanup()
        
        logger.info("Ghost Host application ended")

if __name__ == "__main__":
    main() 