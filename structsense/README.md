# StructSense: Building Health Monitoring

Web app with a Python backend. It works on laptop and phone, and uses **machine learning** (Isolation Forest) and **image processing** (OpenCV).

## Run it (5 minutes)
1. Install Python 3.10 or newer from python.org.
2. Open a terminal in this folder and run:
   ```
   python -m venv venv
   venv\Scripts\activate          (Windows)   |   source venv/bin/activate   (Mac/Linux)
   pip install -r requirements.txt
   python app.py
   ```
3. The terminal prints two addresses:
   - **Laptop:** http://localhost:8000
   - **Phone:** the second address, for example http://192.168.1.5:8000. The phone must be on the **same Wi-Fi**. If it does not open, allow Python through your laptop firewall.
4. Open the page, press **Create a new account**, and sign in. The page loads React from the internet, so you need to be online the first time.

## Put it online (Render, free)
1. Create a free account on github.com, press **New repository**, name it `structsense`, and create it.
2. Open the extracted `structsense` folder. Select **everything inside it** (not the folder itself) and drag it into the GitHub page that says "uploading an existing file". Then press **Commit changes**. `render.yaml` must sit at the top level of the repository.
3. Create a free account on render.com. Press **New + → Blueprint**, connect your GitHub, choose the `structsense` repository, and press **Apply**.
4. Wait 5 to 10 minutes for the first build. Render then gives you a link like `https://structsense-xxxx.onrender.com`. It works on any laptop or phone.
5. The free plan sleeps after 15 minutes without visitors, so the first page load after that takes about a minute. The database also resets when it restarts, so you must create your account again. This is fine for a demo.

## Try the features
- **Accounts:** sign up with just an email and a password. No role to choose. Your crack reports and your crack-photo alerts are saved in **your own account**, and other users cannot see them.
- **Dashboard:** live health score, sensor map and charts. Readings are simulated by the server every 2 seconds.
- **Crack analysis:** run `python make_test_image.py`, then upload `crack_test.jpg` (or a wall photo; on a phone it opens the camera). Choose the part of the structure (wall, column, beam, slab, foundation) and press **Analyse photo**. You get:
  - the cracks found by the ML model, measured by OpenCV (length, width, direction),
  - a **repair simulation**: drag the slider to see the wall before and after the crack is filled,
  - a short **"What to do"** guide: priority, likely cause, repair steps, and a deformation warning if the tilt or strain sensors are high,
  - a **structure diagram** showing which part of the building the crack is in, and what that part does,
  - your report saved under **My crack reports**.
- **Alerts and History:** as before. History has date filters and CSV export.
- **Real sensors (ESP32/Arduino):**
  ```
  curl -X POST http://localhost:8000/api/readings -H "X-API-Key: device-demo-key" -H "Content-Type: application/json" -d "{\"building\":0,\"vib\":1.2,\"tilt\":0.1,\"crack\":0.3,\"strain\":190,\"temp\":27}"
  ```

## How it works (for your viva)
**Machine learning, Isolation Forest.** The model learns from normal readings only. Random trees split the data, and unusual readings get isolated in fewer splits, so they score low. We add two engineered features (the largest and the total z-score) because one extreme sensor among five normal ones is otherwise hard to isolate. About 2 to 3 percent of normal readings are flagged, which is the price of catching real spikes. Endpoint `POST /api/ml/retrain?b=0` retrains it on stored normal data.

**Crack ML model (`crackml.py`).** The photo is cut into 64x64 patches. For each patch we compute 23 numbers (brightness, strength of thin dark lines, edge strength, how aligned the edges are, shape of the dark pixels). A **Random Forest** (150 trees) says "crack" or "no crack" for every patch, which gives a crack probability map.

**Image processing (`vision.py`, OpenCV).**
1. Shrink the photo, then the ML model builds the probability map.
2. Black-hat morphology highlights thin dark lines. Only long thin shapes that sit inside patches the ML trusts are kept, so stains, shadows and pores are dropped.
3. A skeleton gives the crack length, a distance transform gives the width, and `fitLine` gives the direction.
4. Pixels convert to millimetres using your scale. Width above 1.0 mm is Major, 0.3 to 1.0 mm is Minor, below 0.3 mm is Hairline.
5. `cv2.inpaint` paints the crack out to make the "after repair" picture.

**Repair guide (`advice.py`).** Rule-based text chosen from the crack severity, direction and the part of the structure. Columns and foundations get a higher priority. If the tilt, strain or crack-width sensor is above its warning level, a deformation warning is added.

**How accurate is the crack model? (be honest in your viva)** The shipped model was trained on **generated (synthetic) patches**, because real crack photos could not be downloaded when it was built. It scores about **98% on its own test patches** and about **76% on a deliberately harder test set** (faint cracks, noisy surfaces). That is NOT proof it works as well on real photos. To get a properly validated model, download a real dataset such as *Concrete Crack Images for Classification* (Kaggle or Mendeley, folders `Positive` and `Negative`) and run:
```
python crackml.py --real path\to\Positive path\to\Negative
```
It trains on your real photos, prints the accuracy on 20% held-out photos, and saves a new `crack_model.joblib` that the app uses automatically. Restart the app afterwards.

**Health score.** Each sensor scores 100 at rest, falling to 0 at its critical limit. The score is a weighted average: vibration 25%, tilt 25%, crack width 20%, strain 20%, temperature 10%.

## Files
- `app.py` API, login, simulator, alerts, history
- `ml.py` Isolation Forest for sensor anomalies
- `crackml.py` Random Forest crack model and training script
- `crack_model.joblib` the saved crack model (retrained automatically if it cannot be loaded)
- `vision.py` OpenCV crack measurement and repair simulation
- `advice.py` repair guidance text
- `static/index.html` the React web app

## Limits to be honest about
- Sensor data is **simulated**. State this in your report.
- Crack sizes are only as accurate as the scale you enter (lengths are estimates). Thresholds are examples, not engineering standards.
- Accounts use only an email and a password. There is **no email verification or password reset**, because that needs an email service (SMTP). Passwords are stored hashed.
- The repair advice is general guidance, not an engineering report. A photo cannot measure leaning or bending.
- Set `SECRET_KEY` and `DEVICE_KEY` environment variables before sharing the app. The built-in Flask server is for demos, not production.
