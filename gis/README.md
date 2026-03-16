# GIS Pipeline README

This folder contains the AOI-based geospatial pipeline for:
- Sentinel-1 SAR processing (VV, VH, VV-VH)
- Sentinel-2 optical index processing (NDVI, NDWI, NDBI)
- Monthly feature table generation (`features.parquet`)

## Folder Layout

```text
gis/
  aoi/
    talanta.geojson
  optical/
    ndvi-aoi.py
  sar/
    sar_aoi.py
  src/
    cli_runner.py
    feature_engine.py
    process_month.py
    optical_extractor.py
    sar_extractor.py
    utils.py
```

Project data should be organized like:

```text
projects/
  talanta_stadium/
    aoi.geojson
    sentinel1/
      2022-01/
      2022-02/
      ...
    sentinel2/
      2022-01/
      2022-02/
      ...
    features/
      features.parquet
```

## Setup

From repo root:

```bash
pip install -r gis/requirements.txt
```

## Execution Order

1. Process Sentinel-1 for a month (`process-s1-month`)
2. Process Sentinel-2 for the same month (`process-s2-month`)
3. Repeat for all months
4. Build feature table once (`build-features`)

## Run Commands

Change directory first:

```bash
cd gis/src
```

### 1) Process one Sentinel-1 month

```bash
python cli_runner.py process-s1-month \
  --vv "projects/talanta_stadium/raw/sentinel1/YYYY-MM/vv.tif" \
  --vh "projects/talanta_stadium/raw/sentinel1/YYYY-MM/vh.tif" \
  --output-dir "projects/talanta_stadium/sentinel1/YYYY-MM" \
  --aoi "projects/talanta_stadium/aoi.geojson"
```

### 2) Process one Sentinel-2 month

```bash
python cli_runner.py process-s2-month \
  --band B03="projects/talanta_stadium/raw/sentinel2/YYYY-MM/B03.jp2" \
  --band B04="projects/talanta_stadium/raw/sentinel2/YYYY-MM/B04.jp2" \
  --band B08="projects/talanta_stadium/raw/sentinel2/YYYY-MM/B08.jp2" \
  --band B11="projects/talanta_stadium/raw/sentinel2/YYYY-MM/B11.jp2" \
  --output-dir "projects/talanta_stadium/sentinel2/YYYY-MM" \
  --aoi "projects/talanta_stadium/aoi.geojson"
```

### 3) Build final monthly features table

```bash
python cli_runner.py build-features --project-path "projects/talanta_stadium"
```

Output:

```text
projects/talanta_stadium/features/features.parquet
```

## Notes

- SAR conversion is deterministic and hard-coded as linear -> dB:
  - `sigma0 = raw / 10000.0`
  - `sigma0_db = 10 * log10(sigma0)` for `sigma0 > 0`
- If Sentinel-1 TIFF CRS is missing, the SAR pipeline uses GCP georeferencing when present.
- `build-features` uses `project_path/aoi.geojson` by default unless `--aoi` is explicitly passed.
