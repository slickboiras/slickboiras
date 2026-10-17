"""
make_ascii.py - turn an image into the colored ASCII art used in the profile card.

Pipeline:
  1. rembg (isnet-general-use) finds the subject (speaker stack + car) so it can be
     drawn at full contrast while the busy background is drawn dim and sparse.
  2. area-average (BOX) downsample -> each cell = mean of its pixels. Matters for
     halftone images: LANCZOS would alias the dot grid into moire stripes.
  3. luminance -> character from RAMP (space = darkest, '@' = brightest).
     Background cells are capped at BG_MAX so they never compete with the subject.
  4. cell color -> small k-means palette per region, lifted in lightness so glyphs
     stay readable on the dark art panel. A small palette keeps the SVG small,
     because runs of same-colored chars collapse into one <tspan>.

Usage:
    pip install rembg onnxruntime pillow numpy
    python tools/make_ascii.py pfp.png                  # writes art.json
    python tools/make_ascii.py pfp.png --cols 112 --no-subject
Then run generate.py to rebuild the SVGs.
"""
import argparse
import colorsys
import json

import numpy as np
from PIL import Image, ImageFilter

RAMP = " .,:;-=+*#%@"
BG_MAX = 3                     # background uses at most RAMP[:4] -> " .,:"
ART_FONT, ART_LINE = 8, 8.8    # must match generate.py
CHAR_ASPECT = 0.57 * ART_FONT / ART_LINE   # glyph width / line height


def kmeans(x, k, iters=30, seed=0):
    rng = np.random.default_rng(seed)
    c = x[rng.choice(len(x), k, replace=False)].copy()
    for _ in range(iters):
        lab = ((x[:, None, :] - c[None]) ** 2).sum(-1).argmin(1)
        for j in range(k):
            if (lab == j).any():
                c[j] = x[lab == j].mean(0)
    return c, lab


def lift(rgb, floor, span, sat=1.25):
    """Remap lightness into [floor, floor+span] so dark-cell glyphs stay visible."""
    h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in rgb))
    r, g, b = colorsys.hls_to_rgb(h, floor + span * l, min(1.0, s * sat))
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--cols", type=int, default=112)
    ap.add_argument("--no-subject", action="store_true", help="skip subject detection")
    ap.add_argument("--out", default="art.json")
    args = ap.parse_args()

    im = Image.open(args.image).convert("RGB")
    w, h = im.size
    cols = args.cols
    rows = round(cols * (h / w) * CHAR_ASPECT)

    # subject mask (upscale first: rembg works better above its 320px input)
    if args.no_subject:
        subj = np.ones((rows, cols), bool)
    else:
        from rembg import new_session, remove
        big = im.resize((w * 3, h * 3), Image.LANCZOS)
        alpha = remove(big, session=new_session("isnet-general-use")).split()[3]
        subj = np.asarray(alpha.resize((cols, rows), Image.BOX), dtype=float) > 100

    small = np.asarray(im.resize((cols, rows), Image.BOX), dtype=float)
    # luminance: blur away the halftone dot grid, then sharpen at a larger radius so
    # speaker cones / car edges survive the downsample
    soft = im.convert("L").filter(ImageFilter.GaussianBlur(1.2)).filter(ImageFilter.UnsharpMask(4, 140, 1))
    lum_raw = np.asarray(soft.resize((cols, rows), Image.BOX), dtype=float)
    # rank-equalise each region separately: the white car would otherwise squash the
    # speaker stack into a narrow dark band
    lum = np.zeros_like(lum_raw)
    for region in (subj, ~subj):
        if region.any():
            v = np.sort(lum_raw[region])
            lum[region] = np.searchsorted(v, lum_raw[region]) / len(v)

    # one palette for the subject (near-neutral, bright) and one for the background (dim green)
    palette, labels = [], np.zeros((rows, cols), int)
    for region, k, floor, span, sat in ((subj, 4, 0.55, 0.45, 0.6), (~subj, 4, 0.28, 0.40, 1.5)):
        if not region.any():
            continue
        cen, lab = kmeans(small[region], k)
        labels[region] = lab + len(palette)
        palette += [lift(c, floor, span, sat) for c in cen]

    chars, colors = [], []
    for r in range(rows):
        row_c, row_k = [], []
        for c in range(cols):
            if subj[r, c]:   # never blank inside the subject, so its silhouette reads
                idx = 1 + min(len(RAMP) - 2, int(lum[r, c] * (len(RAMP) - 1)))
            else:            # background: sparse texture only
                idx = min(BG_MAX, int(lum[r, c] * (BG_MAX + 1)))
            row_c.append(RAMP[idx])
            row_k.append("0123456789abcdef"[labels[r, c]])
        chars.append("".join(row_c))
        colors.append("".join(row_k))

    with open(args.out, "w") as f:
        json.dump({"chars": chars, "colors": colors, "palette": palette}, f, indent=0)
    print(f"wrote {args.out}: {cols} cols x {rows} rows, {len(palette)} colors")


if __name__ == "__main__":
    main()
