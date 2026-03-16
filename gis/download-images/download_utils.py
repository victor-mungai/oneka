import time
from pathlib import Path

import requests


def _format_mb(num_bytes):
    return f"{num_bytes / (1024 * 1024):.1f}MB"


def _stream_download(url, output_tmp_path, timeout=(20, 300), progress_step_mb=5):
    progress_step = progress_step_mb * 1024 * 1024
    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        next_log = progress_step
        start = time.time()

        with open(output_tmp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if downloaded >= next_log:
                    if total > 0:
                        pct = (downloaded / total) * 100
                        print(f"    {_format_mb(downloaded)} / {_format_mb(total)} ({pct:.1f}%)")
                    else:
                        print(f"    {_format_mb(downloaded)} downloaded")
                    next_log += progress_step

        elapsed = time.time() - start
        print(f"    Completed in {elapsed:.1f}s")


def download_with_url_provider(
    output_path,
    url_provider,
    label,
    max_retries=3,
    retry_backoff_seconds=2,
    timeout=(20, 300),
):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = Path(str(output_path) + ".part")

    last_err = None
    for attempt in range(1, max_retries + 1):
        if tmp_path.exists():
            tmp_path.unlink()

        url = url_provider()
        try:
            _stream_download(url, tmp_path, timeout=timeout)
            tmp_path.replace(output_path)
            return
        except requests.RequestException as err:
            last_err = err
            status = err.response.status_code if getattr(err, "response", None) is not None else None
            reason = f"HTTP {status}" if status is not None else err.__class__.__name__
            print(f"    Attempt {attempt}/{max_retries} failed for {label} ({reason}).")
            if attempt < max_retries:
                print("    Refreshing signed URL and retrying...")
                time.sleep(retry_backoff_seconds)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    raise RuntimeError(f"Failed to download {label} after {max_retries} attempts.") from last_err

