import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import planetary_computer
from pystac_client import Client

from download_utils import download_with_url_provider


PC_STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"


def _load_first_geometry(aoi_path):
    with open(aoi_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("type") == "FeatureCollection":
        features = data.get("features", [])
        if not features:
            raise ValueError(f"No features found in AOI file: {aoi_path}")
        return features[0]["geometry"]

    if data.get("type") == "Feature":
        return data["geometry"]

    if data.get("type") in {"Polygon", "MultiPolygon"}:
        return data

    raise ValueError(f"Unsupported AOI GeoJSON type: {data.get('type')}")


def _cloud_value(item):
    props = item.properties or {}
    cloud = props.get("eo:cloud_cover")
    if cloud is None:
        cloud = props.get("s2:cloud_cover")
    if cloud is None:
        return 10_000.0
    return float(cloud)


def _normalize_date(value):
    value = value.strip()
    if len(value) == 8 and value.isdigit():
        return datetime.strptime(value, "%Y%m%d").strftime("%Y-%m-%d")
    return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")


def _search_items(client, collection, geometry, start_date, end_date, max_cloud):
    fallback_search = client.search(
        collections=[collection],
        intersects=geometry,
        datetime=f"{start_date}/{end_date}",
    )
    all_items = list(fallback_search.items())
    filtered = [item for item in all_items if _cloud_value(item) <= max_cloud]
    return all_items, filtered


def _resolve_asset_key(item, requested_band):
    if requested_band in item.assets:
        return requested_band
    requested_lower = requested_band.lower()
    for key in item.assets:
        if key.lower() == requested_lower:
            return key
    raise KeyError(
        f"Band asset '{requested_band}' not available for item '{item.id}'. "
        f"Available assets: {', '.join(sorted(item.assets.keys()))}"
    )


def _get_signed_asset_href(item, asset_key):
    signed_item = planetary_computer.sign(item)
    asset = signed_item.assets.get(asset_key)
    if asset is None:
        raise KeyError(
            f"Band asset '{asset_key}' missing after signing for item '{item.id}'. "
            f"Available assets: {', '.join(sorted(signed_item.assets.keys()))}"
        )
    return asset.href


def download_lowest_cloud_bands(
    aoi_path,
    output_dir,
    start_date,
    end_date,
    bands,
    max_cloud=20.0,
    top_n=1,
    collection="sentinel-2-l2a",
    expand_days=0,
    download_retries=3,
    retry_backoff_seconds=2,
):
    start_date = _normalize_date(start_date)
    end_date = _normalize_date(end_date)
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    if end_dt < start_dt:
        raise ValueError("end-date must be on or after start-date.")

    geometry = _load_first_geometry(aoi_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    client = Client.open(PC_STAC_URL)
    all_items, filtered_items = _search_items(
        client, collection, geometry, start_date, end_date, max_cloud
    )
    items = filtered_items
    if not items:
        if expand_days > 0:
            expanded_start = (start_dt - timedelta(days=expand_days)).strftime("%Y-%m-%d")
            expanded_end = (end_dt + timedelta(days=expand_days)).strftime("%Y-%m-%d")
            all_items, filtered_items = _search_items(
                client, collection, geometry, expanded_start, expanded_end, max_cloud
            )
            items = filtered_items
            if all_items:
                print(
                    f"No scenes in requested range {start_date}..{end_date}; "
                    f"using expanded range {expanded_start}..{expanded_end}."
                )

    if not items:
        if all_items:
            print(
                f"No scenes met max_cloud={max_cloud}%. "
                f"Falling back to lowest-cloud available scene out of {len(all_items)} result(s)."
            )
            items = all_items
        else:
            raise ValueError(
                f"No scenes found for AOI/date range. "
                f"collection={collection}, dates={start_date}..{end_date}."
            )

    selected = sorted(items, key=_cloud_value)[:top_n]

    for idx, item in enumerate(selected, start=1):
        cloud = _cloud_value(item)
        scene_dir = output_dir / f"{idx:02d}_{item.id}"
        scene_dir.mkdir(parents=True, exist_ok=True)

        print(f"Scene {idx}: {item.id} (cloud={cloud:.2f}%)")

        for band in bands:
            asset_key = _resolve_asset_key(item, band)
            out_path = scene_dir / f"{band}.tif"
            print(f"  Downloading {band} -> {out_path}")
            download_with_url_provider(
                output_path=out_path,
                url_provider=lambda i=item, k=asset_key: _get_signed_asset_href(i, k),
                label=f"{item.id}:{band}",
                max_retries=download_retries,
                retry_backoff_seconds=retry_backoff_seconds,
            )


def main():
    parser = argparse.ArgumentParser(
        description="Download only required Sentinel band assets using STAC (Planetary Computer)."
    )
    parser.add_argument("--aoi", required=True, help="AOI GeoJSON path.")
    parser.add_argument("--output-dir", required=True, help="Output directory.")
    parser.add_argument("--start-date", required=True, help="Start date YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="End date YYYY-MM-DD.")
    parser.add_argument(
        "--bands",
        nargs="+",
        default=["B03", "B04", "B08", "B11"],
        help="Band asset keys to download (default: B03 B04 B08 B11).",
    )
    parser.add_argument(
        "--max-cloud",
        type=float,
        default=20.0,
        help="Maximum cloud cover percentage (default: 20).",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=1,
        help="Number of lowest-cloud scenes to download (default: 1).",
    )
    parser.add_argument(
        "--collection",
        default="sentinel-2-l2a",
        help="STAC collection name (default: sentinel-2-l2a).",
    )
    parser.add_argument(
        "--expand-days",
        type=int,
        default=10,
        help=(
            "If no scenes are found, expand both sides of the date range by this many days "
            "and retry (default: 10)."
        ),
    )
    parser.add_argument(
        "--download-retries",
        type=int,
        default=3,
        help="Number of download retries per band (default: 3).",
    )
    parser.add_argument(
        "--retry-backoff-seconds",
        type=int,
        default=2,
        help="Seconds to wait between band download retries (default: 2).",
    )
    args = parser.parse_args()

    download_lowest_cloud_bands(
        aoi_path=args.aoi,
        output_dir=args.output_dir,
        start_date=args.start_date,
        end_date=args.end_date,
        bands=args.bands,
        max_cloud=args.max_cloud,
        top_n=args.top_n,
        collection=args.collection,
        expand_days=args.expand_days,
        download_retries=args.download_retries,
        retry_backoff_seconds=args.retry_backoff_seconds,
    )


if __name__ == "__main__":
    main()
