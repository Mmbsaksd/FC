import os
import sys
import time
import logging
from datetime import datetime, timezone

# Ensure workspace root is first in sys.path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from scripts.run_scanner import run_market_scan
from app.config.scheduler import ScanScheduler

import signal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

running = True
is_scanning = False

def handle_exit(signum, frame):
    global running
    logging.info(f"Received shutdown signal ({signum}). Gracefully stopping scanner daemon...")
    running = False

signal.signal(signal.SIGINT, handle_exit)
try:
    signal.signal(signal.SIGTERM, handle_exit)
except Exception:
    pass

def main():
    global is_scanning
    scheduler = ScanScheduler()
    print("=" * 60)
    print(" CONTINUOUS AI MARKET SCANNER DAEMON ")
    print(" Press Ctrl+C to stop ")
    print("=" * 60)

    while running:
        if not is_scanning:
            try:
                is_scanning = True
                run_market_scan()
            except Exception as e:
                logging.error(f"Error during scan loop: {e}")
            finally:
                is_scanning = False
        
        minutes = scheduler.get_scan_interval_minutes()
        interval_seconds = max(10, minutes * 60)
        print(f"\nSleeping for {minutes}m (Configured Interval)... Next scan scheduled in {minutes}m.")
        
        # Sleep in small increments for fast shutdown response
        for _ in range(int(interval_seconds)):
            if not running:
                break
            time.sleep(1)

    print("\nScanner daemon exited cleanly.")

if __name__ == "__main__":
    main()
