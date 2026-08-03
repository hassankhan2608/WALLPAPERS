#!/usr/bin/env python3
from __future__ import annotations

import base64
import colorsys
import html
import io
import json
import os
import re
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "Wallpapers"
OUTPUT_DIR = ROOT / ".wallpaper-catalog"
CACHE_DIR = ROOT / ".wallpaper-cache"
THUMBNAIL_SIZE = (640, 360)
SAMPLE_SIZE = (8, 8)
METADATA_VERSION = 1
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
COLOR_GROUPS = ("red", "orange", "yellow", "green", "blue", "purple")
WALLHAVEN_PATTERN = re.compile(r"wallhaven-([a-z0-9]+)", re.IGNORECASE)


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def tracked_images() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", SOURCE_DIR.relative_to(ROOT).as_posix()],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    paths = [ROOT / os.fsdecode(value) for value in result.stdout.split(b"\0") if value]
    return sorted(
        (path for path in paths if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS),
        key=lambda path: path.name.casefold(),
    )


def color_group(red: int, green: int, blue: int) -> str:
    hue, _, _ = colorsys.rgb_to_hsv(red / 255, green / 255, blue / 255)
    degrees = hue * 360
    if degrees < 10 or degrees >= 345:
        return "red"
    if degrees < 45:
        return "orange"
    if degrees < 70:
        return "yellow"
    if degrees < 160:
        return "green"
    if degrees < 250:
        return "blue"
    return "purple"


def analyze_colors(sample: Image.Image) -> tuple[str, list[str]]:
    red, green, blue = sample.resize((1, 1), Image.Resampling.BILINEAR).getpixel((0, 0))
    dominant = f"#{red:02x}{green:02x}{blue:02x}"

    grid = sample.resize(SAMPLE_SIZE, Image.Resampling.BILINEAR)
    counts: Counter[str] = Counter()
    for pixel in grid.getdata():
        _, saturation, value = colorsys.rgb_to_hsv(
            pixel[0] / 255,
            pixel[1] / 255,
            pixel[2] / 255,
        )
        if saturation >= 0.25 and value >= 0.20:
            counts[color_group(*pixel)] += 1

    groups = [group for group, count in counts.items() if count >= 12]
    if not groups and counts:
        top = max(counts, key=counts.get)
        if counts[top] >= 6:
            groups = [top]

    return dominant, sorted(groups)


def process_image(path: Path, blob_sha: str) -> dict[str, object]:
    cached_metadata = CACHE_DIR / "metadata" / f"{blob_sha}.json"
    cached_thumbnail = CACHE_DIR / "thumbnails" / f"{blob_sha}.webp"
    output_thumbnail = OUTPUT_DIR / "thumbnails" / f"{blob_sha}.webp"

    if cached_metadata.is_file() and cached_thumbnail.is_file():
        cached = json.loads(cached_metadata.read_text(encoding="utf-8"))
        if cached.get("_version") == METADATA_VERSION:
            metadata = {key: value for key, value in cached.items() if key != "_version"}
            shutil.copy2(cached_thumbnail, output_thumbnail)
            return metadata

    cached_thumbnail.parent.mkdir(parents=True, exist_ok=True)
    width = 0
    height = 0
    try:
        with Image.open(path) as source:
            width, height = source.size
            thumbnail = source.copy()
            thumbnail.thumbnail(THUMBNAIL_SIZE)
            thumbnail.save(cached_thumbnail, "WEBP", optimize=True, quality=85)
    except Exception as error:
        print(f"Pillow could not process {path.name}: {error}. Using ImageMagick.")
        dimensions = subprocess.run(
            ["identify", "-format", "%w %h", str(path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.split()
        width, height = map(int, dimensions[:2])

        command = [
            "magick",
            str(path),
            "-thumbnail",
            f"{THUMBNAIL_SIZE[0]}x{THUMBNAIL_SIZE[1]}",
            "-quality",
            "85",
            str(cached_thumbnail),
        ]
        try:
            subprocess.run(command, check=True, stderr=subprocess.PIPE)
        except (subprocess.CalledProcessError, FileNotFoundError):
            command[0] = "convert"
            subprocess.run(command, check=True)

    with Image.open(cached_thumbnail) as source:
        thumbnail = source.convert("RGB")
        dominant_color, color_groups = analyze_colors(thumbnail)
        blur = thumbnail.resize((16, 9), Image.Resampling.BILINEAR)
        blur_buffer = io.BytesIO()
        blur.save(blur_buffer, "WEBP", quality=25, method=4)

    shutil.copy2(cached_thumbnail, output_thumbnail)
    metadata: dict[str, object] = {
        "width": width,
        "height": height,
        "dominantColor": dominant_color,
        "colorGroups": color_groups,
        "blurDataUrl": f"data:image/webp;base64,{base64.b64encode(blur_buffer.getvalue()).decode('ascii')}",
    }
    cached_metadata.parent.mkdir(parents=True, exist_ok=True)
    cached_metadata.write_text(
        json.dumps({"_version": METADATA_VERSION, **metadata}, separators=(",", ":")),
        encoding="utf-8",
    )
    return metadata


def updated_at(relative_path: str, fallback: str) -> str:
    value = run_git("log", "-1", "--format=%cI", "--", relative_path)
    return value or fallback


def display_name(filename: str) -> str:
    value = re.sub(r"[_-]+", " ", Path(filename).stem)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:1].upper() + value[1:]


def write_index(count: int, total_bytes: int, repository_url: str) -> None:
    size = f"{total_bytes / 1024 / 1024:.1f} MB"
    document = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex">
    <title>Wallpaper catalog</title>
    <style>
      :root {{ color-scheme: light dark; font-family: ui-monospace, monospace; }}
      body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; background: Canvas; color: CanvasText; }}
      main {{ width: min(34rem, calc(100% - 3rem)); border-left: 1px solid color-mix(in srgb, CanvasText 25%, transparent); padding: 1.5rem; }}
      p {{ color: color-mix(in srgb, CanvasText 65%, transparent); line-height: 1.6; }}
      a {{ color: inherit; }}
    </style>
  </head>
  <body>
    <main>
      <small>WALLPAPERS // CATALOG</small>
      <h1>Generated wallpaper data</h1>
      <p>{count} tracked images ({size}). This endpoint is generated by GitHub Actions for downstream galleries.</p>
      <p><a href="wallpapers.json">wallpapers.json</a> · <a href="{html.escape(repository_url)}">source repository</a></p>
    </main>
  </body>
