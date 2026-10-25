# 🏢 StructSense: Structural Health Monitoring & AI Crack Detection

**StructSense** is a full-stack IoT and AI-powered structural health monitoring platform designed to inspect building integrity in real-time. It combines **IoT sensor telemetry**, **Isolation Forest machine learning anomaly detection**, and **OpenCV + Random Forest computer vision** for automated crack inspection and repair simulations.

---

## 🚀 Quick Start (1 Click)

### On Windows:
Simply **double-click** [`run.bat`](file:///c:/Users/SHIVAM/Downloads/structsensen/run.bat) (or run `run.ps1` in PowerShell).

### From Terminal / Command Prompt:
```powershell
python run.py
```

StructSense will start immediately and automatically open your default web browser to:
👉 **`http://localhost:8000`**

### Mobile Access (Same Wi-Fi):
StructSense displays your local network IP upon starting (e.g., `http://192.168.x.x:8000`). Open this link on your phone to inspect the dashboard or take photos directly from your phone camera!

---

## 🔑 Login Credentials

The database is pre-configured with a ready-to-use demo account:

- **Email:** `admin@structsense.com`
- **Password:** `admin123`
- *Or simply click the **"⚡ Quick Demo Sign In"** button on the login screen!*
- You can also register a new personal account anytime; your inspection reports are securely isolated to your account.

---

## 🛠️ Testing the Core Features

### 1. 📊 3D Architectural Digital Twin & Live Dashboard
- **Interactive 3D Digital Twin (Three.js WebGL):** Full 3D architectural building model featuring concrete slabs, load-bearing columns, and translucent curtain walls. Click and drag to rotate 360°, scroll to zoom, and inspect sensor nodes glowing in 3D space with real-time status colors!
- Toggle between **3D Twin** and **2D Blueprint** elevation views with a single click.
- View real-time simulated sensors updating every 2 seconds across 3 buildings: **Skyline Tower A**, **Harbor Heights B**, and **Civic Plaza C**.
- Monitored parameters:
  - **Vibration** ($mm/s$) — dynamic loads, machinery resonance, or seismic vibration.
  - **Tilt** ($^\circ$) — building inclination or foundation settlement.
  - **Crack Width** ($mm$) — real-time linear displacement transducers across existing joints.
  - **Strain** ($\mu\epsilon$) — microstrain on key load-bearing beams and columns.
  - **Temperature** ($^\circ C$) — thermal expansion monitoring.
- **Isolation Forest ML**: Unsupervised anomaly detector flags multi-sensor deviations even before fixed thresholds are exceeded.

### 2. 🔍 AI Crack Detection & Official PDF Engineering Reports
1. Click **Crack Analysis** in the left navigation menu.
2. Select or drag-and-drop any test image from the included [`sample_images/`](file:///c:/Users/SHIVAM/Downloads/structsensen/sample_images) folder:
   - [`crack_test_severe.jpg`](file:///c:/Users/SHIVAM/Downloads/structsensen/sample_images/crack_test_severe.jpg) — Wide branching crack (triggers **Major Crack / High Urgency** alert).
   - [`crack_test_hairline.jpg`](file:///c:/Users/SHIVAM/Downloads/structsensen/sample_images/crack_test_hairline.jpg) — Subtle surface crack (evaluates as **Minor / Hairline**).
   - [`crack_test_diagonal.jpg`](file:///c:/Users/SHIVAM/Downloads/structsensen/sample_images/crack_test_diagonal.jpg) — Diagonal shear pattern.
   - [`concrete_normal.jpg`](file:///c:/Users/SHIVAM/Downloads/structsensen/sample_images/concrete_normal.jpg) — Clean surface with no cracks (tests **False Positive rejection**).
3. Select the structural member (**Wall**, **Column**, **Beam**, **Slab**, or **Foundation**).
4. Click **Analyse photo** to receive:
   - **Precise Measurements:** Total length ($mm$), maximum width ($mm$), average width, coverage percentage, and crack orientation.
   - **Interactive Repair Simulation:** Drag the Before/After slider to visualize the Telea inpainting restoration.
   - **📄 Official PDF Engineering Report Export:** Click the **"Export Official PDF Report"** button to generate a certified, high-resolution forensic inspection certificate formatted for standard A4 printing and instant browser 'Save as PDF'!

### 3. 📈 Multi-Sensor Correlation & Safety Threshold Tuning (Analytics Tab)
- **Multi-Sensor Pearson Correlation Matrix ($5 \times 5$ Heatmap):** Dynamically calculates physical coupling between sensors (e.g. how dynamic vibration couples with column strain).
- **Cross-Building Risk Scoring:** Side-by-side health comparison across all monitored properties.
- **Safety Limit Calibration:** Civil engineers can fine-tune Warning and Critical thresholds dynamically from the web interface.

### 4. 📡 IoT Hardware Simulation (ESP32 / Arduino)
You can simulate external IoT hardware sending real-time sensor packets using the included [`simulate_iot.py`](file:///c:/Users/SHIVAM/Downloads/structsensen/simulate_iot.py) utility:

```powershell
# Send normal continuous readings every 2 seconds
python simulate_iot.py --loop

# Inject a severe vibration spike (e.g. earthquake or shockwave)
python simulate_iot.py --spike vib

# Inject an abnormal structural tilt
python simulate_iot.py --spike tilt

# Inject an unusual combination to trigger the ML Isolation Forest
python simulate_iot.py --spike ml
```

### 4. 📈 History & CSV Export
- Go to the **History** tab to inspect daily minimum, average, and maximum sensor values over the past 30 days.
- Filter by date range and export complete historical telemetry directly to CSV.

---

## 📁 Project Structure

```
structsensen/
├── run.bat                 # 1-Click Windows Batch Launcher
├── run.ps1                 # PowerShell Launcher
├── run.py                  # Python Root Entry Point
├── simulate_iot.py         # IoT Device / Hardware Telemetry Simulator
├── sample_images/          # Ready-to-use sample inspection photos
│   ├── concrete_normal.jpg
│   ├── crack_test_diagonal.jpg
│   ├── crack_test_hairline.jpg
│   └── crack_test_severe.jpg
├── structsense/            # Application Core
│   ├── app.py              # Flask API, SQLite ORM, Auth, Sensor Telemetry
│   ├── static/index.html   # React SPA Dashboard (Tailwind/CSS, Dark Mode)
│   ├── ml.py               # Isolation Forest Anomaly Detection
│   ├── crackml.py          # Random Forest Patch Classifier & Feature Extraction
│   ├── crack_model.joblib  # Pre-trained ML model bundle
│   ├── vision.py           # OpenCV morphological processing, skeleton & inpaint
│   ├── advice.py           # Structural engineering guidance rule engine
│   └── structsense.db      # SQLite Database
├── VIVA_GUIDE.md           # Complete Project Defense & Viva Voce Q&A Guide
└── requirements.txt        # Python Dependencies
```

---

## 🎓 Viva & Presentation Guide
Presenting this project for college, university, or an engineering viva?
Read [`VIVA_GUIDE.md`](file:///c:/Users/SHIVAM/Downloads/structsensen/VIVA_GUIDE.md) for full answers to common examiner questions regarding the ML algorithms, OpenCV pipeline, formulas, limitations, and future enhancements.
