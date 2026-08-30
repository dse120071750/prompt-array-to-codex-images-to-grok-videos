"""Export one completed run into the skill's small public JSON shape."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def chosen_members(run_dir: Path, milestone: str, output_id: str) -> list[Path]:
    chosen_path = run_dir / "milestones" / milestone / "out" / "chosen-output.json"
    chosen = read_json(chosen_path)
    if chosen.get("schema") != "m8m_chosen_output_v1" or chosen.get("status") != "chosen":
        raise ValueError(f"{milestone} has no valid chosen output")
    members = [
        member
        for member in chosen.get("members", [])
        if isinstance(member, dict) and member.get("output_id") == output_id
    ]
    members.sort(key=lambda item: int(item.get("order", 0)))
    paths = [(run_dir / str(member["path"])).resolve() for member in members]
    if not paths or any(not path.is_file() for path in paths):
        raise ValueError(f"{milestone}.{output_id} is incomplete")
    return paths


def export(run_dir: Path) -> list[dict[str, Any]]:
    run_dir = run_dir.resolve()
    request = read_json(run_dir / "request.json")
    prompts = request.get("prompts") if isinstance(request, dict) else None
    if not isinstance(prompts, list) or not prompts:
        raise ValueError("run request has no prompts array")

    image_paths = chosen_members(run_dir, "codex_images_generated_frozen", "images")
    video_prompt_path = chosen_members(
        run_dir, "image_video_prompts_frozen", "video_prompts"
    )
    if len(video_prompt_path) != 1:
        raise ValueError("video_prompts must have exactly one JSON member")
    video_prompts = read_json(video_prompt_path[0])
    video_paths = chosen_members(run_dir, "grok_videos_generated_frozen", "videos")
    if not isinstance(video_prompts, list):
        raise ValueError("chosen video_prompts member is not an array")
    if not (len(prompts) == len(image_paths) == len(video_prompts) == len(video_paths)):
        raise ValueError("chosen prompt, image, motion-prompt, and video counts differ")

    return [
        {
            "index": index,
            "image_prompt": prompt,
            "image_path": str(image_paths[index]),
            "video_prompt": video_prompts[index],
            "video_path": str(video_paths[index]),
        }
        for index, prompt in enumerate(prompts)
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = export(args.run_dir)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
