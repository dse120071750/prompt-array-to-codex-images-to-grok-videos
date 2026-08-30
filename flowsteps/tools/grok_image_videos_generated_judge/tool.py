"""Deterministically judge the complete single-session image-to-video batch."""

from __future__ import annotations

from typing import Any


def run(input_data: dict[str, Any], params: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
    del params
    images = input_data.get("images") if isinstance(input_data.get("images"), list) else []
    prompts = input_data.get("video_prompts") if isinstance(input_data.get("video_prompts"), dict) else {}
    validated = input_data.get("validated") if isinstance(input_data.get("validated"), dict) else {}
    videos = validated.get("videos") if isinstance(validated.get("videos"), list) else []
    receipt = validated.get("receipt") if isinstance(validated.get("receipt"), dict) else {}
    validation = validated.get("validation") if isinstance(validated.get("validation"), dict) else {}
    motion_items = prompts.get("items") if isinstance(prompts.get("items"), list) else []
    if not images or len(videos) != len(images) or len(motion_items) != len(images):
        raise ValueError("judge requires one complete video per frozen image and motion prompt")
    if validation.get("ok") is not True or receipt.get("count") != len(images):
        raise ValueError("judge requires passing technical validation for the full batch")
    session_id = str(receipt.get("session_id") or "")
    clips = receipt.get("clips") if isinstance(receipt.get("clips"), list) else []
    if not session_id or len(clips) != len(images):
        raise ValueError("judge receipt has no complete ACP session mapping")
    if {str(clip.get("session_id") or "") for clip in clips if isinstance(clip, dict)} != {session_id}:
        raise ValueError("judge found more than one ACP session")
    expected_ids = [f"prompt-{index + 1:03d}" for index in range(len(images))]
    if [str(video.get("id") or "") for video in videos] != expected_ids:
        raise ValueError("judge video order does not match frozen image order")
    if receipt.get("allowed_tools") != ["image_to_video"]:
        raise ValueError("judge requires the image_to_video-only tool allowlist")
    result: dict[str, Any] = {"ok": True, "code": "pass", "count": len(videos), "session_id": session_id}
    if input_data.get("gem_path"):
        result["gem"] = str(input_data["gem_path"])
    return result
