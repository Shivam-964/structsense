"""StructSense Root Launcher.
Run this script from anywhere to start StructSense and open your browser:
    python run.py
"""
import os
import sys
import threading
import time
import webbrowser

# Ensure we run from the structsense directory
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(ROOT_DIR, "structsense")

if os.path.exists(APP_DIR):
    os.chdir(APP_DIR)
    sys.path.insert(0, APP_DIR)
else:
    sys.path.insert(0, ROOT_DIR)

import app


def open_browser(port):
    time.sleep(1.2)
    url = f"http://localhost:{port}"
    print(f"Opening {url} in your default browser...")
    try:
        webbrowser.open(url)
    except Exception:
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    app.boot()
    print(f"\n  =======================================================")
    print(f"   StructSense - Structural Health Monitoring System")
    print(f"  =======================================================")
    print(f"  Local Laptop:  http://localhost:{port}")
    print(f"  Mobile Device: http://{app.lan_ip()}:{port}")
    print(f"  Demo Account:  admin@structsense.com / admin123")
    print(f"  =======================================================\n")
    app.app.run(host="0.0.0.0", port=port, threaded=True)
