#!/usr/bin/env python3
"""Find historical Street View panoramas for each GPS point in a route CSV."""

from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from streetview import search_panoramas


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
        return False
    current = date_key(date_value)
    if before is not None and current >= date_key(before):
        return False
    if after is not None and current < date_key(after):
        return False
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search historical Street View panoramas for a CSV route."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=PROJECT_DIR / "data" / "input" / "route_current_streetview_metadata.csv",
        help="Input CSV containing route GPS points.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_DIR / "outputs" / "from_route_metadata" / "historical_metadata.csv",
        help="Output CSV containing historical panorama candidates.",
    )
    parser.add_argument(
        "--lat-col",
        default="target_lat",
        help="Latitude column in the input CSV.",
    )
    parser.add_argument(
        "--lon-col",
        default="target_lon",
        help="Longitude column in the input CSV.",
    )
    parser.add_argument(
        "--before",
        default="2015-01",
        help="Keep only panoramas before this YYYY-MM date.",
    )
    parser.add_argument(
        "--after",
        default=None,
        help="Keep only panoramas from this YYYY-MM date or later.",
    )
    parser.add_argument(
        "--candidate-limit",
        type=int,
        default=3,
        help="Maximum historical panorama candidates kept for each GPS point.",
    )
    parser.add_argument(
        "--max-points",
        type=int,
        default=0,
        help="Maximum input points to process. 0 means all points.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="Delay in seconds between Google search requests.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.input.open(newline="", encoding="utf-8") as f:
        source_rows = list(csv.DictReader(f))

    if args.max_points > 0:
        source_rows = source_rows[: args.max_points]

    output_rows: list[dict[str, object]] = []
    for source_rank, source in enumerate(source_rows):
        source_index = source.get("index", source_rank)
        lat = float(source[args.lat_col])
        lon = float(source[args.lon_col])
        print(
            f"[{source_rank + 1}/{len(source_rows)}] "
            f"Searching historical panos for source index {source_index}..."
        )

        try:
            panos = search_panoramas(lat, lon)
            panos = [p for p in panos if keep_by_date(p.date, args.before, args.after)]
            panos = sorted(
                panos,
                key=lambda p: (
                    haversine_m(lat, lon, p.lat, p.lon),
                    date_key(p.date),
                    p.pano_id,
                ),
            )
            if args.candidate_limit > 0:
                panos = panos[: args.candidate_limit]

            if not panos:
                output_rows.append(
                    {
                        "source_index": source_index,
                        "source_lat": lat,
                        "source_lon": lon,
                        "source_current_pano_id": source.get("pano_id", ""),
                        "source_current_image_file": source.get("image_file", ""),
                        "candidate_rank": "",
                        "historical_pano_id": "",
                        "historical_date": "",
                        "historical_lat": "",
                        "historical_lon": "",
                        "distance_to_source_m": "",
                        "heading": "",
                        "pitch": "",
                        "roll": "",
                        "search_status": "no_historical_pano",
                        "error": "",
                    }
                )
            else:
                for candidate_rank, pano in enumerate(panos):
                    output_rows.append(
                        {
                            "source_index": source_index,
                            "source_lat": lat,
                            "source_lon": lon,
                            "source_current_pano_id": source.get("pano_id", ""),
                            "source_current_image_file": source.get("image_file", ""),
                            "candidate_rank": candidate_rank,
                            "historical_pano_id": pano.pano_id,
                            "historical_date": pano.date or "",
                            "historical_lat": pano.lat,
                            "historical_lon": pano.lon,
                            "distance_to_source_m": round(
                                haversine_m(lat, lon, pano.lat, pano.lon), 3
                            ),
                            "heading": pano.heading,
                            "pitch": pano.pitch if pano.pitch is not None else "",
                            "roll": pano.roll if pano.roll is not None else "",
                            "search_status": "ok",
                            "error": "",
                        }
                    )
        except Exception as exc:
            output_rows.append(
                {
                    "source_index": source_index,
                    "source_lat": lat,
                    "source_lon": lon,
                    "source_current_pano_id": source.get("pano_id", ""),
                    "source_current_image_file": source.get("image_file", ""),
                    "candidate_rank": "",
                    "historical_pano_id": "",
                    "historical_date": "",
                    "historical_lat": "",
                    "historical_lon": "",
                    "distance_to_source_m": "",
                    "heading": "",
                    "pitch": "",
                    "roll": "",
                    "search_status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

        time.sleep(args.sleep)

    fieldnames = [
        "source_index",
        "source_lat",
        "source_lon",
        "source_current_pano_id",
        "source_current_image_file",
        "candidate_rank",
        "historical_pano_id",
        "historical_date",
        "historical_lat",
        "historical_lon",
        "distance_to_source_m",
        "heading",
        "pitch",
        "roll",
        "search_status",
        "error",
    ]
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    ok_count = sum(1 for row in output_rows if row["search_status"] == "ok")
    no_count = sum(1 for row in output_rows if row["search_status"] == "no_historical_pano")
    err_count = sum(1 for row in output_rows if row["search_status"] == "error")
    print(f"Output: {args.output}")
    print(f"Rows: {len(output_rows)} | ok={ok_count} no_historical={no_count} errors={err_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
