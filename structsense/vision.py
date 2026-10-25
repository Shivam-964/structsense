"""Crack analysis: ML decides WHERE cracks are, OpenCV measures them, then a repair is simulated.

1. Resize the photo, then the ML model (crackml.py) scores every 64x64 patch for cracks.
2. OpenCV black-hat finds thin dark lines; we keep only long thin shapes inside patches the ML trusts.
3. Skeleton gives the length, distance transform gives the width, fitLine gives the direction.
4. cv2.inpaint paints the crack out to simulate the repaired surface.
"""
import base64
import cv2
import numpy as np
import crackml


def skeleton(mask):
    """Thin every shape down to a 1-pixel line using repeated erosion."""
    sk = np.zeros_like(mask)
    el = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    m = mask.copy()
    while cv2.countNonZero(m):
        er = cv2.erode(m, el)
        sk = cv2.bitwise_or(sk, cv2.subtract(m, cv2.dilate(er, el)))
        m = er
    return sk


def uri(im, q=82):
    return 'data:image/jpeg;base64,' + base64.b64encode(cv2.imencode('.jpg', im, [cv2.IMWRITE_JPEG_QUALITY, q])[1]).decode()


def pick(bw, pmap, relaxed):
    """Keep components that are long, thin AND where the ML model sees a crack."""
    n, lab, st, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    mask, boxes = np.zeros_like(bw), []
    min_len, max_thick = (30, 14) if relaxed else (40, 12)
    for i in range(1, n):
        x, y, w, h, area = st[i]
        if max(w, h) >= min_len and area >= 30 and area / max(w, h) < max_thick:
            sel = lab == i
            if float(pmap[sel].mean()) >= 0.5:
                mask[sel] = 255
                boxes.append((x, y, w, h))
    return mask, boxes


def analyze(data, mm_per_px=0.25):
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError('That file is not a readable image.')
    h, w = img.shape[:2]
    f = 800 / w if w > 800 else 1.0              # shrink big phone photos so analysis stays fast
    if f < 1:
        img = cv2.resize(img, (800, int(h * f)), interpolation=cv2.INTER_AREA)
    mm = mm_per_px / f                            # millimetres per pixel of the resized image
    raw = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    model, meta = crackml.get_model()
    pmap, probs = crackml.heatmap(raw, model)
    ml_conf = float(probs.max())

    blur = cv2.GaussianBlur(raw, (5, 5), 0)
    bh = cv2.morphologyEx(blur, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17)))
    pm = pmap[:raw.shape[0], :raw.shape[1]]
    mask, boxes = np.zeros_like(raw), []
    if ml_conf >= 0.5:                            # only look for cracks if the ML model believes there is one
        for relaxed, k in ((False, 3), (True, 2)):
            _, bw = cv2.threshold(bh, max(10, bh.mean() + k * bh.std()), 255, cv2.THRESH_BINARY)
            bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
            mask, boxes = pick(bw, pm, relaxed)
            if boxes:
                break

    res = dict(detected=False, severity='none', label='No crack found', length_mm=0.0, max_width_mm=0.0, avg_width_mm=0.0,
               coverage_pct=0.0, regions=0, pattern='none', ml_conf=round(ml_conf, 3),
               ml_area_pct=round(float((probs > 0.5).mean() * 100), 1), model=meta,
               original=uri(img), image=uri(img), repaired=None)
    if boxes:
        sk = skeleton(mask)
        widths = 2 * cv2.distanceTransform(mask, cv2.DIST_L2, 5)[sk > 0]
        length_px = int(cv2.countNonZero(sk))
        max_w = float(np.percentile(widths, 95)) * mm      # 95th percentile ignores noisy pixels
        sev = 'crit' if max_w > 1.0 else 'warn' if max_w >= 0.3 else 'ok'
        ys, xs = np.nonzero(sk)
        vx, vy = cv2.fitLine(np.column_stack([xs, ys]).astype(np.float32), cv2.DIST_L2, 0, 0.01, 0.01).ravel()[:2]
        ang = float(np.degrees(np.arctan2(vy, vx)) % 180)
        pattern = 'branching' if len(boxes) >= 3 else 'horizontal' if ang < 25 or ang > 155 else 'vertical' if 65 < ang < 115 else 'diagonal'
        out = img.copy()
        out[mask > 0] = (0, 0, 255)
        out = cv2.addWeighted(out, 0.85, img, 0.15, 0)
        for x, y, bw_, bh_ in boxes:
            cv2.rectangle(out, (x - 4, y - 4), (x + bw_ + 4, y + bh_ + 4), (0, 190, 255), 2)
        repaired = cv2.inpaint(img, cv2.dilate(mask, np.ones((5, 5), np.uint8)), 4, cv2.INPAINT_TELEA)
        res.update(detected=True, severity=sev, label={'crit': 'Major crack', 'warn': 'Minor crack', 'ok': 'Hairline crack'}[sev],
                   length_mm=round(length_px * mm, 1), max_width_mm=round(max_w, 2), avg_width_mm=round(float(widths.mean()) * mm, 2),
                   coverage_pct=round(cv2.countNonZero(mask) / mask.size * 100, 3), regions=len(boxes), pattern=pattern,
                   image=uri(out), repaired=uri(repaired))
    return res
