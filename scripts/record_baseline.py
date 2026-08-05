import sys
import sqlite3
import subprocess

def run_baseline():
    print(f"Python Version: {sys.version}")
    print(f"SQLite Version: {sqlite3.sqlite_version}")
    
    print("\nRunning pytest...")
    # Run pytest and capture output
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/"], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
        
if __name__ == "__main__":
    run_baseline()
