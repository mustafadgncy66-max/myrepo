"""Yeşil ekran önünde çizilmiş bir portreden Attila portre dosyalarını üretir.

    python3 portrait.py <kaynak> <çıktı klasörü> <ad>

Kenarlara bağlı yeşil alan şeffaf yapılır; figürün içindeki yeşiller (ör. zümrüt taşlar) korunur. Çıktı:
ui/portraits/portholes/att_cult_eastern/<ad>.png (180x240) ve ui/portraits/units/att_cult_eastern/<ad>.png
(64x152), MK1212'nin sultan portresiyle aynı boyut ve kadrajda.
"""
import os
import sys
from collections import deque

import numpy as np
from PIL import Image, ImageFilter

# Yeşillik: G - max(R, B). Arka plan ~95; bu eşiğin üstü arka plan sayılır.
GREEN_KEY = 40
# Kenar bandında yumuşak geçiş: yeşillik SOFT_LOW'da opak, SOFT_HIGH'ta tamamen şeffaf.
SOFT_LOW, SOFT_HIGH = 25, 85
EDGE_BAND = 13          # kenar bandı genişliği (piksel, tek sayı)
WORK_WIDTH = 600        # bağlantılı arka plan bu genişlikte bulunur
# Kadrajlar, kaynak genişliğine/yüksekliğine oranla (sol, üst, sağ, alt).
PORTHOLE_BOX = (0.064, 0.03, 0.874, 0.8365)
UNIT_BOX = (0.201, 0.03, 0.737, 0.98)
SIZES = {'portholes': (180, 240), 'units': (64, 152)}


def greenness(rgb):
    return rgb[..., 1] - np.maximum(rgb[..., 0], rgb[..., 2])


def background_region(im):
    """Kenarlardan erişilebilen yeşil alan (küçük ölçekte, 255 = arka plan)."""
    small = im.resize((WORK_WIDTH, round(im.height * WORK_WIDTH / im.width)), Image.BILINEAR)
    key = greenness(np.asarray(small, dtype=np.int32)) > GREEN_KEY
    h, w = key.shape
    bg = np.zeros_like(key)
    queue = deque((x, y) for x in range(w) for y in (0, h - 1))
    queue.extend((x, y) for y in range(h) for x in (0, w - 1))
    while queue:
        x, y = queue.popleft()
        if bg[y, x] or not key[y, x]:
            continue
        bg[y, x] = True
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not bg[ny, nx]:
                queue.append((nx, ny))
    return Image.fromarray(np.where(bg, 255, 0).astype(np.uint8))


def cut_out(im):
    rgb = np.asarray(im, dtype=np.int32)
    bg = background_region(im).resize(im.size, Image.NEAREST)
    band = np.asarray(bg.filter(ImageFilter.MaxFilter(EDGE_BAND))) > 0
    soft = np.clip((SOFT_HIGH - greenness(rgb)) / (SOFT_HIGH - SOFT_LOW), 0, 1)
    alpha = np.where(band, soft, 1.0)
    # Kenardaki yeşil yansımayı temizle.
    rgb = rgb.copy()
    rgb[..., 1] = np.where(band, np.minimum(rgb[..., 1], np.maximum(rgb[..., 0], rgb[..., 2])), rgb[..., 1])
    out = np.dstack([rgb, np.round(alpha * 255)]).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')


def main(source, out_dir, name):
    im = Image.open(source).convert('RGB')
    rgba = cut_out(im)
    for kind, box in (('portholes', PORTHOLE_BOX), ('units', UNIT_BOX)):
        crop = rgba.crop(tuple(round(v * (im.width if i % 2 == 0 else im.height)) for i, v in enumerate(box)))
        path = os.path.join(out_dir, 'ui', 'portraits', kind, 'att_cult_eastern', name + '.png')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        crop.resize(SIZES[kind], Image.LANCZOS).save(path)
        print(path, SIZES[kind])


if __name__ == '__main__':
    main(*sys.argv[1:4])
