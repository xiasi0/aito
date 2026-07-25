from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .const import DEFAULT_USER_AGENT

ResourceDownloader = Callable[[str, Path], None]


class AitoResourceError(RuntimeError):
    pass


def cache_vehicle_resources(
    storage_root: str | Path,
    asset_key: str,
    manifests: Mapping[str, Mapping[str, Any]],
    *,
    downloader: ResourceDownloader | None = None,
) -> dict[str, dict[str, str | None]]:
    """Download each declared resource archive once using normal HTTPS validation."""
    account_dir = Path(storage_root) / _safe_path_part(asset_key)
    download = downloader or _download_https_resource
    created_files: list[Path] = []
    cached: dict[str, dict[str, str | None]] = {}
    try:
        for vehicle_id, manifest in manifests.items():
            resource_url = _required_https_url(manifest.get("resourceFile"))
            resource_sign = _required_value(manifest.get("resourceSign"), "resource signature")
            vehicle_dir = account_dir / _safe_path_part(vehicle_id)
            archive = vehicle_dir / f"{_safe_path_part(resource_sign)}.zip"
            if not archive.is_file() or archive.stat().st_size == 0:
                vehicle_dir.mkdir(parents=True, exist_ok=True)
                temporary = archive.with_suffix(".part")
                try:
                    download(resource_url, temporary)
                    if not temporary.is_file() or temporary.stat().st_size == 0:
                        raise AitoResourceError("resource archive is empty")
                    os.replace(temporary, archive)
                    created_files.append(archive)
                finally:
                    temporary.unlink(missing_ok=True)
            cached[str(vehicle_id)] = {
                "resourceVersion": _optional_value(manifest.get("resourceVersion")),
                "resourceSign": resource_sign,
                "versionName": _optional_value(manifest.get("versionName")),
                "archive": archive.relative_to(account_dir).as_posix(),
            }
        _remove_stale_archives(account_dir, cached)
    except Exception as error:
        for archive in created_files:
            archive.unlink(missing_ok=True)
        if isinstance(error, AitoResourceError):
            raise
        raise AitoResourceError("vehicle resource download failed") from error
    return cached


def remove_vehicle_resources(storage_root: str | Path, asset_key: str) -> None:
    root = Path(storage_root).resolve()
    account_dir = (root / _safe_path_part(asset_key)).resolve()
    if account_dir.parent != root:
        raise AitoResourceError("invalid resource storage path")
    shutil.rmtree(account_dir, ignore_errors=True)


def _download_https_resource(url: str, destination: Path) -> None:
    request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urlopen(request, timeout=120) as response:
        final_url = response.geturl()
        if urlparse(final_url).scheme.lower() != "https":
            raise AitoResourceError("resource redirect did not use HTTPS")
        if response.status != 200:
            raise AitoResourceError("resource download returned an unexpected status")
        with destination.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)


def _remove_stale_archives(account_dir: Path, cached: Mapping[str, Mapping[str, str | None]]) -> None:
    for vehicle_id, resource in cached.items():
        archive_name = resource.get("archive")
        if not archive_name:
            continue
        vehicle_dir = account_dir / _safe_path_part(vehicle_id)
        expected = account_dir / archive_name
        for archive in vehicle_dir.glob("*.zip"):
            if archive != expected:
                archive.unlink()


def _required_https_url(value: Any) -> str:
    url = _required_value(value, "resource URL")
    if urlparse(url).scheme.lower() != "https":
        raise AitoResourceError("resource URL must use HTTPS")
    return url


def _required_value(value: Any, name: str) -> str:
    normalized = _optional_value(value)
    if not normalized:
        raise AitoResourceError(f"missing {name}")
    return normalized


def _optional_value(value: Any) -> str | None:
    return str(value) if value is not None and str(value) else None


def _safe_path_part(value: Any) -> str:
    safe = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in str(value))
    return safe.strip(" .") or "unknown"
