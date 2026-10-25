"""Machine-learning crack classifier.

The photo is cut into small 64x64 patches. For every patch we compute ~23 numbers (brightness,
dark thin-line strength, edge strength, how aligned the edges are, shape of the dark pixels...).
A Random Forest then says "crack" or "not crack" for each patch, which gives a crack probability map.
OpenCV (vision.py) measures the cracks only inside the patches the model believes in, so stains,
shadows and pores are filtered out.
"""
import os
import cv2
import joblib
import numpy as np

P = 64                                   # patch size in pixels
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'crack_model.joblib')
_CACHE = {}


def features(gray):
    """23 numbers describing one grayscale (uint8) patch."""
    g = gray.astype(np.float32)
    bh = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))).astype(np.float32)
    gx, gy = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.hypot(gx, gy)
    jxx, jyy, jxy = (gx * gx).mean(), (gy * gy).mean(), (gx * gy).mean()
    coherence = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / (jxx + jyy + 1e-6)   # 1 = all edges point the same way
    p5, p50, p95 = np.percentile(g, [5, 50, 95])
    thr = max(12.0, float(bh.mean() + 2.5 * bh.std()))
    bw = (bh > thr).astype(np.uint8)
    n, _, st, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    if n > 1:
        i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        area = float(st[i, cv2.CC_STAT_AREA])
        length = float(max(st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT]))
    else:
        area = length = 0.0
    return [g.mean(), g.std(), p5, p50, p95, p50 - p5, bh.mean(), bh.std(), bh.max(), (bh > 15).mean(), (bh > 30).mean(),
            mag.mean(), mag.std(), np.percentile(mag, 95), coherence, area, length, area / (length + 1e-6),
            length / gray.shape[0], n - 1, bw.mean(), (g < g.mean() - 25).mean(), thr]


# ---------------------------------------------------------------- synthetic training data
def _texture(rng, hard=False):
    img = np.full((P, P), rng.uniform(80, 200), np.float32)
    for size, amp in ((4, 10), (8, 8), (16, 5)):
        img += cv2.resize(rng.normal(0, amp, (size, size)).astype(np.float32), (P, P), interpolation=cv2.INTER_CUBIC)
    return img + rng.normal(0, rng.uniform(8, 12) if hard else rng.uniform(2, 7), (P, P))


def _path(rng, c, theta, length, wander):
    d, perp = np.array([np.cos(theta), np.sin(theta)]), np.array([-np.sin(theta), np.cos(theta)])
    off, pts = 0.0, []
    for t in np.linspace(-length / 2, length / 2, 14):
        off += rng.normal(0, wander)
        pts.append(c + d * t + perp * off)
    return np.array(pts, np.int32).reshape(-1, 1, 2)


def _crack_mask(rng, hard):
    m = np.zeros((P, P), np.float32)
    c = np.array([P / 2, P / 2]) + rng.uniform(-14, 14, 2)
    th = rng.uniform(0, np.pi)
    w = int(rng.integers(1, 3 if hard else 6))
    cv2.polylines(m, [_path(rng, c, th, rng.uniform(.8, 1.7) * P, rng.uniform(1.2, 3.2))], False, 1.0, w)
    if rng.random() < .35:      # a branch
        cv2.polylines(m, [_path(rng, c + rng.uniform(-10, 10, 2), th + rng.uniform(.5, 1.2), rng.uniform(.3, .7) * P, 2.0)], False, 1.0, max(1, w - 1))
    return m


def sample(rng, crack, hard=False):
    """One synthetic 64x64 patch. crack=True -> contains a crack, else a 'trap' such as stains or pores."""
    img = _texture(rng, hard)
    if crack:
        m = _crack_mask(rng, hard)
        if m.sum() < 40:                         # keep only patches with a real visible crack
            return sample(rng, True, hard)
        img -= cv2.GaussianBlur(m, (0, 0), rng.uniform(.5, 1.1)) * rng.uniform(25, 45) if hard else \
               cv2.GaussianBlur(m, (0, 0), rng.uniform(.5, 1.1)) * rng.uniform(40, 110)
    kind = rng.choice(['plain', 'pores', 'stain', 'shadow', 'edge', 'scratch', 'mixed'])
    if kind in ('pores', 'mixed'):
        for _ in range(int(rng.integers(3, 16))):
            cv2.circle(img, tuple(rng.integers(0, P, 2).tolist()), int(rng.integers(1, 3)), float(img.mean() - rng.uniform(25, 70)), -1)
    if kind in ('stain', 'mixed'):
        s = np.zeros((P, P), np.float32)
        cv2.ellipse(s, tuple(rng.integers(10, 54, 2).tolist()), (int(rng.integers(6, 24)), int(rng.integers(6, 24))), float(rng.uniform(0, 180)), 0, 360, 1.0, -1)
        img -= cv2.GaussianBlur(s, (0, 0), rng.uniform(3, 8)) * rng.uniform(20, 90 if hard else 60)
    if kind == 'shadow':
        img += np.linspace(0, rng.uniform(-60, 60), P, dtype=np.float32)[None, :] * (1 if rng.random() < .5 else 0) + \
               np.linspace(0, rng.uniform(-60, 60), P, dtype=np.float32)[:, None]
    if kind == 'edge':
        img[:, int(rng.integers(10, 54)):] += rng.uniform(-45, 45)
    if kind == 'scratch' and not crack:          # very short faint marks are NOT cracks
        a = rng.integers(8, 56, 2)
        cv2.line(img, tuple(a.tolist()), tuple((a + rng.integers(-9, 10, 2)).tolist()), float(img.mean() - rng.uniform(15, 45)), 1)
    img = img * rng.uniform(.75, 1.25) + rng.uniform(-20, 20)
    img = cv2.GaussianBlur(img, (0, 0), rng.uniform(0, 1.0)) if rng.random() < .5 else img
    return np.clip(img, 0, 255).astype(np.uint8)


