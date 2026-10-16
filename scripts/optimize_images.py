"""图片压缩脚本：把原始图片转成 WebP（大图 + 小图）。

用法：
    python scripts/optimize_images.py <原始图片目录> [输出目录] [选项]

默认输出到 web/public/products，默认生成 <名字>.webp（最长边 1000px）与 <名字>-thumb.webp（最长边 320px）。

选项：
    --full-max N       大图最长边，默认 1000（Banner 建议 1600）
    --thumb-max N      小图最长边，默认 320（Banner 建议 800）
    --thumb-suffix S   小图后缀，默认 -thumb（Banner 常用 -sm）
    --quality N        大图质量，默认 82
    --thumb-quality N  小图质量，默认 80

示例（首页 Banner）：
    python scripts/optimize_images.py ~/banners web/public/banners \
        --full-max 1600 --thumb-max 800 --thumb-suffix -sm --quality 80 --thumb-quality 78
"""
import argparse
import pathlib

from PIL import Image

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def main() -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("src")
    parser.add_argument("out", nargs="?")
    parser.add_argument("--full-max", type=int, default=1000)
    parser.add_argument("--thumb-max", type=int, default=320)
    parser.add_argument("--thumb-suffix", default="-thumb")
    parser.add_argument("--quality", type=int, default=82)
    parser.add_argument("--thumb-quality", type=int, default=80)
    args = parser.parse_args()

    src = pathlib.Path(args.src)
    out = pathlib.Path(args.out) if args.out else pathlib.Path(__file__).resolve().parents[1] / "web" / "public" / "products"
    out.mkdir(parents=True, exist_ok=True)

    sources = sorted(p for p in src.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
    if not sources:
        print(f"未在 {src} 找到图片")
        return 1

    before = after = 0
    for path in sources:
        image = Image.open(path).convert("RGB")
        before += path.stat().st_size
        full = image.copy()
        full.thumbnail((args.full_max, args.full_max), Image.LANCZOS)
        full_path = out / f"{path.stem}.webp"
        full.save(full_path, "WEBP", quality=args.quality, method=6)
        small = image.copy()
        small.thumbnail((args.thumb_max, args.thumb_max), Image.LANCZOS)
        small_path = out / f"{path.stem}{args.thumb_suffix}.webp"
        small.save(small_path, "WEBP", quality=args.thumb_quality, method=6)
        after += full_path.stat().st_size + small_path.stat().st_size
        print(f"{path.name:24} {full.size[0]:>4}x{full.size[1]:<4} {path.stat().st_size / 1024:8.0f}KB -> "
              f"{full_path.stat().st_size / 1024:6.0f}KB + {small_path.stat().st_size / 1024:5.0f}KB")
    print(f"合计 {before / 1024 / 1024:.2f}MB -> {after / 1024:.0f}KB（压缩 {before / after:.1f}x）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
