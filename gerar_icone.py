from PIL import Image, ImageDraw
import math
S = 2048  # 4x de 512
img = Image.new("RGB", (S, S))
px = img.load()
top, bot = (0x3E, 0x6B, 0x74), (0x1C, 0xC2, 0xDE)
for y in range(S):
    t = y / (S - 1)
    c = tuple(round(top[i] + (bot[i] - top[i]) * t) for i in range(3))
    for x in range(S):
        px[x, y] = c
d = ImageDraw.Draw(img)
k = S / 512
# cartao branco arredondado
d.rounded_rectangle([130*k, 130*k, 382*k, 382*k], radius=56*k, fill="white")
# arco do velocimetro (semicirculo)
cx, cy, r, w = 256*k, 300*k, 92*k, 24*k
d.arc([cx-r, cy-r, cx+r, cy+r], 180, 360, fill=(0xDC, 0xE8, 0xEC), width=int(w))
d.arc([cx-r, cy-r, cx+r, cy+r], 180, 310, fill=(0x1C, 0xC2, 0xDE), width=int(w))
# ponteiro
ang = math.radians(-50)
L = 78*k
ex, ey = cx + L*math.cos(ang), cy + L*math.sin(ang)
d.line([cx, cy, ex, ey], fill=(0x1C, 0xC2, 0xDE), width=int(18*k))
for p in [(cx, cy), (ex, ey)]:
    d.ellipse([p[0]-9*k, p[1]-9*k, p[0]+9*k, p[1]+9*k], fill=(0x1C, 0xC2, 0xDE))
d.ellipse([cx-18*k, cy-18*k, cx+18*k, cy+18*k], fill=(0x3E, 0x6B, 0x74))
# base
d.rounded_rectangle([190*k, 336*k, 322*k, 350*k], radius=7*k, fill=(0xDC, 0xE8, 0xEC))
for n in (512, 192, 180):
    img.resize((n, n), Image.LANCZOS).save(f"icon-{n}.png")
