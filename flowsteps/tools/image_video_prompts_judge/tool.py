"""Validate the one-image-to-one-motion-prompt array from the supplied gem."""

from __future__ import annotations

import re
from typing import Any


PRESERVE_TERMS = ("composition", "subjects", "object count", "palette", "materials", "textures", "background")
LARGE_ACTION_TERMS = (
    "assemble", "expand", "fold", "lock", "place", "reconfigure", "slide",
    "stack", "transform", "unfold", "rise", "break", "enter",
)
STYLE_TERMS = (
    "tactile 2d paper collage", "stop-motion", "machine-cut paper edges",
    "warm cream paper keylines", "halftone photographic textures",
    "soft paper drop shadows", "klein blue",
)


def _draft(input_data: dict[str, Any]) -> dict[str, Any]:
    value = input_data.get("draft")
    if isinstance(value, dict) and isinstance(value.get("video_prompts"), dict):
        value = value["video_prompts"]
    return value if isinstance(value, dict) else {}


def run(input_data: dict[str, Any], params: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
    del params
    images = input_data.get("images") if isinstance(input_data.get("images"), list) else []
    candidate = _draft(input_data)
    findings: list[str] = []
    if "ok" in candidate:
        findings.append("the model draft must not contain ok")
    if set(candidate) != {"count", "prompts"}:
        findings.append("draft must contain exactly count and prompts")
    prompts = candidate.get("prompts")
    if not isinstance(prompts, list):
        findings.append("prompts must be a JSON array")
        prompts = []
    if candidate.get("count") != len(prompts):
        findings.append("count must equal the prompt array length")
    if len(prompts) != len(images) or not images:
        findings.append("prompt count must exactly equal the frozen image count")
    seen: set[str] = set()
    for index, prompt in enumerate(prompts):
        label = f"prompt {index + 1}"
        if not isinstance(prompt, str):
            findings.append(f"{label} must be a string")
            continue
        folded = re.sub(r"\s+", " ", prompt).strip().casefold()
        if len(prompt) < 300:
            findings.append(f"{label} is not detailed enough to be independently usable")
        if folded in seen:
            findings.append(f"{label} duplicates another prompt")
        seen.add(folded)
        if not re.search(r"\b3[- ]second\b", folded) or "9:16" not in folded or "vertical" not in folded:
            findings.append(f"{label} must specify a 3-second vertical 9:16 clip")
        if "reference image" not in folded or not any(term in folded for term in ("exact final still", "exact final frame")):
            findings.append(f"{label} must use its supplied reference image as the exact final still")
        if not any(term in folded for term in LARGE_ACTION_TERMS):
            findings.append(f"{label} needs one large readable transformation action")
        if not any(term in folded for term in ("hold", "holds", "holding")):
            findings.append(f"{label} must finish with a brief final hold")
        for term in PRESERVE_TERMS:
            if term not in folded:
                findings.append(f"{label} must preserve {term}")
        for term in STYLE_TERMS:
            if term not in folded:
                findings.append(f"{label} must include style term: {term}")
        if "camera" not in folded or "locked" not in folded:
            findings.append(f"{label} must include a camera lock")
        if "visual continuity" not in folded and "continuity" not in folded:
            findings.append(f"{label} must require visual continuity")
        for negative in ("no 3d cgi", "no photoreal environments", "no text", "no letters", "no watermark", "no ui"):
            if negative not in folded:
                findings.append(f"{label} must include negative constraint: {negative}")
        forbidden = ("another reference", "other reference", "next image", "previous image", "image 1", "image 2", "image 3", "reverse master", "reverse-generation")
        if any(term in folded for term in forbidden):
            findings.append(f"{label} must use only its own supplied image")
        image = images[index] if index < len(images) and isinstance(images[index], dict) else {}
        source_prompt = str(image.get("source_prompt") or "").casefold()
        if "hand" in source_prompt:
            if not any(term in folded for term in ("outside the canvas", "off-canvas", "beyond the frame")):
                findings.append(f"{label} must bring the hand in from outside the canvas")
            if not any(term in folded for term in ("place", "places", "placing", "lock", "locks", "lower", "lowers")):
                findings.append(f"{label} must show the hand placing or locking its object")
        if any(term in folded for term in ("visual analysis", "i observe", "the image contains", "analysis:")):
            findings.append(f"{label} exposes visual analysis")
    receipt: dict[str, Any] = {
        "ok": not findings,
        "code": "pass" if not findings else "rejected",
        "findings": findings,
        "image_count": len(images),
        "prompt_count": len(prompts),
    }
    if input_data.get("gem_path"):
        receipt["gem"] = str(input_data["gem_path"])
    return receipt
