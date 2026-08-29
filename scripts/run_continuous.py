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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    print("=" * 60)
    print(" CONTINUOUS AI MARKET SCANNER DAEMON ")
    print(" Press Ctrl+C to stop ")
    print("=" * 60)
    
    interval_seconds = 900 # 15 minutes

    while True:
        try:
            run_market_scan()
        except Exception as e:
            logging.error(f"Error during scan loop: {e}")
        
        print(f"\nSleeping for 15 minutes... Next scan at {datetime.now(timezone.utc)}")
        time.sleep(interval_seconds)

if __name__ == "__main__":
    main()