def make_set(n, seed, hard=False):
    rng = np.random.default_rng(seed)
    X, y = [], []
    for _ in range(n):
        X += [features(sample(rng, True, hard)), features(sample(rng, False, hard))]
        y += [1, 0]
    return np.array(X, np.float32), np.array(y)


def _fit(X, y):
    from sklearn.ensemble import RandomForestClassifier
    return RandomForestClassifier(n_estimators=150, max_depth=14, min_samples_leaf=3, n_jobs=-1, random_state=0).fit(X, y)


def train_synthetic(n=3000, save=True):
    import sklearn
    X1, y1 = make_set(n, 0)                 # clear examples
    X2, y2 = make_set(n // 2, 3, hard=True)  # faint, thin, noisy examples (like difficult real photos)
    X, y = np.vstack([X1, X2]), np.concatenate([y1, y2])
    rf = _fit(X, y)
    Xt, yt = make_set(800, 1)
    Xh, yh = make_set(800, 2, hard=True)
    meta = dict(source='synthetic', trained_on=int(len(y)), accuracy=round(float((rf.predict(Xt) == yt).mean()), 3),
                accuracy_hard=round(float((rf.predict(Xh) == yh).mean()), 3), sklearn=sklearn.__version__)
    bundle = dict(model=rf, meta=meta)
    if save:
        joblib.dump(bundle, MODEL_PATH, compress=3)
    return bundle


def train_from_folder(pos_dir, neg_dir, save=True, limit=6000):
    """Train on a REAL dataset: two folders of photos (cracked / not cracked), e.g. 'Concrete Crack Images for Classification'."""
    import sklearn
    from sklearn.model_selection import train_test_split
    X, y = [], []
    for label, folder in ((1, pos_dir), (0, neg_dir)):
        names = sorted(os.listdir(folder))[:limit]
        for nme in names:
            im = cv2.imread(os.path.join(folder, nme), cv2.IMREAD_GRAYSCALE)
            if im is not None:
                X.append(features(cv2.resize(im, (P, P), interpolation=cv2.INTER_AREA))); y.append(label)
    Xtr, Xte, ytr, yte = train_test_split(np.array(X, np.float32), np.array(y), test_size=.2, random_state=0, stratify=y)
    rf = _fit(Xtr, ytr)
    meta = dict(source='real dataset', trained_on=int(len(ytr)), accuracy=round(float((rf.predict(Xte) == yte).mean()), 3),
                accuracy_hard=None, sklearn=sklearn.__version__)
    bundle = dict(model=rf, meta=meta)
    if save:
        joblib.dump(bundle, MODEL_PATH, compress=3)
    return bundle


def get_model():
    """Load the saved model; if the file is missing or from an incompatible version, train a fresh one."""
    if 'm' not in _CACHE:
        try:
            _CACHE['m'] = joblib.load(MODEL_PATH)
        except Exception:
            print('Training the crack model (first run, about 30 seconds)...')
            _CACHE['m'] = train_synthetic(save=True)
    b = _CACHE['m']
    return b['model'], b['meta']


def heatmap(gray, model):
    """Crack probability for every pixel: slide a 64x64 window (step 32) and keep the highest score covering each pixel."""
    h, w = gray.shape
    if h < P or w < P:
        gray = cv2.copyMakeBorder(gray, 0, max(0, P - h), 0, max(0, P - w), cv2.BORDER_REFLECT)
        h, w = gray.shape
    ys, xs = list(range(0, h - P + 1, 32)), list(range(0, w - P + 1, 32))
    if ys[-1] + P < h: ys.append(h - P)
    if xs[-1] + P < w: xs.append(w - P)
    spots = [(y, x) for y in ys for x in xs]
    probs = model.predict_proba(np.array([features(gray[y:y + P, x:x + P]) for y, x in spots], np.float32))[:, 1]
    pmap = np.zeros((h, w), np.float32)
    for (y, x), p in zip(spots, probs):
        pmap[y:y + P, x:x + P] = np.maximum(pmap[y:y + P, x:x + P], p)
    return pmap, probs


if __name__ == '__main__':
    import argparse, time
    ap = argparse.ArgumentParser(description='Train the crack model.')
    ap.add_argument('--real', nargs=2, metavar=('POSITIVE_DIR', 'NEGATIVE_DIR'), help='folders of cracked / not-cracked photos')
    a = ap.parse_args()
    t = time.time()
    b = train_from_folder(*a.real) if a.real else train_synthetic()
    print('Saved', MODEL_PATH, '|', b['meta'], f'| {time.time() - t:.0f}s')
