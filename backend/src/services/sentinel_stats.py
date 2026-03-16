"""
Sentinel Hub Statistical API integration.
"""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List

import requests

from src.config import settings


_TOKEN_CACHE: Dict[str, Any] = {
    "token": None,
    "expires_at": None,
}


S2_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B03", "B04", "B08", "B11", "dataMask"] }],
    output: [
      { id: "ndvi", bands: 1, sampleType: "FLOAT32" },
      { id: "ndwi", bands: 1, sampleType: "FLOAT32" },
      { id: "ndbi", bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1 }
    ]
  };
}

function evaluatePixel(samples) {
  var denomNdvi = samples.B08 + samples.B04;
  var denomNdwi = samples.B03 + samples.B08;
  var denomNdbi = samples.B11 + samples.B08;
  var valid = denomNdvi !== 0 && denomNdwi !== 0 && denomNdbi !== 0;

  var ndvi = valid ? (samples.B08 - samples.B04) / denomNdvi : 0;
  var ndwi = valid ? (samples.B03 - samples.B08) / denomNdwi : 0;
  var ndbi = valid ? (samples.B11 - samples.B08) / denomNdbi : 0;

  return {
    ndvi: [ndvi],
    ndwi: [ndwi],
    ndbi: [ndbi],
    dataMask: [samples.dataMask * (valid ? 1 : 0)]
  };
}
"""


S1_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["VV", "VH", "dataMask"] }],
    output: [
      { id: "vv", bands: 1, sampleType: "FLOAT32" },
      { id: "vh", bands: 1, sampleType: "FLOAT32" },
      { id: "vv_vh_ratio", bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1 }
    ]
  };
}

function evaluatePixel(samples) {
  var valid = samples.VV > 0 && samples.VH > 0;
  var vvDb = valid ? 10 * Math.log(samples.VV) / Math.LN10 : 0;
  var vhDb = valid ? 10 * Math.log(samples.VH) / Math.LN10 : 0;
  var ratio = vvDb - vhDb;

  return {
    vv: [vvDb],
    vh: [vhDb],
    vv_vh_ratio: [ratio],
    dataMask: [samples.dataMask * (valid ? 1 : 0)]
  };
}
"""


def _get_access_token() -> str:
    if not settings.sentinelhub_client_id or not settings.sentinelhub_client_secret:
        raise RuntimeError("Sentinel Hub credentials are not configured.")

    now = datetime.utcnow()
    token = _TOKEN_CACHE.get("token")
    expires_at = _TOKEN_CACHE.get("expires_at")
    if token and expires_at and now < expires_at:
        return token

    response = requests.post(
        settings.sentinelhub_token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": settings.sentinelhub_client_id,
            "client_secret": settings.sentinelhub_client_secret,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError("Failed to obtain Sentinel Hub access token.")

    expires_in = int(payload.get("expires_in", 3600))
    _TOKEN_CACHE["token"] = access_token
    _TOKEN_CACHE["expires_at"] = now + timedelta(seconds=max(expires_in - 60, 60))

    return access_token


def _build_stats_request(
    geometry_geojson: Dict[str, Any],
    start_date: date,
    end_date: date,
    evalscript: str,
    data_type: str,
) -> Dict[str, Any]:
    return {
        "input": {
            "bounds": {
                "geometry": geometry_geojson,
                "properties": {
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/4326"
                },
            },
            "data": [{"type": data_type}],
        },
        "aggregation": {
            "timeRange": {
                "from": f"{start_date.isoformat()}T00:00:00Z",
                "to": f"{end_date.isoformat()}T23:59:59Z",
            },
            "aggregationInterval": {"of": "P1M"},
            "evalscript": evalscript,
            "resx": 10,
            "resy": 10,
            "lastIntervalBehavior": "SHORTEN",
        },
    }


def _fetch_stats(payload: Dict[str, Any]) -> Dict[str, Any]:
    token = _get_access_token()
    base_url = (settings.sentinelhub_base_url or "https://services.sentinel-hub.com").rstrip("/")
    url = f"{base_url}/api/v1/statistics"
    response = requests.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def _parse_interval_date(interval_from: str) -> date:
    return datetime.fromisoformat(interval_from.replace("Z", "+00:00")).date()


def _extract_means(response: Dict[str, Any], output_id: str) -> Dict[date, float | None]:
    results: Dict[date, float | None] = {}
    for entry in response.get("data", []):
        interval = entry.get("interval", {})
        interval_from = interval.get("from")
        if not interval_from:
            continue
        month_date = _parse_interval_date(interval_from)
        stats = (
            entry.get("outputs", {})
            .get(output_id, {})
            .get("bands", {})
            .get("B0", {})
            .get("stats", {})
        )
        results[month_date] = stats.get("mean")
    return results


def compute_monthly_features(
    geometry_geojson: Dict[str, Any],
    start_date: date,
    end_date: date,
) -> List[Dict[str, Any]]:
    s2_request = _build_stats_request(
        geometry_geojson,
        start_date,
        end_date,
        S2_EVALSCRIPT,
        "sentinel-2-l2a",
    )
    s1_request = _build_stats_request(
        geometry_geojson,
        start_date,
        end_date,
        S1_EVALSCRIPT,
        "sentinel-1-grd",
    )

    s2_response = _fetch_stats(s2_request)
    s1_response = _fetch_stats(s1_request)

    ndvi = _extract_means(s2_response, "ndvi")
    ndwi = _extract_means(s2_response, "ndwi")
    ndbi = _extract_means(s2_response, "ndbi")
    vv = _extract_means(s1_response, "vv")
    vh = _extract_means(s1_response, "vh")
    ratio = _extract_means(s1_response, "vv_vh_ratio")

    all_dates = sorted(set(ndvi) | set(ndwi) | set(ndbi) | set(vv) | set(vh) | set(ratio))

    results: List[Dict[str, Any]] = []
    for month_date in all_dates:
        results.append(
            {
                "date": month_date,
                "ndvi_mean": ndvi.get(month_date),
                "ndwi_mean": ndwi.get(month_date),
                "ndbi_mean": ndbi.get(month_date),
                "vv_mean": vv.get(month_date),
                "vh_mean": vh.get(month_date),
                "vv_vh_ratio": ratio.get(month_date),
            }
        )

    return results
