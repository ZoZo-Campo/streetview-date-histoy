#!/usr/bin/env python3
"""Search and optionally download historical Google Street View panoramas.

This script is intentionally small and practical:
- query one GPS point;
- list available panorama dates;
- save metadata to CSV;
- optionally download full panorama images.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from streetview import (
    crop_bottom_and_right_black_border,
    get_panorama,
    get_streetview,
    search_panoramas,
)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    return 2.0 * radius_m * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def date_key(date_value: str | None) -> tuple[int, int]:
    if not date_value:
        return (9999, 99)
    year, month = date_value.split("-")
    return (int(year), int(month))


def keep_by_date(date_value: str | None, before: str | None, after: str | None) -> bool:
    if not date_value:
        return before is None and after is None
    current = date_key(date_value)
    if before is not None and current >= date_key(before):
        return False
    if after is not None and current < date_key(after):
        return False
    return True


def write_metadata(rows: list[dict[str, object]], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "rank",
        "pano_id",
        "date",
        "lat",
        "lon",
        "distance_to_query_m",
        "heading",
        "pitch",
        "roll",
        "elevation",
        "image_path",
        "download_error",
    ]
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search and optionally download historical Google Street View panoramas."
    )
    parser.add_argument("--lat", type=float, required=True, help="Query latitude.")
    parser.add_argument("--lon", type=float, required=True, help="Query longitude.")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_DIR / "outputs" / "historical_streetview",
        help="Output directory for metadata and images.",
    )
    parser.add_argument(
        "--before",
        type=str,
        default=None,
        help="Keep only panoramas before this YYYY-MM date, for example 2015-01.",
    )
    parser.add_argument(
        "--after",
        type=str,
        default=None,
        help="Keep only panoramas from this YYYY-MM date or later.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of panoramas to keep after filtering.",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download full panorama JPG files. Without this flag, only metadata is saved.",
    )
    parser.add_argument(
        "--download-mode",
        choices=("panorama", "static"),
        default="panorama",
        help=(
            "panorama downloads full 360 tile panoramas without an API key when Google allows it. "
            "static uses the official Street View image API and requires a Google Maps API key."
        ),
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.environ.get("GOOGLE_MAPS_API_KEY", ""),
        help="Google Maps API key for --download-mode static. Defaults to GOOGLE_MAPS_API_KEY.",
    )
    parser.add_argument("--width", type=int, default=640, help="Static API image width.")
    parser.add_argument("--height", type=int, default=640, help="Static API image height.")
    parser.add_argument("--heading", type=int, default=None, help="Static API heading.")
    parser.add_argument("--fov", type=int, default=100, help="Static API field of view.")
    parser.add_argument("--pitch", type=int, default=0, help="Static API pitch.")
    parser.add_argument(
        "--zoom",
        type=int,
        default=3,
        choices=range(1, 6),
        metavar="1-5",
        help="Panorama zoom level. 3 is a good quick test; 5 is much larger.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        help="Delay in seconds between panorama downloads.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    image_dir = args.output / "images"
    if args.download:
        image_dir.mkdir(parents=True, exist_ok=True)
        if args.download_mode == "static" and not args.api_key:
            raise SystemExit(
                "--download-mode static requires --api-key or GOOGLE_MAPS_API_KEY."
            )

    print(f"Searching panoramas near lat={args.lat}, lon={args.lon}")
    panos = search_panoramas(args.lat, args.lon)
    panos = [p for p in panos if keep_by_date(p.date, args.before, args.after)]
    panos = sorted(panos, key=lambda p: (date_key(p.date), p.pano_id))
    if args.limit > 0:
        panos = panos[: args.limit]

    rows: list[dict[str, object]] = []
    for rank, pano in enumerate(panos):
        image_path = ""
        download_error = ""
        if args.download:
            filename = f"{rank:03d}_{pano.date or 'unknown'}_{pano.pano_id}.jpg"
            safe_filename = filename.replace("/", "_").replace(":", "_")
            output_image = image_dir / safe_filename
            print(f"Downloading {rank + 1}/{len(panos)}: {pano.date} {pano.pano_id}")
            try:
                if args.download_mode == "static":
                    image = get_streetview(
                        pano_id=pano.pano_id,
                        api_key=args.api_key,
                        width=args.width,
                        height=args.height,
                        heading=args.heading if args.heading is not None else int(pano.heading),
                        fov=args.fov,
                        pitch=args.pitch,
                    )
                else:
                    image = get_panorama(pano.pano_id, zoom=args.zoom, multi_threaded=False)
                    image = crop_bottom_and_right_black_border(image)
                image.save(output_image, "jpeg", quality=92)
                image_path = str(output_image)
                time.sleep(args.sleep)
            except Exception as exc:
                download_error = f"{type(exc).__name__}: {exc}"
                print(f"Download failed for {pano.pano_id}: {download_error}")

        rows.append(
            {
                "rank": rank,
                "pano_id": pano.pano_id,
                "date": pano.date or "",
                "lat": pano.lat,
                "lon": pano.lon,
                "distance_to_query_m": round(
                    haversine_m(args.lat, args.lon, pano.lat, pano.lon), 3
                ),
                "heading": pano.heading,
                "pitch": pano.pitch if pano.pitch is not None else "",
                "roll": pano.roll if pano.roll is not None else "",
                "elevation": pano.elevation if pano.elevation is not None else "",
                "image_path": image_path,
                "download_error": download_error,
            }
        )

    metadata_csv = args.output / "metadata.csv"
    write_metadata(rows, metadata_csv)

    print(f"Found {len(rows)} panorama(s).")
    print(f"Metadata: {metadata_csv}")
    if args.download:
        print(f"Images: {image_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
