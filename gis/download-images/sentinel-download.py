import argparse
from pathlib import Path

from sentinelsat import SentinelAPI, geojson_to_wkt, read_geojson


def _query_lowest_cloud_product(
    api,
    footprint,
    start_date,
    end_date,
    cloud_cover_max,
    platform,
    processing_level,
):
    products = api.query(
        footprint,
        date=(start_date, end_date),
        platformname=platform,
        processinglevel=processing_level,
        cloudcoverpercentage=(0, cloud_cover_max),
    )

    if not products:
        return None, None

    products_df = api.to_dataframe(products)
    best_row = products_df.sort_values("cloudcoverpercentage", ascending=True).head(1)
    best_id = best_row.index[0]
    best_cloud = float(best_row.iloc[0]["cloudcoverpercentage"])
    return best_id, best_cloud


def download_lowest_cloud_per_aoi(
    username,
    password,
    aoi_geojson_path,
    output_dir,
    start_date,
    end_date,
    cloud_cover_max=20,
    api_url="https://scihub.copernicus.eu/apihub",
    platform="Sentinel-2",
    processing_level="Level-2A",
):
    api = SentinelAPI(username, password, api_url)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    geojson = read_geojson(str(aoi_geojson_path))
    features = geojson.get("features", [])
    if not features:
        raise ValueError(f"No features found in AOI file: {aoi_geojson_path}")

    for idx, geometry in enumerate(features, start=1):
        footprint = geojson_to_wkt(geometry)
        best_id, best_cloud = _query_lowest_cloud_product(
            api,
            footprint,
            start_date,
            end_date,
            cloud_cover_max,
            platform,
            processing_level,
        )

        if best_id is None:
            print(
                f"[AOI {idx}] No products found for {start_date} to {end_date} "
                f"with cloud cover <= {cloud_cover_max}%."
            )
            continue

        print(
            f"[AOI {idx}] Downloading lowest-cloud product {best_id} "
            f"(cloud cover: {best_cloud:.2f}%)."
        )
        api.download(best_id, directory_path=str(output_dir))


def main():
    parser = argparse.ArgumentParser(
        description="Download lowest-cloud Sentinel products for AOI(s) in a date range."
    )
    parser.add_argument("--username", required=True, help="Copernicus SciHub username.")
    parser.add_argument("--password", required=True, help="Copernicus SciHub password.")
    parser.add_argument("--aoi", required=True, help="Path to AOI GeoJSON file.")
    parser.add_argument("--output-dir", required=True, help="Download output directory.")
    parser.add_argument("--start-date", required=True, help="Start date (YYYYMMDD).")
    parser.add_argument("--end-date", required=True, help="End date (YYYYMMDD).")
    parser.add_argument(
        "--cloud-cover-max",
        type=float,
        default=20,
        help="Maximum cloud cover percent for query filtering (default: 20).",
    )
    parser.add_argument(
        "--api-url",
        default="https://scihub.copernicus.eu/apihub",
        help="Sentinel API base URL.",
    )
    parser.add_argument(
        "--platform",
        default="Sentinel-2",
        help="Platform name for query (default: Sentinel-2).",
    )
    parser.add_argument(
        "--processing-level",
        default="Level-2A",
        help="Processing level for query (default: Level-2A).",
    )
    args = parser.parse_args()

    download_lowest_cloud_per_aoi(
        username=args.username,
        password=args.password,
        aoi_geojson_path=args.aoi,
        output_dir=args.output_dir,
        start_date=args.start_date,
        end_date=args.end_date,
        cloud_cover_max=args.cloud_cover_max,
        api_url=args.api_url,
        platform=args.platform,
        processing_level=args.processing_level,
    )


if __name__ == "__main__":
    main()

