import cv2
import numpy as np

YELLOW = (0, 255, 255)   # BGR


def show_step(title, image):
    """Show one image, wait for a key press, then close it."""
    cv2.imshow(title, image)
    cv2.waitKey(0)
    cv2.destroyWindow(title)


def scan_perpendicular(vis, lump, lumps, direction=None, color=(0, 0, 255), thickness=1):
    """Scan perpendicular to `lump` through the whole image.

    returns a list of (id, contour) for every other lump the line crosses,
    nearest first. Empty list if none are hit.
    """
    H, W = vis.shape[:2]

    labels = np.zeros((H, W), np.int32)
    for lump_id, c in lumps.items():
        cv2.drawContours(labels, [c], -1, lump_id, -1)
    own_id = next((i for i, c in lumps.items() if c is lump), 0)

    M = cv2.moments(lump)
    cx, cy = M["m10"] / M["m00"], M["m01"] / M["m00"]

    vx, vy, _, _ = cv2.fitLine(lump, cv2.DIST_L2, 0, 0.01, 0.01).flatten()
    px, py = -vy, vx

    L = int(np.hypot(W, H))
    dirs = (1, -1) if direction is None else (direction,)

    hits = {}  # id -> (distance, hit_point); keeps the nearest hit per lump
    for d in dirs:
        last = (int(cx), int(cy))
        for t in range(1, L):
            x = int(round(cx + d * px * t))
            y = int(round(cy + d * py * t))
            if not (0 <= x < W and 0 <= y < H):
                break
            last = (x, y)
            label = int(labels[y, x])
            if label != 0 and label != own_id:
                if label not in hits or t < hits[label][0]:
                    hits[label] = (t, (x, y))
        cv2.line(vis, (int(cx), int(cy)), last, color, thickness)

    ordered = sorted(hits.items(), key=lambda kv: kv[1][0])
    for _, (_, point) in ordered:
        cv2.circle(vis, point, 5, (255, 255, 0), -1)   # cyan hit dots

    return [(lump_id, lumps[lump_id]) for lump_id, _ in ordered]


def find_identical_pairs(lump_pairs):
    """Return pairs that appear in both orders, e.g. (1, 2) and (2, 1)."""
    seen = set(lump_pairs)
    return sorted(
        (a, b) for a, b in seen
        if a < b and (b, a) in seen
    )


def lump_center(lump):
    M = cv2.moments(lump)
    return int(round(M["m10"] / M["m00"])), int(round(M["m01"] / M["m00"]))


def show_basket(vis, lumps, pair):
    """Mark a found basket: text, both lump centers, line between them, inclination."""
    id_a, id_b = pair
    ca, cb = lump_center(lumps[id_a]), lump_center(lumps[id_b])

    cv2.putText(vis, "Basket found", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, YELLOW, 3)

    cv2.line(vis, ca, cb, (255, 0, 255), 1)

    # Inclination of the line: 0 = horizontal, range -90..90
    dx = cb[0] - ca[0]
    dy = ca[1] - cb[1]                      # flip y, image y points down
    inclination = np.degrees(np.arctan2(dy, dx))
    if inclination > 90:
        inclination -= 180
    elif inclination <= -90:
        inclination += 180

    cv2.putText(vis, f"inclination: {inclination:.1f} deg", (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, YELLOW, 2)

    for lump_id, (cx, cy) in ((id_a, ca), (id_b, cb)):
        cv2.circle(vis, (cx, cy), 6, (255, 0, 255), -1)
        cv2.putText(vis, f"#{lump_id} ({cx},{cy})", (cx - 50, cy - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, YELLOW, 2)

    return ca, cb, inclination


# ---------- load and prepare ----------
img = cv2.imread("hard1/noise3.jpeg")
img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)

target_w = 800
scale = target_w / img.shape[1]
small = cv2.resize(img, (target_w, int(img.shape[0] * scale)), interpolation=cv2.INTER_AREA)

hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)

# ---------- masks ----------
lower = np.array([10, 120, 100])
upper = np.array([25, 255, 255])

mask_raw = cv2.inRange(hsv, lower, upper)
show_step("1 - Raw mask", mask_raw)

mask_open = cv2.morphologyEx(mask_raw, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
show_step("2 - After opening (speckle removed)", mask_open)

mask = cv2.morphologyEx(mask_open, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
show_step("3 - After closing (final mask)", mask)

# ---------- lumps and IDs ----------
contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
blobs = [c for c in contours if cv2.contourArea(c) > 300]

# Assign IDs: sort left to right, ID 1 = leftmost lump
blobs.sort(key=lambda c: cv2.boundingRect(c)[0])
lumps = {i + 1: c for i, c in enumerate(blobs)}

ID_COLOR = (0, 0, 255)   # BGR: red

ids_vis = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
for lump_id, c in lumps.items():
    M = cv2.moments(c)
    cx, cy = int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
    x, y, w, h = cv2.boundingRect(c)
    cv2.rectangle(ids_vis, (x, y), (x + w, y + h), (0, 255, 0), 1)
    cv2.putText(ids_vis, str(lump_id), (cx - 10, cy + 10),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, ID_COLOR, 2)
show_step("4 - Lump IDs", ids_vis)

# ---------- scanning and pairing ----------
scan_vis = ids_vis.copy()

SIZE_TOLERANCE = 0.3   # "almost similar" = within ±30% of this lump's area

lump_pairs = []   # list of (id, partner_id)

for lump_id, lump in lumps.items():
    found = scan_perpendicular(scan_vis, lump, lumps)

    if not found:
        print(f"Lump {lump_id}: no lump found")
        continue

    base_area = cv2.contourArea(lump)

    similar = [
        f for f in found
        if abs(cv2.contourArea(f[1]) - base_area) <= SIZE_TOLERANCE * base_area
    ]

    if not similar:
        print(f"Lump {lump_id}: found {[i for i, _ in found]}, but none of similar size")
        continue

    big_id, big_contour = max(similar, key=lambda f: cv2.contourArea(f[1]))
    lump_pairs.append((lump_id, big_id))
    print(f"Lump {lump_id}: pair ({lump_id}, {big_id})")

show_step("5 - Perpendicular scan lines", scan_vis)

print("All pairs:", lump_pairs)

identical = find_identical_pairs(lump_pairs)

# ---------- final image: the only one with basket text and inclination ----------
if len(identical) == 1:
    ca, cb, inclination = show_basket(small, lumps, identical[0])
    print(f"Bowl found: lump {identical[0][0]} at {ca}, lump {identical[0][1]} at {cb}")
    print(f"Inclination: {inclination:.1f} deg")
else:
    print(f"{len(identical)} identical pairs found, no basket")

show_step("6 - Final result", small)