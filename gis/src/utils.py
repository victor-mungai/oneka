from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask


def _default_nodata_for_dtype(dtype):
    np_dtype = np.dtype(dtype)
    if np.issubdtype(np_dtype, np.floating):
        return np.nan
    return 0


def clip_to_aoi(raster_path, aoi_path):
    aoi = gpd.read_file(aoi_path)
    with rasterio.open(raster_path) as src:
        aoi = aoi.to_crs(src.crs)
        nodata_value = src.nodata if src.nodata is not None else _default_nodata_for_dtype(src.dtypes[0])
        clipped, transform = mask(src, aoi.geometry, crop=True, filled=True, nodata=nodata_value)
        profile = src.profile.copy()
        profile.update(
            {
                "height": clipped.shape[1],
                "width": clipped.shape[2],
                "transform": transform,
                "nodata": nodata_value,
            }
        )
    return clipped, profile


def save_cog(output_path, array, profile):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cog_profile = profile.copy()
    cog_profile.update(
        {
            "driver": "GTiff",
            "tiled": True,
            "compress": "deflate",
            "blockxsize": 512,
            "blockysize": 512,
        }
    )

    with rasterio.open(output_path, "w", **cog_profile) as dst:
        dst.write(array)

