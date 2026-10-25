"""Simulate an IoT device (ESP32/Arduino/Raspberry Pi) sending live sensor data to StructSense.

Usage examples:
  python simulate_iot.py                   # Sends 10 normal sensor readings
  python simulate_iot.py --loop            # Streams live readings every 2 seconds
  python simulate_iot.py --spike vib       # Injects a severe vibration spike (earthquake/heavy machinery)
  python simulate_iot.py --spike tilt      # Injects an abnormal structural tilt
  python simulate_iot.py --spike strain    # Injects an excessive beam strain
  python simulate_iot.py --spike ml        # Injects an unusual multi-sensor pattern to trigger ML Isolation Forest
"""
import argparse
import json
import random
import sys
import time
import urllib.request
import urllib.error

DEFAULT_URL = "http://localhost:8000/api/readings"
DEFAULT_KEY = "device-demo-key"


def send_reading(url, key, building, vib, tilt, crack, strain, temp):
    payload = {
        "building": building,
        "vib": round(vib, 3),
        "tilt": round(tilt, 3),
        "crack": round(crack, 3),
        "strain": round(strain, 1),
        "temp": round(temp, 1),
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "X-API-Key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            print(f"[{time.strftime('%H:%M:%S')}] Sent building {building}: vib={vib:.2f} tilt={tilt:.2f} crack={crack:.2f} strain={strain:.0f} temp={temp:.1f} -> HTTP {status}")
            return True
    except urllib.error.URLError as e:
        print(f"[{time.strftime('%H:%M:%S')}] Failed to send reading: {e}")
        print("  --> Is StructSense running? Start it first with run.bat or python run.py")
        return False


def main():
    parser = argparse.ArgumentParser(description="StructSense IoT Device Simulator")
    parser.add_argument("--url", default=DEFAULT_URL, help="Target API endpoint")
    parser.add_argument("--key", default=DEFAULT_KEY, help="X-API-Key device token")
    parser.add_argument("--building", type=int, default=0, choices=[0, 1, 2], help="Building index (0: Skyline Tower A, 1: Harbor Heights B, 2: Civic Plaza C)")
    parser.add_argument("--loop", action="store_true", help="Continuously send readings every 2 seconds")
    parser.add_argument("--spike", choices=["vib", "tilt", "crack", "strain", "ml", "all"], help="Simulate a sensor spike / structural anomaly")
    args = parser.parse_args()

    print("=" * 60)
    print("  StructSense - IoT Device Simulator (ESP32 / Sensor Node)")
    print(f"  Target: {args.url} (Building {args.building})")
    print("=" * 60)

    # Base normal readings
    vib = 1.1 + random.uniform(-0.15, 0.15)
    tilt = 0.12 + random.uniform(-0.02, 0.02)
    crack = 0.30 + random.uniform(-0.03, 0.03)
    strain = 180.0 + random.uniform(-10.0, 10.0)
    temp = 27.0 + random.uniform(-0.5, 0.5)

    if args.spike:
        print(f"\n[!] INJECTING ANOMALY: {args.spike.upper()}\n")
        if args.spike == "vib":
            vib = 6.8  # Critical (> 5.0 mm/s)
        elif args.spike == "tilt":
            tilt = 1.3  # Critical (> 1.0 deg)
        elif args.spike == "crack":
            crack = 1.8  # Critical (> 1.5 mm)
        elif args.spike == "strain":
            strain = 650.0  # Critical (> 600 ue)
        elif args.spike == "ml":
            # Odd combination that triggers Isolation Forest without crossing critical thresholds
            vib = 2.8
            tilt = 0.45
            crack = 0.75
            strain = 380.0
        elif args.spike == "all":
            vib = 7.2
            tilt = 1.5
            crack = 2.0
            strain = 700.0

        send_reading(args.url, args.key, args.building, vib, tilt, crack, strain, temp)
        print("\nSpike sent! Check the StructSense dashboard and alerts tab to see the live alert.")
        return

    # Normal streaming
    count = 0
    while True:
        # Subtle drift
        vib = max(0.2, vib + random.uniform(-0.1, 0.1))
        tilt = max(0.01, tilt + random.uniform(-0.01, 0.01))
        crack = max(0.05, crack + random.uniform(-0.02, 0.02))
        strain = max(50.0, strain + random.uniform(-5.0, 5.0))
        temp = max(15.0, temp + random.uniform(-0.2, 0.2))

        ok = send_reading(args.url, args.key, args.building, vib, tilt, crack, strain, temp)
        if not ok and not args.loop:
            sys.exit(1)

        count += 1
        if not args.loop and count >= 5:
            print(f"\nFinished sending {count} sample readings.")
            print("Tip: Run with '--loop' for continuous streaming, or '--spike vib' to trigger an alert.")
            break
        time.sleep(2)


if __name__ == "__main__":
    main()
