from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.mask import mask
from rasterio.vrt import WarpedVRT


def _load_optical_module():
    module_path = Path(__file__).resolve().parents[1] / "optical" / "ndvi-aoi.py"
    spec = spec_from_file_location("optical_ndvi_aoi", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load optical module from: {module_path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _find_band_file(folder_path, band_code):
    band_code = band_code.lower()
    candidates = []
    for p in Path(folder_path).iterdir():
        if not p.is_file():
            continue
        name = p.name.lower()
        if p.suffix.lower() in {".tif", ".tiff", ".jp2"} and band_code in name:
            candidates.append(p)
    if not candidates:
        raise FileNotFoundError(f"Band {band_code.upper()} not found in: {folder_path}")
    return sorted(candidates)[0]


def _compute_index_stats(numerator, denominator, index_name):
    index = np.full(numerator.shape, np.nan, dtype=np.float32)
    valid = (~numerator.mask) & (~denominator.mask) & ((numerator.data + denominator.data) != 0)
    index[valid] = (numerator.data[valid] - denominator.data[valid]) / (
        numerator.data[valid] + denominator.data[valid]
    )
    if np.isnan(index).all():
        raise ValueError(f"No valid {index_name} pixels found.")
    return {
        "mean": float(np.nanmean(index)),
        "min": float(np.nanmin(index)),
        "max": float(np.nanmax(index)),
        "std": float(np.nanstd(index)),
    }


def _compute_optical_indices_from_band_folder(folder_path, aoi_path=None):
    folder_path = Path(folder_path)
    red_path = _find_band_file(folder_path, "b04")
    nir_path = _find_band_file(folder_path, "b08")
    green_path = _find_band_file(folder_path, "b03")
    swir_path = _find_band_file(folder_path, "b11")

    if aoi_path:
        import geopandas as gpd

        aoi = gpd.read_file(aoi_path)
    else:
        aoi = None

    with rasterio.open(nir_path) as nir_src:
        if aoi is not None:
            aoi_on_nir = aoi.to_crs(nir_src.crs)
            nir_masked, _ = mask(nir_src, aoi_on_nir.geometry, crop=True, filled=False)
        else:
            nir_masked = nir_src.read(1, masked=True)[None, ...]

        with rasterio.open(red_path) as red_src:
            if aoi is not None:
                red_masked, _ = mask(red_src, aoi_on_nir.geometry, crop=True, filled=False)
            else:
                red_masked = red_src.read(1, masked=True)[None, ...]

        with rasterio.open(green_path) as green_src:
            if aoi is not None:
                green_masked, _ = mask(green_src, aoi_on_nir.geometry, crop=True, filled=False)
            else:
                green_masked = green_src.read(1, masked=True)[None, ...]

        with rasterio.open(swir_path) as swir_src:
            with WarpedVRT(
                swir_src,
                crs=nir_src.crs,
                transform=nir_src.transform,
                width=nir_src.width,
                height=nir_src.height,
                resampling=Resampling.bilinear,
            ) as swir_on_nir_grid:
                if aoi is not None:
                    swir_masked, _ = mask(swir_on_nir_grid, aoi_on_nir.geometry, crop=True, filled=False)
                else:
                    swir_masked = swir_on_nir_grid.read(1, masked=True)[None, ...]

    red = red_masked[0].astype(np.float32)
    nir = nir_masked[0].astype(np.float32)
    green = green_masked[0].astype(np.float32)
    swir = swir_masked[0].astype(np.float32)

    return {
        "ndvi": _compute_index_stats(nir, red, "NDVI"),
        "ndwi": _compute_index_stats(green, nir, "NDWI"),
        "ndbi": _compute_index_stats(swir, nir, "NDBI"),
        "red_path": str(red_path),
        "nir_path": str(nir_path),
        "green_path": str(green_path),
        "swir_path": str(swir_path),
    }


def compute_optical_indices(safe_folder_path, aoi_path=None):
    folder = Path(safe_folder_path)
    # If this is a monthly processed folder with band files, use direct folder mode.
    has_band_files = any(
        p.is_file() and p.suffix.lower() in {".tif", ".tiff", ".jp2"} for p in folder.iterdir()
    )
    if has_band_files:
        return _compute_optical_indices_from_band_folder(folder, aoi_path=aoi_path)

    # Otherwise, fallback to SAFE-based extraction.
    module = _load_optical_module()
    if aoi_path is None:
        aoi_path = Path(__file__).resolve().parents[1] / "aoi" / "talanta.geojson"
    return module.compute_ndvi_ndwi_ndbi_from_safe(str(safe_folder_path), str(aoi_path))

