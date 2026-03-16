# Download Images (STAC)

This folder contains download scripts for fetching only required Sentinel assets using STAC (Planetary Computer).

## Scripts

- `stac-band-download.py`: Sentinel-2 band download (`B03`, `B04`, `B08`, `B11` by default)
- `s1-band-download.py`: Sentinel-1 SAR download (`vv.tif`, `vh.tif`)
- `download_utils.py`: shared resilient downloader (progress, retries, `.part` safety)

## Setup

From repo root:

```bash
pip install -r gis/requirements.txt
```

## Sentinel-2 Download

Downloads lowest-cloud scene(s) in AOI/date range and only requested bands.

```bash
python gis/download-images/stac-band-download.py \
  --aoi projects/atlanta_stadium/aoi.geojson \
  --output-dir projects/atlanta_stadium/raw/sentinel2/2024-01 \
  --start-date 2022-01-01 \
  --end-date 2022-01-31 \
  --max-cloud 20 \
  --bands B03 B04 B08 B11 \
  --top-n 1
```

Optional resilience flags:

- `--download-retries` (default `3`)
- `--retry-backoff-seconds` (default `2`)
- `--expand-days` (default `10`)

## Sentinel-1 Download

Downloads Sentinel-1 scene(s) and saves only `vv.tif` and `vh.tif`.

```bash
python gis/download-images/s1-band-download.py \
  --aoi projects/atlanta_stadium/aoi.geojson \
  --output-dir projects/atlanta_stadium/raw/sentinel1/2024-01 \
  --start-date 2024-01-01 \
  --end-date 2024-01-31 \
  --top-n 1 \
  --prefer closest
```

Optional resilience flags:

- `--download-retries` (default `3`)
- `--retry-backoff-seconds` (default `2`)
- `--expand-days` (default `10`)

## Output Structure

Both scripts write scene folders under `--output-dir`:

```text
<output-dir>/
  01_<scene_id>/
    # S2:
    B03.tif
    B04.tif
    B08.tif
    B11.tif
    # S1:
    vv.tif
    vh.tif
```

## Reliability Notes

- Signed URLs are refreshed per attempt (prevents stale SAS retry loops).
- Downloads are written to `*.part` first, then atomically renamed on success.
- If retries are exhausted, the run fails (no silent skip).

