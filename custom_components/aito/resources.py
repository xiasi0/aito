from __future__ import annotations

import os
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .const import DEFAULT_USER_AGENT

ResourceDownloader = Callable[[str, Path], None]

# The interactive car model ships as layered PNGs under this prefix.
_CAR_IMAGE_SEARCH_PREFIX = "carmodel/"


class AitoResourceError(RuntimeError):
    pass


# The car model is layered PNGs; the skeleton alone is a doorless shell. The
# App rebuilds the full car by stacking each part over it. Layer groups are
# matched by keyword rather than exact path, because the numeric prefixes are
# not guaranteed to be identical across vehicle models. Each door/window group
# is a bodymovin animation whose CLOSED state is the LAST frame of its
# *__open_to_close variant (the *__close_to_open first frame is not fully shut
# and leaves a black gap). The lamp layer is deliberately skipped so the
# daytime running lights are not lit.
_CAR_SKELETON_KEYWORD = "skeleton"
_CAR_WINDSHIELD_KEYWORD = "windshield"
_CAR_CLOSING_SUFFIX = "open_to_close"
# Paint order, bottom to top. The left-front door is painted again last because
# the window layers' black edges otherwise cover its trailing edge and leave a
# thick black seam at the B-pillar.
_CAR_DOOR_KEYWORDS = ("left_front_door", "right_front_door", "left_rear_door", "right_rear_door")
_CAR_WINDOW_KEYWORDS = ("left_front_window", "left_rear_window", "right_front_window", "right_rear_window")
_CAR_LATE_KEYWORDS = ("trunk", "charging_port")
_CAR_TOP_KEYWORD = "left_front_door"


def _layer_groups(names: set[str]) -> list[str]:
    """Return the distinct carmodel animation group directories in the archive."""
    groups = set()
    for name in names:
        if not name.startswith(_CAR_IMAGE_SEARCH_PREFIX) or "/images/" not in name:
            continue
        groups.add(name.split("/images/", 1)[0])
    return sorted(groups)


def _find_group(groups: list[str], keyword: str) -> str | None:
    """Find the closed-state animation group whose name contains keyword."""
    for group in groups:
        if keyword in group and group.endswith(_CAR_CLOSING_SUFFIX):
            return group
    return None


def _find_background(names: set[str], keyword: str) -> str | None:
    """Find a static background.png layer whose directory contains keyword."""
    for name in sorted(names):
        if name.startswith(_CAR_IMAGE_SEARCH_PREFIX) and keyword in name and name.endswith("background.png"):
            return name
    return None


def _closed_frame(names: set[str], group: str) -> str | None:
    """Return the fully-closed frame of an animation group (its last frame).

    Frames are named a__0-20_.png (frame 0) then a__0-20__0.png .. __N.png, so
    pick the highest numeric index rather than trusting string order.
    """
    prefix = f"{group}/images/"
    frames = [n for n in names if n.startswith(prefix) and n.lower().endswith(".png")]
    if not frames:
        return None

    def index(name: str) -> int:
        leaf = name.rsplit("/", 1)[1]
        if leaf == "a__0-20_.png":
            return 0
        match = re.search(r"__(\d+)\.png$", leaf)
        return int(match.group(1)) + 1 if match else -1

    return max(frames, key=index)


def _compose_full_car(bundle: zipfile.ZipFile) -> bytes | None:
    """Rebuild the all-closed car view by alpha-stacking the model layers.

    All layers are same-size full-canvas PNGs, so a plain composite works.
    Returns encoded PNG bytes, or None when Pillow is missing or the archive
    lacks the skeleton layer (the caller then falls back to a single PNG).
    """
    try:
        import io

        from PIL import Image
    except Exception:
        return None
    names = set(bundle.namelist())

    def load(path: str | None):
        if not path or path not in names:
            return None
        try:
            return Image.open(io.BytesIO(bundle.read(path))).convert("RGBA")
        except Exception:
            return None

    base = load(_find_background(names, _CAR_SKELETON_KEYWORD))
    if base is None:
        return None

    def stack(image, layer):
        return Image.alpha_composite(image, layer) if layer is not None and layer.size == image.size else image

    groups = _layer_groups(names)

    def closed(keyword: str):
        group = _find_group(groups, keyword)
        return load(_closed_frame(names, group)) if group else None

    for keyword in _CAR_DOOR_KEYWORDS + _CAR_WINDOW_KEYWORDS:
        base = stack(base, closed(keyword))
    base = stack(base, load(_find_background(names, _CAR_WINDSHIELD_KEYWORD)))
    for keyword in _CAR_LATE_KEYWORDS:
        base = stack(base, closed(keyword))
    # Left-front door on top, over the window layers, to hide the B-pillar seam.
    base = stack(base, closed(_CAR_TOP_KEYWORD))
    buffer = io.BytesIO()
    base.save(buffer, format="PNG")
    return buffer.getvalue()


def extract_car_image(archive: str | Path, destination: str | Path) -> bool:
    """Write the full (all-closed) car render out of a downloaded archive.

    Composites the layered model into a complete car; if Pillow is unavailable
    or the layout is unexpected, falls back to the skeleton background or the
    largest PNG under carmodel/, so a new vehicle model still gets a picture.
    """
    archive = Path(archive)
    destination = Path(destination)
    if not archive.is_file():
        return False
    try:
        with zipfile.ZipFile(archive) as bundle:
            payload = _compose_full_car(bundle)
            if payload is None:
                names = bundle.namelist()
                chosen = _find_background(set(names), _CAR_SKELETON_KEYWORD)
                if chosen is None:
                    pngs = [
                        name
                        for name in names
                        if name.startswith(_CAR_IMAGE_SEARCH_PREFIX) and name.lower().endswith(".png")
                    ]
                    if not pngs:
                        return False
                    chosen = max(pngs, key=lambda name: bundle.getinfo(name).file_size)
                payload = bundle.read(chosen)
    except (zipfile.BadZipFile, OSError) as error:
        raise AitoResourceError("could not read vehicle resource archive") from error
    if not payload:
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.write_bytes(payload)
    os.replace(temporary, destination)
    return True


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
