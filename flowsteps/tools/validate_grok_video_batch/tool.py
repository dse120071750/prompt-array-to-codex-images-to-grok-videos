"""Technically validate a Grok Build video batch with bundled ffprobe."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(root: Path, path: Path) -> bool:
    root = root.resolve()
    path = path.resolve()
    return path == root or root in path.parents


def resolve_ffprobe_command() -> list[str]:
    codebase = Path(__file__).resolve().parents[3]
    package_bin = codebase / "node_modules" / "ffprobe-static" / "bin"
    candidates = [path for path in package_bin.rglob("ffprobe*") if path.is_file()]
    if os.name == "nt":
        candidates = [path for path in candidates if path.suffix.lower() == ".exe"]
    else:
        candidates = [path for path in candidates if path.suffix.lower() != ".exe"]
    if not candidates:
        raise FileNotFoundError("repository-bundled ffprobe-static executable was not found")
    return [str(sorted(candidates)[0])]


def probe_video(path: Path, ffprobe_command: list[str]) -> dict[str, Any]:
    command = [
        *ffprobe_command,
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(path),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        raise ValueError(f"ffprobe rejected {path.name}: {(completed.stderr or '').strip()}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"ffprobe returned invalid JSON for {path.name}") from exc
    if not isinstance(result, dict):
        raise ValueError(f"ffprobe returned no object for {path.name}")
    return result


def _video_metadata(
    path: Path,
    probe: dict[str, Any],
    *,
    allowed_dimensions: set[tuple[int, int]] | None = None,
    duration_range: tuple[float, float] = (5.5, 6.5),
) -> dict[str, Any]:
    streams = probe.get("streams") if isinstance(probe.get("streams"), list) else []
    video_stream = next(
        (stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"),
        None,
    )
    if not isinstance(video_stream, dict):
        raise ValueError(f"{path.name} has no video stream")
    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    accepted = allowed_dimensions or {(720, 1280)}
    if (width, height) not in accepted:
        expected = " or ".join(f"{w}x{h}" for w, h in sorted(accepted))
        raise ValueError(f"{path.name} must be {expected}, got {width}x{height}")
    format_data = probe.get("format") if isinstance(probe.get("format"), dict) else {}
    format_name = str(format_data.get("format_name") or "").lower()
    if "mp4" not in format_name:
        raise ValueError(f"{path.name} is not an MP4 container: {format_name or 'unknown'}")
    duration_raw = video_stream.get("duration") or format_data.get("duration")
    try:
        duration = float(duration_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path.name} has no readable duration") from exc
    minimum_duration, maximum_duration = duration_range
    if not minimum_duration <= duration <= maximum_duration:
        midpoint = (minimum_duration + maximum_duration) / 2
        raise ValueError(f"{path.name} duration must be approximately {midpoint:g} seconds, got {duration:.3f}")
    size = path.stat().st_size
    if size <= 0:
        raise ValueError(f"{path.name} is empty")
    return {
        "width": width,
        "height": height,
        "duration_seconds": round(duration, 6),
        "format_name": format_name,
        "video_codec": str(video_stream.get("codec_name") or "unknown"),
        "bytes": size,
        "sha256": _sha256(path),
    }


def validate_batch(
    prompt_batch: dict[str, Any],
    generation: dict[str, Any],
    *,
    ffprobe_command: list[str],
) -> dict[str, Any]:
    items = prompt_batch.get("items")
    videos = generation.get("videos")
    receipt = generation.get("receipt")
    if not isinstance(items, list) or not items:
        raise ValueError("prompt_batch.items must be non-empty")
    if not isinstance(videos, list) or len(videos) != len(items):
        raise ValueError("video count does not match prompt count")
    if not isinstance(receipt, dict) or receipt.get("transport") != "acp":
        raise ValueError("generation receipt must use ACP")
    session_id = str(receipt.get("session_id") or "")
    if not session_id:
        raise ValueError("generation receipt has no session_id")
    attempt_dir_raw = receipt.get("attempt_dir")
    if not isinstance(attempt_dir_raw, str) or not attempt_dir_raw:
        raise ValueError("generation receipt has no attempt_dir")
    attempt_dir = Path(attempt_dir_raw).resolve()
    receipt_clips = receipt.get("clips")
    if not isinstance(receipt_clips, list) or len(receipt_clips) != len(items):
        raise ValueError("generation receipt clip count does not match prompts")

    validated_clips: list[dict[str, Any]] = []
    output_videos: list[dict[str, Any]] = []
    for index, (item, video, clip) in enumerate(zip(items, videos, receipt_clips)):
        if not isinstance(item, dict) or not isinstance(video, dict) or not isinstance(clip, dict):
            raise ValueError(f"batch item {index} is malformed")
        expected_id = f"prompt-{index + 1:03d}"
        if item.get("id") != expected_id or video.get("id") != expected_id or clip.get("id") != expected_id:
            raise ValueError(f"batch item {index} ID/order mismatch")
        if item.get("index") != index or video.get("index") != index or clip.get("index") != index:
            raise ValueError(f"batch item {index} numeric order mismatch")
        if video.get("prompt") != item.get("prompt") or clip.get("source_prompt") != item.get("prompt"):
            raise ValueError(f"batch item {index} source prompt mismatch")
        if clip.get("session_id") != session_id:
            raise ValueError(f"batch item {index} used a different ACP session")
        path_raw = video.get("path")
        if not isinstance(path_raw, str) or not path_raw:
            raise ValueError(f"batch item {index} has no path")
        path = Path(path_raw).resolve()
        if not _inside(attempt_dir, path):
            raise ValueError(f"batch item {index} path escaped the attempt directory")
        if not path.is_file():
            raise ValueError(f"batch item {index} video does not exist: {path}")
        metadata = _video_metadata(path, probe_video(path, ffprobe_command))
        if clip.get("sha256") != metadata["sha256"] or clip.get("bytes") != metadata["bytes"]:
            raise ValueError(f"batch item {index} checksum or byte count changed after generation")
        clip_with_metadata = dict(clip)
        clip_with_metadata.update(metadata)
        validated_clips.append(clip_with_metadata)
        output_video = dict(video)
        output_video.update(metadata)
        output_videos.append(output_video)

    updated_receipt = dict(receipt)
    updated_receipt["clips"] = validated_clips
    updated_receipt["validation"] = {
        "ok": True,
        "code": "technical_pass",
        "count": len(validated_clips),
        "required_dimensions": {"width": 720, "height": 1280},
        "duration_range_seconds": [5.5, 6.5],
        "ffprobe": ffprobe_command[0],
    }
    return {
        "videos": output_videos,
        "receipt": updated_receipt,
        "validation": updated_receipt["validation"],
    }


def run(
    input_data: dict[str, Any],
    draft: dict[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    del draft
    prompt_batch = input_data.get("prompt_batch")
    generation = input_data.get("generation")
    if not isinstance(prompt_batch, dict) or not isinstance(generation, dict):
        raise ValueError("validate_grok_video_batch needs prompt_batch and generation")
    return validate_batch(
        prompt_batch,
        generation,
        ffprobe_command=resolve_ffprobe_command(),
    )
