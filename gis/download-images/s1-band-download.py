import argparse
import json
from datetime import datetime, timedelta, timezone
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


def _normalize_date(value):
    value = value.strip()
    if len(value) == 8 and value.isdigit():
        return datetime.strptime(value, "%Y%m%d").strftime("%Y-%m-%d")
    return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")


def _find_asset_key(item, key):
    if key in item.assets:
        return key
    key_lower = key.lower()
    for name in item.assets:
        if name.lower() == key_lower:
            return name
    return None


def _get_signed_asset_href(item, asset_key):
    signed_item = planetary_computer.sign(item)
    asset = signed_item.assets.get(asset_key)
    if asset is None:
        raise KeyError(
            f"Asset '{asset_key}' missing after signing for item '{item.id}'. "
            f"Available assets: {', '.join(sorted(signed_item.assets.keys()))}"
        )
    return asset.href


def _search_items(client, collection, geometry, start_date, end_date):
    search = client.search(
        collections=[collection],
        intersects=geometry,
        datetime=f"{start_date}/{end_date}",
    )
    return list(search.items())


def _parse_item_time(item):
    value = item.properties.get("datetime")
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _rank_items(items, prefer, start_date, end_date):
    if prefer == "earliest":
        return sorted(items, key=_parse_item_time)
    if prefer == "latest":
        return sorted(items, key=_parse_item_time, reverse=True)

    # closest to center of requested period
    start_dt = datetime.fromisoformat(f"{start_date}T00:00:00+00:00")
    end_dt = datetime.fromisoformat(f"{end_date}T00:00:00+00:00")
    mid = start_dt + (end_dt - start_dt) / 2
    return sorted(items, key=lambda i: abs((_parse_item_time(i) - mid).total_seconds()))


def download_s1_vv_vh(
    aoi_path,
    output_dir,
    start_date,
    end_date,
    top_n=1,
    collection="sentinel-1-rtc",
    expand_days=10,
    prefer="closest",
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
    items = _search_items(client, collection, geometry, start_date, end_date)

    if not items and expand_days > 0:
        expanded_start = (start_dt - timedelta(days=expand_days)).strftime("%Y-%m-%d")
        expanded_end = (end_dt + timedelta(days=expand_days)).strftime("%Y-%m-%d")
        items = _search_items(client, collection, geometry, expanded_start, expanded_end)
        if items:
            print(
                f"No scenes in requested range {start_date}..{end_date}; "
                f"using expanded range {expanded_start}..{expanded_end}."
            )

    if not items:
        raise ValueError(
            f"No Sentinel-1 scenes found for AOI/date range. "
            f"collection={collection}, dates={start_date}..{end_date}."
        )

    ranked = _rank_items(items, prefer=prefer, start_date=start_date, end_date=end_date)

    valid = []
    for item in ranked:
        vv_key = _find_asset_key(item, "vv")
        vh_key = _find_asset_key(item, "vh")
        if vv_key is not None and vh_key is not None:
            valid.append((item, vv_key, vh_key))
        if len(valid) >= top_n:
            break

    if not valid:
        sample_assets = ", ".join(sorted(ranked[0].assets.keys()))
        raise ValueError(
            "Found Sentinel-1 scenes, but none expose both VV and VH assets. "
            f"First scene assets: {sample_assets}"
        )

    for idx, (item, vv_key, vh_key) in enumerate(valid, start=1):
        scene_time = item.properties.get("datetime", "unknown-time")
        scene_dir = output_dir / f"{idx:02d}_{item.id}"
        scene_dir.mkdir(parents=True, exist_ok=True)
        print(f"Scene {idx}: {item.id} ({scene_time})")

        vv_out = scene_dir / "vv.tif"
        print(f"  Downloading {vv_key} -> {vv_out}")
        download_with_url_provider(
            output_path=vv_out,
            url_provider=lambda i=item, k=vv_key: _get_signed_asset_href(i, k),
            label=f"{item.id}:vv",
            max_retries=download_retries,
            retry_backoff_seconds=retry_backoff_seconds,
        )

        vh_out = scene_dir / "vh.tif"
        print(f"  Downloading {vh_key} -> {vh_out}")
        download_with_url_provider(
            output_path=vh_out,
            url_provider=lambda i=item, k=vh_key: _get_signed_asset_href(i, k),
            label=f"{item.id}:vh",
            max_retries=download_retries,
            retry_backoff_seconds=retry_backoff_seconds,
        )


def main():
    parser = argparse.ArgumentParser(
        description="Download Sentinel-1 VV/VH assets using STAC (Planetary Computer)."
    )
    parser.add_argument("--aoi", required=True, help="AOI GeoJSON path.")
    parser.add_argument("--output-dir", required=True, help="Output directory.")
    parser.add_argument("--start-date", required=True, help="Start date YYYY-MM-DD or YYYYMMDD.")
    parser.add_argument("--end-date", required=True, help="End date YYYY-MM-DD or YYYYMMDD.")
    parser.add_argument(
        "--top-n",
        type=int,
        default=1,
        help="Number of scenes to download (default: 1).",
    )
    parser.add_argument(
        "--collection",
        default="sentinel-1-rtc",
        help="STAC collection name (default: sentinel-1-rtc).",
    )
    parser.add_argument(
        "--expand-days",
        type=int,
        default=10,
        help="If no scenes are found, expand both sides of date range by this many days (default: 10).",
    )
    parser.add_argument(
        "--prefer",
        choices=["closest", "latest", "earliest"],
        default="closest",
        help="How to rank scenes in the date window (default: closest).",
    )
    parser.add_argument(
        "--download-retries",
        type=int,
        default=3,
        help="Number of download retries per asset (default: 3).",
    )
    parser.add_argument(
        "--retry-backoff-seconds",
        type=int,
        default=2,
        help="Seconds to wait between asset download retries (default: 2).",
    )
    args = parser.parse_args()

    download_s1_vv_vh(
        aoi_path=args.aoi,
        output_dir=args.output_dir,
        start_date=args.start_date,
        end_date=args.end_date,
        top_n=args.top_n,
        collection=args.collection,
        expand_days=args.expand_days,
        prefer=args.prefer,
        download_retries=args.download_retries,
        retry_backoff_seconds=args.retry_backoff_seconds,
    )


if __name__ == "__main__":
    main()
