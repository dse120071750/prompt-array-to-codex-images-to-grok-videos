"""Generate and technically judge the complete frozen-image Grok ACP batch."""

from __future__ import annotations

import importlib.util
import hashlib
from pathlib import Path
from typing import Any


CODEBASE = Path(__file__).resolve().parents[5]
FLOW_DIR = Path(__file__).resolve().parents[2]


def _load_tool(tool_id: str) -> Any:
    path = CODEBASE / "flowsteps" / "tools" / tool_id / "tool.py"
    spec = importlib.util.spec_from_file_location(f"m8m_{tool_id}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load tool: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _dict_schema(value: Any, schema: str, label: str) -> dict[str, Any]:
    current = value
    for _ in range(5):
        if isinstance(current, dict) and current.get("schema") == schema:
            return current
        if not isinstance(current, dict):
            break
        moved = False
        for key in ("value", "batch", "manifest", "video_prompts", "prompt_batch", "image_manifest"):
            if isinstance(current.get(key), dict):
                current = current[key]
                moved = True
                break
        if not moved:
            break
    raise ValueError(f"grok_videos_generated_frozen needs the chosen {label}")


def _images(value: Any) -> list[dict[str, Any]]:
    current = value
    for _ in range(5):
        if isinstance(current, list) and current and all(isinstance(item, dict) for item in current):
            return current
        if not isinstance(current, dict):
            break
        if isinstance(current.get("images"), list):
            current = current["images"]
        elif isinstance(current.get("value"), list):
            current = current["value"]
        else:
            break
    raise ValueError("grok_videos_generated_frozen needs the chosen images")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bind_images(assets: list[dict[str, Any]], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    items = manifest.get("items") if isinstance(manifest.get("items"), list) else []
    if manifest.get("count") != len(assets) or len(items) != len(assets):
        raise ValueError("chosen images and manifest are incomplete")
    bound: list[dict[str, Any]] = []
    for index, (asset, item) in enumerate(zip(assets, items)):
        if not isinstance(item, dict) or asset.get("id") != item.get("id") or item.get("index") != index:
            raise ValueError(f"chosen image {index} does not match its manifest binding")
        path = Path(str(asset.get("path") or "")).resolve()
        if not path.is_file() or _sha256(path) != item.get("sha256"):
            raise ValueError(f"chosen image {index} changed after freezing")
        logical = dict(item)
        logical["id"] = str(item.get("stable_id") or "")
        logical["path"] = str(path)
        bound.append(logical)
    return bound


def run(input_data: dict[str, Any], draft: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    del draft
    prompt_batch = _dict_schema(input_data.get("prompt_batch"), "visual_prompt_batch_v1", "prompt batch")
    image_assets = _images(input_data.get("images"))
    image_manifest = _dict_schema(input_data.get("image_manifest"), "codex_image_batch_v1", "image manifest")
    images = _bind_images(image_assets, image_manifest)
    public_prompts = input_data.get("video_prompts")
    if not isinstance(public_prompts, list) or not public_prompts:
        raise ValueError("grok_videos_generated_frozen needs the chosen video prompt array")
    video_prompts = _dict_schema(input_data.get("video_prompt_manifest"), "image_video_prompt_batch_v1", "video prompt manifest")
    if video_prompts.get("prompts") != public_prompts:
        raise ValueError("public video prompt array and binding manifest differ")
    run_dir_raw = kwargs.get("run_dir")
    if not run_dir_raw:
        raise ValueError("grok_videos_generated_frozen needs run_dir")
    run_dir = Path(str(run_dir_raw)).resolve()
    work_dir = run_dir / "milestones" / "grok_videos_generated_frozen" / "work" / "acp_attempts"
    generator = _load_tool("grok_build_acp_image_video_batch")
    validator = _load_tool("validate_grok_image_video_batch")
    judge = _load_tool("grok_image_videos_generated_judge")
    generation = generator.run({
        "prompt_batch": prompt_batch,
        "images": images,
        "image_manifest": image_manifest,
        "video_prompts": video_prompts,
        "work_dir": str(work_dir),
        "run_dir": str(run_dir),
    })
    validated = validator.run({"images": images, "video_prompts": video_prompts, "generation": generation})
    receipt = judge.run({
        "images": images,
        "video_prompts": video_prompts,
        "validated": validated,
        "gem_path": str(FLOW_DIR / "references" / "grok_videos_generated_frozen.md"),
    })
    chosen_videos = []
    for index, video in enumerate(validated["videos"]):
        member = dict(video)
        member["stable_id"] = str(video.get("id") or "")
        member["id"] = f"video_{index + 1:03d}"
        member["name"] = str(video.get("name") or f"Grok image-derived video {index + 1:03d}")
        chosen_videos.append(member)
    return {"outputs": {"videos": chosen_videos, "receipt": validated["receipt"]}, "receipt": receipt}
