#!/usr/bin/env python3
"""
Emergency stop script for the Traider bot.
This script will forcefully terminate any running main.py processes.
"""

import os
import sys
import signal
import subprocess
import time

def find_bot_processes():
    """Find running main.py processes."""
    try:
        if sys.platform == "win32":
            # Windows
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV'], 
                                  capture_output=True, text=True)
            lines = result.stdout.split('\n')
            processes = []
            for line in lines[1:]:  # Skip header
                if 'python.exe' in line and 'main.py' in line:
                    parts = line.split(',')
                    if len(parts) > 1:
                        pid = parts[1].strip('"')
                        processes.append(int(pid))
            return processes
        else:
            # Unix/Linux/Mac
            result = subprocess.run(['pgrep', '-f', 'main.py'], capture_output=True, text=True)
            if result.stdout:
                return [int(pid) for pid in result.stdout.strip().split('\n')]
            return []
    except Exception as e:
        print(f"Error finding processes: {e}")
        return []

def stop_bot():
    """Stop the bot processes."""
    processes = find_bot_processes()
    
    if not processes:
        print("No running bot processes found.")
        return
    
    print(f"Found {len(processes)} bot process(es): {processes}")
    
    for pid in processes:
        try:
            if sys.platform == "win32":
                # Windows
                subprocess.run(['taskkill', '/PID', str(pid), '/F'], check=True)
                print(f"Stopped process {pid}")
            else:
                # Unix/Linux/Mac
                os.kill(pid, signal.SIGTERM)
                print(f"Sent SIGTERM to process {pid}")
                time.sleep(2)
                try:
                    os.kill(pid, signal.SIGKILL)
                    print(f"Force killed process {pid}")
                except ProcessLookupError:
                    print(f"Process {pid} already terminated")
        except Exception as e:
            print(f"Error stopping process {pid}: {e}")
    
    print("Bot stop completed.")

if __name__ == "__main__":
    print("Traider Bot Emergency Stop")
    print("=" * 30)
    stop_bot()
