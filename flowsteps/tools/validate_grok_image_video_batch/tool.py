"""Technically validate a frozen-image Grok Build video batch."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


ACCEPTED_DIMENSIONS = {(720, 1264), (720, 1280)}


def _video_validator() -> Any:
    path = Path(__file__).resolve().parents[1] / "validate_grok_video_batch" / "tool.py"
    spec = importlib.util.spec_from_file_location("m8m_video_validator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load shared video validator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inside(root: Path, path: Path) -> bool:
    root = root.resolve()
    path = path.resolve()
    return path == root or root in path.parents


def validate_batch(
    images: list[dict[str, Any]],
    video_prompts: dict[str, Any],
    generation: dict[str, Any],
    *,
    ffprobe_command: list[str],
) -> dict[str, Any]:
    validator = _video_validator()
    motion_items = video_prompts.get("items") if isinstance(video_prompts.get("items"), list) else []
    videos = generation.get("videos")
    receipt = generation.get("receipt")
    if not images or len(motion_items) != len(images):
        raise ValueError("source images and motion prompts are incomplete")
    if not isinstance(videos, list) or len(videos) != len(images):
        raise ValueError("video count does not match source image count")
    if not isinstance(receipt, dict) or receipt.get("schema") != "grok_image_video_batch_receipt_v1" or receipt.get("transport") != "acp":
        raise ValueError("generation receipt must be a Grok image-to-video ACP receipt")
    session_id = str(receipt.get("session_id") or "")
    if not session_id:
        raise ValueError("generation receipt has no session_id")
    if receipt.get("allowed_tools") != ["image_to_video"]:
        raise ValueError("generation receipt did not enforce the image_to_video-only allowlist")
    attempt_raw = receipt.get("attempt_dir")
    if not isinstance(attempt_raw, str) or not attempt_raw:
        raise ValueError("generation receipt has no attempt_dir")
    attempt_dir = Path(attempt_raw).resolve()
    clips = receipt.get("clips")
    if not isinstance(clips, list) or len(clips) != len(images):
        raise ValueError("generation receipt clip count is incomplete")

    output_videos: list[dict[str, Any]] = []
    validated_clips: list[dict[str, Any]] = []
    for index, (image, motion, video, clip) in enumerate(zip(images, motion_items, videos, clips)):
        expected_id = f"prompt-{index + 1:03d}"
        if not all(isinstance(item, dict) for item in (image, motion, video, clip)):
            raise ValueError(f"batch item {index} is malformed")
        if {image.get("id"), motion.get("id"), video.get("id"), clip.get("id")} != {expected_id}:
            raise ValueError(f"batch item {index} ID/order mismatch")
        if any(item.get("index") != index for item in (image, motion, video, clip)):
            raise ValueError(f"batch item {index} numeric order mismatch")
        if motion.get("source_image_sha256") != image.get("sha256"):
            raise ValueError(f"batch item {index} motion prompt is bound to another image")
        if video.get("source_image_sha256") != image.get("sha256") or clip.get("source_image_sha256") != image.get("sha256"):
            raise ValueError(f"batch item {index} generation used another source image")
        if video.get("video_prompt") != motion.get("video_prompt") or clip.get("video_prompt") != motion.get("video_prompt"):
            raise ValueError(f"batch item {index} motion prompt changed during generation")
        if clip.get("session_id") != session_id:
            raise ValueError(f"batch item {index} used another ACP session")
        path_raw = video.get("path")
        if not isinstance(path_raw, str) or not path_raw:
            raise ValueError(f"batch item {index} has no video path")
        path = Path(path_raw).resolve()
        if not _inside(attempt_dir, path) or not path.is_file():
            raise ValueError(f"batch item {index} video escaped the attempt directory")
        metadata = validator._video_metadata(
            path,
            validator.probe_video(path, ffprobe_command),
            allowed_dimensions=ACCEPTED_DIMENSIONS,
            duration_range=(2.8, 3.2),
        )
        if clip.get("sha256") != metadata["sha256"] or clip.get("bytes") != metadata["bytes"]:
            raise ValueError(f"batch item {index} checksum or byte count changed")
        enriched_video = dict(video)
        enriched_video.update(metadata)
        output_videos.append(enriched_video)
        enriched_clip = dict(clip)
        enriched_clip.update(metadata)
        validated_clips.append(enriched_clip)
    updated_receipt = dict(receipt)
    updated_receipt["clips"] = validated_clips
    updated_receipt["validation"] = {
        "ok": True,
        "code": "technical_pass",
        "count": len(validated_clips),
        "accepted_dimensions": [
            {"width": width, "height": height}
            for width, height in sorted(ACCEPTED_DIMENSIONS)
        ],
        "aspect_ratio": "approximately 9:16",
        "duration_range_seconds": [2.8, 3.2],
        "ffprobe": ffprobe_command[0],
    }
    return {"videos": output_videos, "receipt": updated_receipt, "validation": updated_receipt["validation"]}


def run(input_data: dict[str, Any], draft: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
    del draft
    images = input_data.get("images")
    prompts = input_data.get("video_prompts")
    generation = input_data.get("generation")
    if not isinstance(images, list) or not isinstance(prompts, dict) or not isinstance(generation, dict):
        raise ValueError("validate_grok_image_video_batch needs images, video_prompts, and generation")
    validator = _video_validator()
    return validate_batch(images, prompts, generation, ffprobe_command=validator.resolve_ffprobe_command())
