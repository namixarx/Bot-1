"""
Logging setup for the Telegram Bot Panel
Redirects print statements to both console and log file
"""
import sys
import os
from datetime import datetime
from pathlib import Path

# Create logs directory if it doesn't exist
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Log file with timestamp
LOG_FILE = LOG_DIR / f"bot_server_{datetime.now().strftime('%Y%m%d')}.log"

class TeeOutput:
    """Class to write to both file and console"""
    def __init__(self, *files):
        self.files = files
    
    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()
    
    def flush(self):
        for f in self.files:
            f.flush()

def setup_logging():
    """Setup logging to write to both console and file"""
    # Open log file in append mode
    log_file = open(LOG_FILE, 'a', encoding='utf-8')
    
    # Create TeeOutput to write to both stdout and file
    sys.stdout = TeeOutput(sys.stdout, log_file)
    sys.stderr = TeeOutput(sys.stderr, log_file)
    
    # Write startup message
    print(f"\n{'='*60}")
    print(f"Server started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Log file: {LOG_FILE}")
    print(f"{'='*60}\n")
    
    return log_file

if __name__ == '__main__':
    setup_logging()
    print("Logging setup complete!")


