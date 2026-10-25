"""Makes crack_test.jpg (a concrete-like surface with one crack) so you can try crack detection without a real photo."""
import cv2, numpy as np
rng = np.random.default_rng(1)
img = cv2.GaussianBlur((150 + rng.normal(0, 7, (600, 900))).clip(0, 255).astype(np.uint8), (3, 3), 0)
pts = np.array([[60, 120], [200, 180], [330, 170], [450, 260], [600, 300], [760, 420], [840, 470]], np.int32)
cv2.polylines(img, [pts], False, 45, 4)
cv2.imwrite('crack_test.jpg', img)
print('Saved crack_test.jpg')
