"""Generate PWA icons (192x192, 512x512) with no external dependencies.

Draws a minimal compass-rose logo: a warm dark brown background, a
four-point star (kite shapes) in cream with the north point accented in
sage green, framed by a subtle warm-gray ring, then writes raw PNG bytes
via zlib.
"""
import math
import struct
import zlib

BG = (0x2C, 0x28, 0x25)     # #2C2825 warm dark brown background
CREAM = (0xF0, 0xEB, 0xE3)  # #F0EBE3 compass body
GREEN = (0x5B, 0x9A, 0x6F)  # #5B9A6F north pointer accent
GRAY = (0x8A, 0x82, 0x79)   # #8A8279 subtle inner ring

SQRT2 = math.sqrt(2)
DIRS = {
    "N": (0, -1),
    "E": (1, 0),
    "S": (0, 1),
    "W": (-1, 0),
    "NE": (1 / SQRT2, -1 / SQRT2),
    "SE": (1 / SQRT2, 1 / SQRT2),
    "SW": (-1 / SQRT2, 1 / SQRT2),
    "NW": (-1 / SQRT2, -1 / SQRT2),
}


def point_in_convex(px, py, verts):
    sign = 0
    for i in range(len(verts)):
        x1, y1 = verts[i]
        x2, y2 = verts[(i + 1) % len(verts)]
        cross = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)
        if cross != 0:
            s = 1 if cross > 0 else -1
            if sign == 0:
                sign = s
            elif s != sign:
                return False
    return True


def make_icon(size, path):
    cx = cy = size / 2
    r_outer = size * 0.32
    r_inner = size * 0.105
    ring_r = size * 0.40
    ring_t = size * 0.012

    def pt(direction, r):
        dx, dy = DIRS[direction]
        return (cx + dx * r, cy + dy * r)

    center = (cx, cy)
    kites = {
        "N": [center, pt("NW", r_inner), pt("N", r_outer), pt("NE", r_inner)],
        "E": [center, pt("NE", r_inner), pt("E", r_outer), pt("SE", r_inner)],
        "S": [center, pt("SE", r_inner), pt("S", r_outer), pt("SW", r_inner)],
        "W": [center, pt("SW", r_inner), pt("W", r_outer), pt("NW", r_inner)],
    }
    colors = {"N": GREEN, "E": CREAM, "S": CREAM, "W": CREAM}

    pixels = [[BG] * size for _ in range(size)]
    for y in range(size):
        py = y + 0.5
        for x in range(size):
            px = x + 0.5
            dist = math.hypot(px - cx, py - cy)
            color = None
            if abs(dist - ring_r) <= ring_t / 2:
                color = GRAY
            for key, verts in kites.items():
                if point_in_convex(px, py, verts):
                    color = colors[key]
                    break
            if color:
                pixels[y][x] = color

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
