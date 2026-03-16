import argparse
from pathlib import Path

from feature_engine import build_time_series
from optical_extractor import compute_optical_indices
from process_month import process_sentinel1_month, process_sentinel2_month


def _parse_band_args(items):
    bands = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"Invalid --band '{item}'. Expected format: BAND_NAME=PATH")
        name, path = item.split("=", 1)
        name = name.strip()
        path = path.strip()
        if not name or not path:
            raise ValueError(f"Invalid --band '{item}'. BAND_NAME and PATH are required.")
        bands[name] = path
    return bands


def main():
    parser = argparse.ArgumentParser(description="GIS pipeline CLI runner.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    s1_parser = subparsers.add_parser("process-s1-month", help="Clip and save one Sentinel-1 month.")
    s1_parser.add_argument("--vv", required=True, help="Path to Sentinel-1 VV raster.")
    s1_parser.add_argument("--vh", required=True, help="Path to Sentinel-1 VH raster.")
    s1_parser.add_argument("--output-dir", required=True, help="Output folder for clipped S1 COGs.")
    s1_parser.add_argument("--aoi", required=True, help="AOI GeoJSON path.")

    s2_parser = subparsers.add_parser("process-s2-month", help="Clip and save one Sentinel-2 month.")
    s2_parser.add_argument(
        "--band",
        action="append",
        default=[],
        help="Band mapping in format BAND_NAME=PATH. Repeat for each band (e.g. --band B04=... --band B08=...).",
    )
    s2_parser.add_argument("--output-dir", required=True, help="Output folder for clipped S2 COGs.")
    s2_parser.add_argument("--aoi", required=True, help="AOI GeoJSON path.")

    features_parser = subparsers.add_parser(
        "build-features", help="Build monthly feature parquet from processed sentinel1/sentinel2 folders."
    )
    features_parser.add_argument(
        "--project-path",
        required=True,
        help="Project root containing sentinel1/<month> and sentinel2/<month> folders.",
    )
    features_parser.add_argument("--aoi", default=None, help="Optional AOI GeoJSON path.")

    args = parser.parse_args()

    if args.command == "process-s1-month":
        process_sentinel1_month(args.vv, args.vh, Path(args.output_dir), args.aoi)
        print(f"Saved Sentinel-1 clipped files in: {args.output_dir}")
        return

    if args.command == "process-s2-month":
        band_map = _parse_band_args(args.band)
        if not band_map:
            raise ValueError("At least one --band BAND_NAME=PATH is required for process-s2-month.")
        process_sentinel2_month(band_map, Path(args.output_dir), args.aoi)
        print(f"Saved Sentinel-2 clipped files in: {args.output_dir}")
        optical = compute_optical_indices(Path(args.output_dir), aoi_path=None)
        print("Optical stats:")
        print(optical)
        return

    if args.command == "build-features":
        df = build_time_series(Path(args.project_path), aoi_path=args.aoi)
        print(df)
        print(f"Saved: {Path(args.project_path) / 'features' / 'features.parquet'}")
        return

    raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()

