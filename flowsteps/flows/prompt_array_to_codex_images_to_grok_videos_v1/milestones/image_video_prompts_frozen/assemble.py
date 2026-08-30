"""Privately inspect frozen stills and admit one motion prompt per image."""

from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
from typing import Any


STEP_ID = "image_video_prompts_frozen"
CODEBASE = Path(__file__).resolve().parents[5]
FLOW_DIR = Path(__file__).resolve().parents[2]
GEM_PATH = FLOW_DIR / "references" / f"{STEP_ID}.md"
FORMAT = {
    "duration_seconds": 3,
    "aspect_ratio": "9:16",
    "resolution": "720p",
    "grok_master_duration_seconds": 6,
    "temporal_transform": "reverse_and_2x",
}


def _judge() -> Any:
    path = CODEBASE / "flowsteps" / "tools" / "image_video_prompts_judge" / "tool.py"
    spec = importlib.util.spec_from_file_location("image_video_prompts_judge", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load tool: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _images(value: Any) -> list[dict[str, Any]]:
    current = value
    for _ in range(5):
        if isinstance(current, list):
            if current and all(isinstance(item, dict) for item in current):
                return current
            break
        if not isinstance(current, dict):
            break
        if isinstance(current.get("images"), list):
            current = current["images"]
            continue
        if isinstance(current.get("value"), list):
            current = current["value"]
            continue
        outputs = current.get("outputs")
        if isinstance(outputs, dict) and isinstance(outputs.get("images"), list):
            current = outputs["images"]
            continue
        break
    raise ValueError("image_video_prompts_frozen needs the chosen ordered images output")


def _manifest(value: Any) -> dict[str, Any]:
    current = value
    for _ in range(5):
        if isinstance(current, dict) and current.get("schema") == "codex_image_batch_v1":
            return current
        if not isinstance(current, dict):
            break
        for key in ("manifest", "value", "image_manifest"):
            if isinstance(current.get(key), dict):
                current = current[key]
                break
        else:
            break
    raise ValueError("image_video_prompts_frozen needs the chosen image manifest")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bind_images(assets: list[dict[str, Any]], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    items = manifest.get("items") if isinstance(manifest.get("items"), list) else []
    if manifest.get("count") != len(assets) or len(items) != len(assets):
        raise ValueError("image collection and manifest must be complete")
    bound: list[dict[str, Any]] = []
    for index, (asset, item) in enumerate(zip(assets, items)):
        if not isinstance(item, dict) or asset.get("id") != item.get("id") or item.get("index") != index:
            raise ValueError(f"image collection member {index} does not match its manifest binding")
        path = Path(str(asset.get("path") or "")).resolve()
        if not path.is_file() or _sha256(path) != item.get("sha256"):
            raise ValueError(f"chosen image collection member {index} changed after freezing")
        logical = dict(item)
        logical["id"] = str(item.get("stable_id") or "")
        logical["path"] = str(path)
        bound.append(logical)
    return bound


def _instruction(images: list[dict[str, Any]], findings: list[str] | None = None) -> str:
    image_map = [
        {"id": item.get("id"), "index": item.get("index"), "path": item.get("path"), "sha256": item.get("sha256")}
        for item in images
    ]
    correction = ""
    if findings:
        correction = "\n\nThe previous draft was rejected. Correct every finding without exposing analysis:\n- " + "\n- ".join(findings)
    return (
        "Inspect every local image below with the view_image tool, one at a time and in array order, "
        "before drafting. Keep all visual analysis private. Apply the milestone gem exactly. Write "
        "only a JSON object with count and prompts; prompts must be the strict ordered JSON array of "
        "strings requested by the gem. Do not include ok, PASS, Markdown, image labels, analysis, or "
        "commentary.\n\nMILESTONE GEM\n\n"
        + GEM_PATH.read_text(encoding="utf-8")
        + "\n\nFROZEN IMAGES IN SOURCE ORDER\n\n"
        + json.dumps(image_map, ensure_ascii=False, indent=2)
        + correction
    )


def _need_model(images: list[dict[str, Any]], findings: list[str] | None = None) -> dict[str, Any]:
    return {
        "_flowstep": "NEED_MODEL",
        "model": "completion",
        "model_request": {
            "milestone": STEP_ID,
            "flowstep": "construct_image_video_prompts",
            "required_builtin_tool": "view_image",
            "gem_path": str(GEM_PATH),
            "image_paths": [str(item.get("path") or "") for item in images],
            "instruction": _instruction(images, findings),
        },
    }


def run(input_data: dict[str, Any], draft: dict[str, Any] | None = None, **_: Any) -> dict[str, Any]:
    assets = _images(input_data.get("images") or input_data)
    manifest = _manifest(input_data.get("image_manifest") or input_data)
    images = _bind_images(assets, manifest)
    if draft is None:
        return _need_model(images)
    receipt = _judge().run({"images": images, "draft": draft, "gem_path": str(GEM_PATH)})
    if receipt.get("ok") is not True:
        return _need_model(images, [str(item) for item in receipt.get("findings") or []])
    prompts = draft["prompts"]
    items = []
    for index, (image, prompt) in enumerate(zip(images, prompts)):
        items.append({
            "id": f"prompt-{index + 1:03d}",
            "index": index,
            "source_image_path": image["path"],
            "source_image_sha256": image["sha256"],
            "source_prompt": image["source_prompt"],
            "video_prompt": prompt,
        })
    batch = {
        "schema": "image_video_prompt_batch_v1",
        "count": len(items),
        "format": dict(FORMAT),
        "prompts": list(prompts),
        "items": items,
    }
    return {"outputs": {"video_prompts": list(prompts), "manifest": batch}, "receipt": receipt}