</html>
"""
    (OUTPUT_DIR / "index.html").write_text(document, encoding="utf-8")


def write_readme(
    wallpapers: list[dict[str, object]],
    total_bytes: int,
    pages_base_url: str,
) -> None:
    size = f"{total_bytes / 1024 / 1024:.1f} MB"
    lines = [
        "# My Wallpapers",
        "",
        "A curated collection of wallpapers, with lightweight previews generated from the tracked originals by GitHub Actions.",
        "",
        f"[Open the generated catalog]({pages_base_url}/)",
        "",
        f"**{len(wallpapers)} wallpapers · {size}**",
        "",
        "| | | |",
        "|---|---|---|",
    ]

    cells: list[str] = []
    for wallpaper in wallpapers:
        name = html.escape(str(wallpaper["name"]), quote=True).replace("|", "&#124;")
        source_url = html.escape(str(wallpaper["sourceUrl"]), quote=True)
        thumbnail_url = html.escape(str(wallpaper["thumbnailUrl"]), quote=True)
        cells.append(
            f'<a href="{source_url}"><img src="{thumbnail_url}" width="250" alt="{name}"></a>'
        )

    for index in range(0, len(cells), 3):
        row = cells[index : index + 3]
        row.extend([""] * (3 - len(row)))
        lines.append("| " + " | ".join(row) + " |")

    lines.extend(
        [
            "",
            "_Generated automatically from tracked images by the wallpaper catalog workflow._",
            "",
        ]
    )
    (ROOT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if not SOURCE_DIR.is_dir():
        raise SystemExit(f"Missing source directory: {SOURCE_DIR}")

    repository = os.environ.get("GITHUB_REPOSITORY", "hassankhan2608/WALLPAPERS")
    owner, repo = repository.split("/", 1)
    commit_sha = os.environ.get("GITHUB_SHA") or run_git("rev-parse", "HEAD")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    pages_base_url = os.environ.get(
        "PAGES_BASE_URL",
        f"https://{owner.lower()}.github.io/{quote(repo)}",
    ).rstrip("/")
    repository_url = f"https://github.com/{owner}/{repo}"

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    (OUTPUT_DIR / "thumbnails").mkdir(parents=True)

    wallpapers: list[dict[str, object]] = []
    for path in tracked_images():
        relative_path = path.relative_to(ROOT).as_posix()
        encoded_path = quote(relative_path, safe="/")
        blob_sha = run_git("rev-parse", f"HEAD:{relative_path}")
        metadata = process_image(path, blob_sha)
        wallhaven_match = WALLHAVEN_PATTERN.search(path.name)

        wallpapers.append(
            {
                "id": blob_sha,
                "name": display_name(path.name),
                "filename": path.name,
                "path": relative_path,
                "extension": path.suffix.lower().removeprefix("."),
                "size": path.stat().st_size,
                "updatedAt": updated_at(relative_path, generated_at),
                **metadata,
                "thumbnailUrl": f"{pages_base_url}/thumbnails/{blob_sha}.webp",
                "imageUrl": f"https://raw.githubusercontent.com/{owner}/{repo}/{commit_sha}/{encoded_path}",
                "downloadUrl": f"https://github.com/{owner}/{repo}/raw/{commit_sha}/{encoded_path}",
                "sourceUrl": f"{repository_url}/blob/{commit_sha}/{encoded_path}",
                "wallhavenUrl": (
                    f"https://wallhaven.cc/w/{wallhaven_match.group(1)}"
                    if wallhaven_match
                    else None
                ),
            }
        )

    if not wallpapers:
        raise SystemExit("No tracked wallpaper images were found")

    wallpapers.sort(key=lambda item: (str(item["updatedAt"]), str(item["filename"])), reverse=True)
    total_bytes = sum(int(item["size"]) for item in wallpapers)
    catalog = {
        "version": 1,
        "generatedAt": generated_at,
        "source": {
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "commitSha": commit_sha,
            "directory": SOURCE_DIR.relative_to(ROOT).as_posix(),
            "repositoryUrl": repository_url,
        },
        "totalBytes": total_bytes,
        "wallpapers": wallpapers,
    }

    (OUTPUT_DIR / "wallpapers.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_DIR / ".nojekyll").touch()
    write_index(len(wallpapers), total_bytes, repository_url)
    write_readme(wallpapers, total_bytes, pages_base_url)
    print(f"Generated {len(wallpapers)} wallpapers ({total_bytes / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
