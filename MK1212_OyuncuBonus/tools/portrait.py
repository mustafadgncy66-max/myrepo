"""Düz arka planlı bir portreden Attila portre dosyalarını üretir.

    python3 portrait.py <kaynak> <çıktı klasörü> <ad>

Arka plan, kenarlardan başlayıp kenar rengine yakın piksellere yayılarak şeffaf yapılır. Çıktı:
ui/portraits/portholes/att_cult_eastern/<ad>.png (180x240) ve ui/portraits/units/att_cult_eastern/<ad>.png
(64x152), MK1212'nin sultan portresiyle aynı boyut ve kadrajda.
"""
import os
import sys
from collections import deque

from PIL import Image, ImageFilter

TOLERANCE = 30          # arka plan rengine uzaklık (RGB)
WORK_WIDTH = 600        # maske bu genişlikte hesaplanır
# Kadrajlar, kaynak genişliğine/yüksekliğine oranla (sol, üst, sağ, alt).
PORTHOLE_BOX = (0.18, 0.05, 0.78, 0.65)
UNIT_BOX = (0.29, 0.05, 0.73, 0.83)
SIZES = {'portholes': (180, 240), 'units': (64, 152)}


def largest_component(mask):
    """Arka plandaki fırça izlerinden kalan adacıkları atar; yalnızca figür kalır."""
    w, h = mask.size
    m = mask.load()
    seen = set()
    best = []
    for start in ((x, y) for y in range(h) for x in range(w)):
        if m[start] == 0 or start in seen:
            continue
        seen.add(start)
        component, queue = [], deque([start])
        while queue:
            x, y = queue.popleft()
            component.append((x, y))
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= n[0] < w and 0 <= n[1] < h and m[n] and n not in seen:
                    seen.add(n)
                    queue.append(n)
        if len(component) > len(best):
            best = component
    result = Image.new('L', (w, h), 0)
    r = result.load()
    for xy in best:
        r[xy] = 255
    return result


def background_mask(im):
    small = im.resize((WORK_WIDTH, round(im.height * WORK_WIDTH / im.width)), Image.BILINEAR)
    w, h = small.size
    px = small.load()
    border = [px[x, y] for x in range(w) for y in (0, h - 1)] + [px[x, y] for y in range(h) for x in (0, w - 1)]
    bg = tuple(sorted(c[i] for c in border)[len(border) // 2] for i in range(3))
    near = lambda c: sum((c[i] - bg[i]) ** 2 for i in range(3)) <= TOLERANCE ** 2
    mask = Image.new('L', (w, h), 255)
    m = mask.load()
    queue = deque((x, y) for x in range(w) for y in (0, h - 1)) + deque((x, y) for y in range(h) for x in (0, w - 1))
    while queue:
        x, y = queue.popleft()
        if m[x, y] == 0 or not near(px[x, y]):
            continue
        m[x, y] = 0
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and m[nx, ny]:
                queue.append((nx, ny))
    # Küçük delikleri kapat, kenarı yumuşat.
    mask = largest_component(mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3)))
    return mask.resize(im.size, Image.BILINEAR).filter(ImageFilter.GaussianBlur(2))


def main(source, out_dir, name):
    im = Image.open(source).convert('RGB')
    rgba = im.copy()
    rgba.putalpha(background_mask(im))
    for kind, box in (('portholes', PORTHOLE_BOX), ('units', UNIT_BOX)):
        crop = rgba.crop(tuple(round(v * (im.width if i % 2 == 0 else im.height)) for i, v in enumerate(box)))
        path = os.path.join(out_dir, 'ui', 'portraits', kind, 'att_cult_eastern', name + '.png')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        crop.resize(SIZES[kind], Image.LANCZOS).save(path)
        print(path, SIZES[kind])


if __name__ == '__main__':
    main(*sys.argv[1:4])
