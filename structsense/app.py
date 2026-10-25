"""StructSense backend: Flask API + simulator + ML + image processing. Serves the web app too."""
import math, os, random, re, socket, sqlite3, threading, time, csv, io
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, Response, g, jsonify, request, send_from_directory
from itsdangerous import URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash
import advice, crackml, json, ml, vision, pdf_report
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'structsense.db')
DEVICE_KEY = os.environ.get('DEVICE_KEY', 'device-demo-key')   # key IoT devices must send
app = Flask(__name__, static_folder='static', static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024               # allow big phone photos
ser = URLSafeTimedSerializer(os.environ.get('SECRET_KEY', 'change-this-secret'))

# base = normal reading, warn/crit = alert limits, off = value that counts as "zero" (for temperature)
SENSORS = {
    'vib':    dict(n='Vibration',   u='mm/s', base=1.1,  warn=3,   crit=5,   off=0),
    'tilt':   dict(n='Tilt',        u='deg',  base=.12,  warn=.5,  crit=1,   off=0),
    'crack':  dict(n='Crack width', u='mm',   base=.3,   warn=.8,  crit=1.5, off=0),
    'strain': dict(n='Strain',      u='ue',   base=180,  warn=400, crit=600, off=0),
    'temp':   dict(n='Temperature', u='C',    base=27,   warn=42,  crit=55,  off=20),
}
BUILDINGS = [dict(n='Skyline Tower A', k=1.0), dict(n='Harbor Heights B', k=1.9), dict(n='Civic Plaza C', k=.8)]
LOCK = threading.Lock()


def mean(s, k):
    """Normal level for a sensor in a building with stress factor k (temperature scales only above 20 C)."""
    return s['off'] + (s['base'] - s['off']) * k

DET = [ml.Detector() for _ in BUILDINGS]
LAST = [{k: mean(s, b['k']) for k, s in SENSORS.items()} for b in BUILDINGS]
PREV = {}   # remembers last status per (building, sensor) so we only alert on changes


def run(sql, args=(), many=False):
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        cur = c.executemany(sql, args) if many else c.execute(sql, args)
        rows = cur.fetchall()
        c.commit()
        return rows
    finally:
        c.close()


def init_db():
    run("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE, name TEXT, role TEXT, pw TEXT)""")
    run("""CREATE TABLE IF NOT EXISTS readings(id INTEGER PRIMARY KEY, ts TEXT, b INTEGER, vib REAL, tilt REAL,
           crack REAL, strain REAL, temp REAL, anomaly INTEGER DEFAULT 0, score REAL DEFAULT 0)""")
    run("CREATE INDEX IF NOT EXISTS ix_r ON readings(b, ts)")
    run("""CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY, ts TEXT, b INTEGER, sensor TEXT, sev TEXT,
           val TEXT, st TEXT DEFAULT 'open')""")
    run("""CREATE TABLE IF NOT EXISTS crack_reports(id INTEGER PRIMARY KEY, ts TEXT, b INTEGER, user TEXT, filename TEXT,
           length_mm REAL, width_mm REAL, coverage REAL, severity TEXT, label TEXT)""")
    # newer columns, added safely so an older structsense.db keeps working
    for table, col, decl in (('alerts', 'user', 'TEXT'), ('alerts', 'notes', 'TEXT'),
                             ('crack_reports', 'location', 'TEXT'), ('crack_reports', 'element', 'TEXT'),
                             ('crack_reports', 'result', 'TEXT'), ('crack_reports', 'notes', 'TEXT')):
        if col not in [r['name'] for r in run(f"PRAGMA table_info({table})")]:
            run(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    # seed default demo user if not present
    if not run("SELECT 1 FROM users WHERE email='admin@structsense.com'"):
        run("INSERT INTO users(email, name, role, pw) VALUES(?,?,?,?)",
            ('admin@structsense.com', 'Admin Engineer', 'Engineer', generate_password_hash('admin123')))


def status(s, v):
    return 'crit' if v >= s['crit'] else 'warn' if v >= s['warn'] else 'ok'


def step(s, prev, k, spikes=True):
    """Next simulated value: drifts back to normal, adds noise, rarely spikes."""
    m = mean(s, k)
    v = prev + (m - prev) * .15 + (random.random() - .5) * (m - s['off']) * .25
    if spikes and random.random() < .006:
        v = s['off'] + (v - s['off']) * (2.2 + random.random() * 2)
    return max(s['off'] * .9, v)


def normal_rows(k, n=1500):
    cur = {key: mean(s, k) for key, s in SENSORS.items()}
    rows = []
    for _ in range(n):
        cur = {key: step(s, cur[key], k, spikes=False) for key, s in SENSORS.items()}
        rows.append([cur[key] for key in ml.KEYS])
    return rows


def seed_history():
    if run("SELECT COUNT(*) c FROM readings")[0]['c']:
        return
    rows, start = [], datetime.now() - timedelta(days=30)
    for bi, b in enumerate(BUILDINGS):
        for i in range(30 * 24):
            vals = []
            for key in ml.KEYS:
                s = SENSORS[key]
                m = mean(s, b['k'])
                v = s['off'] + (m - s['off']) * (1 + .15 * math.sin(i / 9)) + (random.random() - .5) * (m - s['off']) * .25
                if random.random() < .004:
                    v = s['off'] + (v - s['off']) * 2.6
                vals.append(round(v, 3))
            rows.append(((start + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M:%S'), bi, *vals, 0, 0))
    run("INSERT INTO readings(ts,b,vib,tilt,crack,strain,temp,anomaly,score) VALUES(?,?,?,?,?,?,?,?,?)", rows, many=True)


def add_alert(bi, sensor, sev, val, user=None):
    """user=None -> shared alert from the sensors; otherwise only that user sees it (e.g. their crack photo)."""
    run("INSERT INTO alerts(ts,b,sensor,sev,val,user) VALUES(?,?,?,?,?,?)", (datetime.now().isoformat(' ', 'seconds'), bi, sensor, sev, val, user))


def store(bi, vals):
    """Save one reading: run ML, store it, and raise alerts when something changes."""
    with LOCK:
        flag, score = DET[bi].check(vals)
        run("INSERT INTO readings(ts,b,vib,tilt,crack,strain,temp,anomaly,score) VALUES(?,?,?,?,?,?,?,?,?)",
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), bi, *[vals[k] for k in ml.KEYS], int(flag), score))
        LAST[bi] = dict(vals)
        any_bad = False
        for key, s in SENSORS.items():
            st = status(s, vals[key])
            any_bad |= st != 'ok'
            if st != 'ok' and PREV.get((bi, key), 'ok') == 'ok':
                add_alert(bi, s['n'], st, f"{vals[key]:.2f} {s['u']}")
            PREV[(bi, key)] = st
        if flag and not any_bad and not PREV.get((bi, 'ml')):
            add_alert(bi, 'ML check', 'warn', f'score {score:.2f}')
        PREV[(bi, 'ml')] = flag


def simulator():
    while True:
        for bi, b in enumerate(BUILDINGS):
            store(bi, {key: step(s, LAST[bi][key], b['k']) for key, s in SENSORS.items()})
        time.sleep(2)


def train_all():
    for bi, b in enumerate(BUILDINGS):
        DET[bi].train(normal_rows(b['k']))


# ---------- auth ----------
def auth(*roles):
    def deco(f):
        @wraps(f)
        def w(*a, **kw):
            token = request.headers.get('Authorization', '').replace('Bearer ', '') or request.args.get('token', '')
            try:
                g.user = ser.loads(token, max_age=7 * 86400)
            except Exception:
                return jsonify(error='Please sign in again.'), 401
            if roles and g.user['role'] not in roles:
                return jsonify(error='Your role is not allowed to do this.'), 403
            return f(*a, **kw)
        return w
    return deco


def bidx():
    try:
        b = int(request.args.get('b', request.form.get('b', 0)))
    except ValueError:
        b = -1
    if not 0 <= b < len(BUILDINGS):
        raise ValueError('Unknown building.')
    return b


@app.errorhandler(ValueError)
def bad(e):
    return jsonify(error=str(e)), 400


@app.post('/api/register')
def register():
    d = request.get_json(force=True, silent=True) or {}
    email, pw, role = str(d.get('email', '')).strip().lower(), str(d.get('password', '')), 'Engineer'
    if not re.match(r'^\S+@\S+\.\S+$', email): raise ValueError('Enter a valid email address.')
    if len(pw) < 6: raise ValueError('Password must be at least 6 characters.')
    if run("SELECT 1 FROM users WHERE email=?", (email,)):
        return jsonify(error='This email already has an account. Sign in instead.'), 409
    run("INSERT INTO users(email,name,role,pw) VALUES(?,?,?,?)", (email, email.split('@')[0], role, generate_password_hash(pw)))
    return login_ok(email, role)


def login_ok(email, role):
    u = dict(email=email, name=email.split('@')[0], role=role)
    return jsonify(token=ser.dumps(u), user=u)


@app.post('/api/login')
def login():
    d = request.get_json(force=True, silent=True) or {}
    r = run("SELECT * FROM users WHERE email=?", (str(d.get('email', '')).strip().lower(),))
    if not r or not check_password_hash(r[0]['pw'], str(d.get('password', ''))):
        return jsonify(error='Wrong email or password.'), 401
    return login_ok(r[0]['email'], r[0]['role'])


# ---------- live data, alerts ----------
@app.get('/api/live')
@auth()
def live():
    bi = bidx()
    rows = run("SELECT * FROM readings WHERE b=? ORDER BY id DESC LIMIT 40", (bi,))[::-1]
    since = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    n24 = run("SELECT COUNT(*) c FROM readings WHERE b=? AND anomaly=1 AND ts>=?", (bi, since))[0]['c']
    last = rows[-1]
    return jsonify(series={k: [r[k] for r in rows] for k in ml.KEYS},
                   ml=dict(flag=bool(last['anomaly']), score=last['score'], n24=n24, trained_on=DET[bi].n_train))


@app.post('/api/readings')           # for real devices (ESP32/Arduino): send X-API-Key header
def ingest():
    if request.headers.get('X-API-Key') != DEVICE_KEY:
        return jsonify(error='Bad device key.'), 401
    d = request.get_json(force=True, silent=True) or {}
    bi = int(d.get('building', 0))
    if not 0 <= bi < len(BUILDINGS): raise ValueError('Unknown building.')
    try:
        vals = {k: float(d[k]) for k in ml.KEYS}
    except (KeyError, TypeError, ValueError):
        raise ValueError('Send numbers for: ' + ', '.join(ml.KEYS))
    store(bi, vals)
    return jsonify(ok=True)


def fmt_time(ts):
    return ts[11:16] if ts[:10] == datetime.now().strftime('%Y-%m-%d') else ts[:10]


@app.get('/api/alerts')
@auth()
def alerts():
    rows = run("SELECT * FROM alerts WHERE user IS NULL OR user=? ORDER BY id DESC LIMIT 100", (g.user['email'],))
    return jsonify(alerts=[dict(id=r['id'], sensor=r['sensor'], sev=r['sev'], val=r['val'], time=fmt_time(r['ts']),
                                b=BUILDINGS[r['b']]['n'], st=r['st']) for r in rows])


@app.post('/api/alerts/<int:i>/advance')
@auth()
def advance(i):
    run("UPDATE alerts SET st=CASE st WHEN 'open' THEN 'ack' ELSE 'resolved' END WHERE id=? AND (user IS NULL OR user=?)", (i, g.user['email']))
    return jsonify(ok=True)


# ---------- history ----------
def history_rows():
    bi, key = bidx(), request.args.get('sensor', 'vib')
    if key not in SENSORS: raise ValueError('Unknown sensor.')
    try:
        a, z = (datetime.strptime(request.args[x], '%Y-%m-%d').strftime('%Y-%m-%d') for x in ('from', 'to'))
    except (KeyError, ValueError):
        raise ValueError('Dates must look like 2026-10-16.')
    rows = run(f"SELECT date(ts) d, MIN({key}) mn, AVG({key}) av, MAX({key}) mx FROM readings "
               "WHERE b=? AND date(ts)>=? AND date(ts)<=? GROUP BY d ORDER BY d", (bi, a, z))
    return key, [dict(date=r['d'], min=r['mn'], avg=r['av'], max=r['mx']) for r in rows]


@app.get('/api/history')
@auth()
def history():
    return jsonify(rows=history_rows()[1])


@app.get('/api/history.csv')
@auth()
def history_csv():
    key, rows = history_rows()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['date', f"min ({SENSORS[key]['u']})", 'average', 'max'])
    for r in rows: w.writerow([r['date'], round(r['min'], 3), round(r['avg'], 3), round(r['max'], 3)])
    return Response(out.getvalue(), mimetype='text/csv')


# ---------- ML + image processing ----------
@app.post('/api/ml/retrain')
@auth()
def retrain():
    bi = bidx()
    rows = run("SELECT vib,tilt,crack,strain,temp FROM readings WHERE b=? AND anomaly=0 ORDER BY id DESC LIMIT 3000", (bi,))
    if len(rows) < 200: raise ValueError('Not enough normal readings to retrain yet.')
    with LOCK:
        DET[bi].train([list(r) for r in rows])
    return jsonify(ok=True, trained_on=len(rows))


@app.post('/api/crack')
@auth()
def crack():
    f = request.files.get('image')
    if not f: raise ValueError('Choose a photo first.')
    try:
        mm = float(request.form.get('mm_per_px', .25))
    except ValueError:
        mm = .25
    if not .001 <= mm <= 50: raise ValueError('Scale must be between 0.001 and 50 mm per pixel.')
    bi = bidx()
    element = request.form.get('element', 'Wall')
    element = element if element in advice.ELEMENTS else 'Wall'
    location = request.form.get('location', '').strip()[:80]
    res = vision.analyze(f.read(), mm)
    # sensors on this building that are already above their warning level (a hint of deformation)
    flags = [(SENSORS[k]['n'], LAST[bi][k], SENSORS[k]['u'], status(SENSORS[k], LAST[bi][k]))
             for k in ('tilt', 'strain', 'crack') if status(SENSORS[k], LAST[bi][k]) != 'ok']
    res['advice'] = advice.build(res, element, flags)
    res['element'], res['location'], res['filename'] = element, location, f.filename[:80]
    me = g.user['email']
    run("INSERT INTO crack_reports(ts,b,user,filename,length_mm,width_mm,coverage,severity,label,location,element,result) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (datetime.now().isoformat(' ', 'seconds'), bi, me, res['filename'], res['length_mm'], res['max_width_mm'], res['coverage_pct'],
         res['severity'], res['label'], location, element, json.dumps(res)))
    run("DELETE FROM crack_reports WHERE user=? AND id NOT IN (SELECT id FROM crack_reports WHERE user=? ORDER BY id DESC LIMIT 50)", (me, me))
    res['id'] = run("SELECT id FROM crack_reports WHERE user=? ORDER BY id DESC LIMIT 1", (me,))[0]['id']
    if res['severity'] in ('warn', 'crit'):
        add_alert(bi, 'Crack photo', res['severity'], f"{res['max_width_mm']} mm wide", user=me)
    return jsonify(res)


@app.get('/api/crack/reports')
@auth()
def crack_reports():
    """Only the signed-in user's own reports."""
    rows = run("SELECT * FROM crack_reports WHERE user=? ORDER BY id DESC LIMIT 50", (g.user['email'],))
    return jsonify(reports=[dict(id=r['id'], time=r['ts'][:16], b=BUILDINGS[r['b']]['n'], file=r['filename'], length=r['length_mm'],
                                 width=r['width_mm'], severity=r['severity'], label=r['label'], element=r['element'] or '',
                                 location=r['location'] or '') for r in rows])


@app.get('/api/crack/reports/<int:i>')
@auth()
def crack_report(i):
    r = run("SELECT result FROM crack_reports WHERE id=? AND user=?", (i, g.user['email']))
    if not r or not r[0]['result']:
        return jsonify(error='Report not found.'), 404
    out = json.loads(r[0]['result'])
    out['id'] = i
    return jsonify(out)


@app.get('/api/crack/model')
@auth()
def crack_model_info():
    return jsonify(crackml.get_model()[1])


@app.get('/api/crack/reports/<int:i>/report')
@auth()
def crack_report_html(i):
    r = run("SELECT * FROM crack_reports WHERE id=? AND user=?", (i, g.user['email']))
    if not r or not r[0]['result']:
        return jsonify(error='Report not found.'), 404
    res = json.loads(r[0]['result'])
    b_name = BUILDINGS[r[0]['b']]['n'] if 0 <= r[0]['b'] < len(BUILDINGS) else 'Skyline Tower A'
    notes = r[0]['notes'] or ''
    html = pdf_report.generate_report_html(i, res, g.user['email'], b_name, notes)
    return Response(html, mimetype='text/html')


@app.post('/api/crack/reports/<int:i>/notes')
@auth()
def save_report_notes(i):
    d = request.get_json(force=True, silent=True) or {}
    notes = str(d.get('notes', '')).strip()[:1000]
    run("UPDATE crack_reports SET notes=? WHERE id=? AND user=?", (notes, i, g.user['email']))
    return jsonify(ok=True, notes=notes)


@app.get('/api/analytics/overview')
@auth()
def analytics_overview():
    bi = bidx()
    rows = run("SELECT vib, tilt, crack, strain, temp FROM readings WHERE b=? ORDER BY id DESC LIMIT 500", (bi,))
    if len(rows) >= 10:
        mat = np.array([[r[k] for k in ml.KEYS] for r in rows], dtype=float)
        corr_mat = np.corrcoef(mat, rowvar=False)
        corr = {
            ml.KEYS[i]: {ml.KEYS[j]: round(float(corr_mat[i, j]), 2) for j in range(len(ml.KEYS))}
            for i in range(len(ml.KEYS))
        }
    else:
        corr = {k: {k2: 1.0 if k == k2 else 0.0 for k2 in ml.KEYS} for k in ml.KEYS}

    bld_stats = []
    for idx, b in enumerate(BUILDINGS):
        last_r = run("SELECT * FROM readings WHERE b=? ORDER BY id DESC LIMIT 1", (idx,))
        anom_24 = run("SELECT COUNT(*) c FROM readings WHERE b=? AND anomaly=1 AND ts >= datetime('now', '-24 hours')", (idx,))[0]['c']
        open_al = run("SELECT COUNT(*) c FROM alerts WHERE b=? AND st='open'", (idx,))[0]['c']
        score = 88
        if last_r:
            lr = last_r[0]
            s_sum = 0
            for k in ml.KEYS:
                s = SENSORS[k]
                ratio = min(1.0, max(0.0, (lr[k] - s['off']) / (s['crit'] - s['off'])))
                s_sum += s.get('w', 0.2) * (100 - 100 * (ratio ** 2))
            score = max(0, min(100, int(round(s_sum))))
        bld_stats.append(dict(id=idx, name=b['n'], score=score, open_alerts=open_al, anomalies_24h=anom_24))

    crack_summary = run("SELECT element, severity, COUNT(*) c FROM crack_reports GROUP BY element, severity")
    defects = {}
    for r in crack_summary:
        el = r['element'] or 'Wall'
        defects.setdefault(el, {'none': 0, 'ok': 0, 'warn': 0, 'crit': 0})
        defects[el][r['severity']] = r['c']

    alert_summary = {r['st']: r['c'] for r in run("SELECT st, COUNT(*) c FROM alerts GROUP BY st")}

    return jsonify(
        correlations=corr,
        buildings=bld_stats,
        defects=defects,
        alerts_summary=alert_summary,
        sensors={k: dict(name=s['n'], unit=s['u'], warn=s['warn'], crit=s['crit'], base=s['base']) for k, s in SENSORS.items()}
    )


@app.get('/api/settings/sensors')
@auth()
def get_sensor_settings():
    return jsonify(sensors={k: dict(name=s['n'], unit=s['u'], warn=s['warn'], crit=s['crit']) for k, s in SENSORS.items()})


@app.post('/api/settings/sensors')
@auth()
def update_sensor_settings():
    d = request.get_json(force=True, silent=True) or {}
    for k, v in d.items():
        if k in SENSORS and isinstance(v, dict):
            if 'warn' in v:
                SENSORS[k]['warn'] = float(v['warn'])
            if 'crit' in v:
                SENSORS[k]['crit'] = float(v['crit'])
    return jsonify(ok=True, sensors={k: dict(name=s['n'], unit=s['u'], warn=s['warn'], crit=s['crit']) for k, s in SENSORS.items()})


@app.get('/sample_images/<path:filename>')
def serve_sample_image(filename):
    sample_dir = os.path.join(BASE, 'sample_images')
    if not os.path.exists(sample_dir):
        sample_dir = os.path.join(os.path.dirname(BASE), 'sample_images')
    return send_from_directory(sample_dir, filename)


@app.post('/api/simulate/spike')
@auth()
def simulate_spike():
    d = request.get_json(force=True, silent=True) or {}
    kind = d.get('kind', 'vib')
    bi = bidx()
    vals = dict(LAST[bi])
    if kind == 'vib': vals['vib'] = 6.8
    elif kind == 'tilt': vals['tilt'] = 1.3
    elif kind == 'crack': vals['crack'] = 1.8
    elif kind == 'strain': vals['strain'] = 650.0
    elif kind == 'temp': vals['temp'] = 58.0
    elif kind == 'ml':
        vals['vib'] = 2.8; vals['tilt'] = 0.45; vals['crack'] = 0.75; vals['strain'] = 380.0
    store(bi, vals)
    return jsonify(ok=True, vals=vals, kind=kind)


@app.get('/')
def index():
    return app.send_static_file('index.html')


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except OSError:
        return '127.0.0.1'


def boot():
    init_db(); seed_history(); train_all(); crackml.get_model()
    threading.Thread(target=simulator, daemon=True).start()


if __name__ == '__main__':
    boot()
    port = int(os.environ.get('PORT', 8000))
    print(f'\n  StructSense is running.\n  Laptop: http://localhost:{port}\n  Phone (same Wi-Fi): http://{lan_ip()}:{port}\n')
    app.run(host='0.0.0.0', port=port, threaded=True)
