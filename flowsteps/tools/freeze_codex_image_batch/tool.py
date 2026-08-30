"""Safely import a current-run Codex built-in ImageGen batch."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError


SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MIME_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def _inside(root: Path, path: Path) -> bool:
    root = root.resolve()
    path = path.resolve()
    return path == root or root in path.parents


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _generated_root(input_data: dict[str, Any]) -> Path:
    test_root = input_data.get("_test_allowed_generated_root")
    if isinstance(test_root, str) and test_root.strip():
        return Path(test_root).resolve()
    configured = os.environ.get("CODEX_HOME")
    codex_home = Path(configured).expanduser().resolve() if configured else Path.home().resolve() / ".codex"
    return (codex_home / "generated_images").resolve()


def _batch_items(batch: dict[str, Any]) -> list[dict[str, Any]]:
    if batch.get("schema") != "visual_prompt_batch_v1":
        raise ValueError("prompt_batch must use visual_prompt_batch_v1")
    if batch.get("image") != {"provider": "codex_builtin_imagegen", "aspect_ratio": "9:16"}:
        raise ValueError("prompt_batch image settings are not frozen to Codex built-in ImageGen 9:16")
    items = batch.get("items")
    if not isinstance(items, list) or not items or batch.get("count") != len(items):
        raise ValueError("prompt_batch items/count are invalid")
    return items


def _draft_items(draft: dict[str, Any]) -> list[dict[str, Any]]:
    if "ok" in draft:
        raise ValueError("the model draft must not contain ok")
    if set(draft) != {"count", "images"}:
        raise ValueError("draft must contain exactly count and images")
    images = draft.get("images")
    if not isinstance(images, list) or not images or draft.get("count") != len(images):
        raise ValueError("draft images/count are invalid")
    return images


def _inspect(path: Path) -> tuple[int, int, str]:
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            width, height = image.size
            image_format = str(image.format or "").upper()
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError(f"unreadable raster image: {path.name}") from exc
    if width <= 0 or height <= 0 or height <= width:
        raise ValueError(f"{path.name} must be a portrait image")
    if abs((width / height) - (9 / 16)) > 0.01:
        raise ValueError(f"{path.name} must be approximately 9:16, got {width}x{height}")
    return width, height, image_format


def run(input_data: dict[str, Any], draft: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
    del draft
    batch = input_data.get("prompt_batch")
    candidate = input_data.get("draft")
    work_dir_raw = input_data.get("work_dir")
    if not isinstance(batch, dict) or not isinstance(candidate, dict):
        raise ValueError("freeze_codex_image_batch needs prompt_batch and draft")
    if not isinstance(work_dir_raw, str) or not work_dir_raw.strip():
        raise ValueError("freeze_codex_image_batch needs an internal work_dir")
    batch_items = _batch_items(batch)
    draft_items = _draft_items(candidate)
    if len(draft_items) != len(batch_items):
        raise ValueError("generated image count must equal the frozen prompt count")
    generated_root = _generated_root(input_data)
    if not generated_root.is_dir():
        raise ValueError(f"Codex generated-images directory does not exist: {generated_root}")
    not_before_raw = input_data.get("not_before_epoch")
    not_before = float(not_before_raw) if isinstance(not_before_raw, (int, float)) else 0.0

    inspected: list[dict[str, Any]] = []
    seen_sources: set[Path] = set()
    for index, (expected, item) in enumerate(zip(batch_items, draft_items)):
        if not isinstance(item, dict):
            raise ValueError(f"images[{index}] must be an object")
        expected_id = f"prompt-{index + 1:03d}"
        if expected.get("id") != expected_id or expected.get("index") != index:
            raise ValueError(f"prompt_batch item {index} order/id is invalid")
        if item.get("id") != expected_id or item.get("index") != index:
            raise ValueError(f"images[{index}] order/id does not match {expected_id}")
        source_prompt = expected.get("prompt")
        if item.get("source_prompt") != source_prompt or item.get("image_prompt") != source_prompt:
            raise ValueError(f"images[{index}] must preserve the source prompt verbatim")
        raw_path = item.get("generated_file")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(f"images[{index}] has no generated_file")
        source = Path(raw_path).resolve()
        if source in seen_sources:
            raise ValueError("each prompt must use a distinct newly generated image")
        seen_sources.add(source)
        if not _inside(generated_root, source):
            raise ValueError(f"images[{index}] escaped Codex generated-images: {source}")
        if source.suffix.lower() not in SUPPORTED_SUFFIXES or not source.is_file():
            raise ValueError(f"images[{index}] is not a supported generated raster: {source}")
        stat = source.stat()
        if stat.st_size <= 0:
            raise ValueError(f"images[{index}] is empty")
        if not_before and stat.st_mtime < not_before - 2.0:
            raise ValueError(f"images[{index}] predates this M8M run and cannot be reused")
        width, height, image_format = _inspect(source)
        inspected.append({
            "expected": expected,
            "source": source,
            "width": width,
            "height": height,
            "image_format": image_format,
            "source_sha256": _sha256(source),
            "bytes": stat.st_size,
        })

    fingerprint = hashlib.sha256(
        "\n".join(str(row["source_sha256"]) for row in inspected).encode("utf-8")
    ).hexdigest()[:16]
    target_dir = (Path(work_dir_raw).resolve() / f"candidate_{fingerprint}").resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    images: list[dict[str, Any]] = []
    manifest_items: list[dict[str, Any]] = []
    for row in inspected:
        expected = row["expected"]
        source = row["source"]
        suffix = source.suffix.lower()
        canonical = (target_dir / f"{expected['id']}{suffix}").resolve()
        if not _inside(target_dir, canonical):
            raise ValueError("canonical image path escaped the candidate directory")
        if canonical.is_file():
            if _sha256(canonical) != row["source_sha256"]:
                raise ValueError(f"existing canonical image changed: {canonical}")
        else:
            shutil.copy2(source, canonical)
        record = {
            # M8M collection member IDs are filesystem-safe addresses and may
            # contain underscores, not hyphens.  Keep the editorial stable ID
            # separately so transport addressing never changes prompt identity.
            "id": f"prompt_{expected['index'] + 1:03d}",
            "stable_id": expected["id"],
            "name": f"Codex ImageGen still {expected['index'] + 1:03d}",
            "path": str(canonical),
            "index": expected["index"],
            "source_prompt": expected["prompt"],
            "image_prompt": expected["prompt"],
            "sha256": row["source_sha256"],
            "bytes": row["bytes"],
            "width": row["width"],
            "height": row["height"],
            "mime_type": MIME_TYPES[suffix],
            "image_format": row["image_format"],
        }
        images.append(record)
        manifest_items.append(dict(record))
    manifest = {
        "schema": "codex_image_batch_v1",
        "provider": "codex_builtin_imagegen",
        "count": len(images),
        "aspect_ratio": "9:16",
        "items": manifest_items,
    }
    return {"images": images, "manifest": manifest}
