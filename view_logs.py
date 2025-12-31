"""
Log Viewer - View bot server logs in real-time
"""
import os
import time
from pathlib import Path
from datetime import datetime

LOG_DIR = Path(__file__).parent / "logs"

def get_latest_log_file():
    """Get the most recent log file"""
    if not LOG_DIR.exists():
        return None
    
    log_files = list(LOG_DIR.glob("bot_server_*.log"))
    if not log_files:
        return None
    
    # Return the most recent log file
    return max(log_files, key=os.path.getmtime)

def view_logs(tail_lines=50, follow=False):
    """View log file contents"""
    log_file = get_latest_log_file()
    
    if not log_file:
        print("No log files found. Start the server first.")
        return
    
    print(f"Viewing log file: {log_file}")
    print(f"{'='*60}\n")
    
    if follow:
        # Follow mode - show last N lines and then tail
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                # Read last N lines
                lines = f.readlines()
                if len(lines) > tail_lines:
                    print("".join(lines[-tail_lines:]))
                else:
                    print("".join(lines))
                
                # Follow new lines
                print("\n--- Following new log entries (Ctrl+C to stop) ---\n")
                while True:
                    line = f.readline()
                    if line:
                        print(line, end='')
                    else:
                        time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\nStopped following logs.")
    else:
        # Just show last N lines
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if len(lines) > tail_lines:
                    print("".join(lines[-tail_lines:]))
                else:
                    print("".join(lines))
        except Exception as e:
            print(f"Error reading log file: {e}")

if __name__ == '__main__':
    import sys
    
    follow = '--follow' in sys.argv or '-f' in sys.argv
    tail = 50
    
    # Check for --tail argument
    if '--tail' in sys.argv:
        idx = sys.argv.index('--tail')
        if idx + 1 < len(sys.argv):
            try:
                tail = int(sys.argv[idx + 1])
            except ValueError:
                pass
    
    view_logs(tail_lines=tail, follow=follow)


