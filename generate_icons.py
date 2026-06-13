"""Generate PWA icons (192x192, 512x512) with no external dependencies.

Draws a warm cream background with a subtly-rounded "card" rect, a
sage-green progress ring filled to ~20% (life score 19/100), the score
"19" centered in the ring, and "LIFE" text below the ring, then writes
raw PNG bytes via zlib.
"""
import math
import struct
import zlib

BG = (232, 224, 213)     # outer panel, muted warm cream
CARD = (240, 235, 227)   # #F0EBE3 inner rounded card
TRACK = (227, 219, 207)  # ring track (unfilled)
GREEN = (91, 154, 111)   # #5B9A6F ring fill
BROWN = (44, 40, 37)     # #2C2825 score text
TAUPE = (138, 130, 121)  # #8A8279 "LIFE" label

RING_FILL_FRACTION = 0.20

FONT = {
    "1": [
        "00100",
        "01100",
        "00100",
        "00100",
        "00100",
        "00100",
        "01110",
    ],
    "9": [
        "01110",
        "10001",
        "10001",
        "01111",
        "00001",
        "00001",
        "01110",
    ],
    "L": [
        "10000",
        "10000",
        "10000",
        "10000",
        "10000",
        "10000",
        "11111",
    ],
    "I": [
        "11111",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
        "11111",
    ],
    "F": [
        "11111",
        "10000",
        "11110",
        "10000",
        "10000",
        "10000",
        "10000",
    ],
    "E": [
        "11111",
        "10000",
        "11110",
        "10000",
        "10000",
        "10000",
        "11111",
    ],
}


def in_rounded_rect(x, y, size, margin, radius):
    if x < margin or x > size - margin or y < margin or y > size - margin:
        return False
    left = x < margin + radius
    right = x > size - margin - radius
    top = y < margin + radius
    bottom = y > size - margin - radius
    if (left or right) and (top or bottom):
        cx = margin + radius if left else size - margin - radius
        cy = margin + radius if top else size - margin - radius
        dx, dy = x - cx, y - cy
        return dx * dx + dy * dy <= radius * radius
    return True


def draw_text(pixels, size, text, scale, color, oy):
    total_w = len(text) * 5 * scale + (len(text) - 1) * scale
    ox = (size - total_w) // 2
    for ci, ch in enumerate(text):
        glyph = FONT[ch]
        gx = ox + ci * 6 * scale
        for ry, row in enumerate(glyph):
            for rx, on in enumerate(row):
                if on == "1":
                    for sy in range(scale):
                        for sx in range(scale):
                            px, py = gx + rx * scale + sx, oy + ry * scale + sy
                            if 0 <= px < size and 0 <= py < size:
                                pixels[py][px] = color


def make_icon(size, path):
    margin = size * 0.03
    radius = size * 0.15625

    pixels = [[None] * size for _ in range(size)]
    for y in range(size):
        for x in range(size):
            pixels[y][x] = CARD if in_rounded_rect(x, y, size, margin, radius) else BG

    # progress ring (~20% filled, clockwise from 12 o'clock)
    cx = size / 2
    cy_ring = size * 0.42
    r_outer = size * 0.30
    thickness = size * 0.055
    r_inner = r_outer - thickness
    for y in range(size):
        for x in range(size):
            dx, dy = x - cx + 0.5, y - cy_ring + 0.5
            dist = math.sqrt(dx * dx + dy * dy)
            if r_inner <= dist <= r_outer:
                angle = math.atan2(dx, -dy) % (2 * math.pi)
                frac = angle / (2 * math.pi)
                pixels[y][x] = GREEN if frac <= RING_FILL_FRACTION else TRACK

    # "19" centered in the ring
    scale_score = max(1, round(size / 28))
    fh_score = 7 * scale_score
    draw_text(pixels, size, "19", scale_score, BROWN, int(cy_ring - fh_score / 2))

    # "LIFE" below the ring
    scale_life = max(1, round(size / 48))
    fh_life = 7 * scale_life
    draw_text(pixels, size, "LIFE", scale_life, TAUPE, int(size * 0.80 - fh_life / 2))

    write_png(path, pixels, size, size)


def write_png(path, pixels, width, height):
    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = bytearray()
    for row in pixels:
        raw.append(0)  # filter: none
        for (r, g, b) in row:
            raw.extend((r, g, b))

    compressed = zlib.compress(bytes(raw), 9)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", compressed))
        f.write(chunk(b"IEND", b""))


if __name__ == "__main__":
    make_icon(192, "icon-192.png")
    make_icon(512, "icon-512.png")
    print("Generated icon-192.png and icon-512.png")
