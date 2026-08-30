# FlowStep skill audit: prompt_array_to_codex_images_to_grok_videos_v1

- audited_skill: `prompt_array_to_codex_images_to_grok_videos_v1`
- path: `<repo>/flowsteps/flows/prompt_array_to_codex_images_to_grok_videos_v1`
- linked_flow: `<repo>/flowsteps/flows/prompt_array_to_codex_images_to_grok_videos_v1`
- audited_at: 2026-08-30T15:41:52Z
- current_flow_schema: `flowstep_flow_v4`
- flow_id: `prompt_array_to_codex_images_to_grok_videos_v1`
- location: `flowsteps_flow`
- verdict: `MILESTONE_TOOLBOX`
- status: `PASS`
- P0: 0  P1: 0

## Audited skill

(no SKILL.md description)

## Goal

Separate `prompt_array_to_codex_images_to_grok_videos_v1` so each human-inspectable outcome is one milestone (`prompt_batch_ready` → `codex_images_generated_frozen` → `image_video_prompts_frozen` → `grok_videos_generated_frozen`). Current shape is v4 milestones with named chosen outputs. Promote reusable current units (0 skill script(s) plus any action-named steps) to standardized Python tools under `flowsteps/tools/<tool_id>/` with typed input/output schemas. Intelligence may exist only *inside* a milestone and may only call that milestone's toolbox. Final payload: `grok_image_video_batch_v1`.

## Tool vs intelligence

Schema: `tool_vs_intelligence_table_v1`. Classify before generate.

| id | class | test | why |
| --- | --- | --- | --- |
| `prepare_visual_prompt_batch` | `tool` | same input → same action; fixture-testable; receipt not opinion; junior can implement from schema | listed toolbox function for this milestone |
| `codex_images_generated_frozen` | `intelligence` | fails at least one of the four tests; no fixture without a model | completion on milestone codex_images_generated_frozen |
| `freeze_codex_image_batch` | `tool` | same input → same action; fixture-testable; receipt not opinion; junior can implement from schema | listed toolbox function for this milestone |
| `codex_images_generated_judge` | `tool` | same input → same action; fixture-testable; receipt not opinion; junior can implement from schema | listed toolbox function for this milestone |
| `image_video_prompts_frozen` | `intelligence` | fails at least one of the four tests; no fixture without a model | completion on milestone image_video_prompts_frozen |
| `image_video_prompts_judge` | `tool` | same input → same action; fixture-testable; receipt not opinion; junior can implement from schema | listed toolbox function for this milestone |
| `grok_build_acp_image_video_batch` | `tool` | same input → same action; fixture-testable; receipt not opinion; junior can implement from schema | listed toolbox function for this milestone |
| `validate_grok_image_video_batch` | `tool` | same input → same action; fixture-testable; receipt not opinion; junior can implement from schema | listed toolbox function for this milestone |
| `grok_image_videos_generated_judge` | `tool` | same input → same action; fixture-testable; receipt not opinion; junior can implement from schema | listed toolbox function for this milestone |

## Current tools

| Unit | Kind | Class | Path |
| --- | --- | --- | --- |
| `prepare_visual_prompt_batch` | declared_toolbox | `tool` | `flowsteps/tools/prepare_visual_prompt_batch/` |
| `prompt_batch_ready` | flow_handler | `tool` | `milestones/prompt_batch_ready/assemble.py` |
| `freeze_codex_image_batch` | declared_toolbox | `tool` | `flowsteps/tools/freeze_codex_image_batch/` |
| `codex_images_generated_judge` | declared_toolbox | `tool` | `flowsteps/tools/codex_images_generated_judge/` |
| `codex_images_generated_frozen` | flow_handler | `tool` | `milestones/codex_images_generated_frozen/assemble.py` |
| `image_video_prompts_judge` | declared_toolbox | `tool` | `flowsteps/tools/image_video_prompts_judge/` |
| `image_video_prompts_frozen` | flow_handler | `tool` | `milestones/image_video_prompts_frozen/assemble.py` |
| `grok_build_acp_image_video_batch` | declared_toolbox | `tool` | `flowsteps/tools/grok_build_acp_image_video_batch/` |
| `validate_grok_image_video_batch` | declared_toolbox | `tool` | `flowsteps/tools/validate_grok_image_video_batch/` |
| `grok_image_videos_generated_judge` | declared_toolbox | `tool` | `flowsteps/tools/grok_image_videos_generated_judge/` |
| `grok_videos_generated_frozen` | flow_handler | `tool` | `milestones/grok_videos_generated_frozen/assemble.py` |

## Proposed milestone split

The M8M flowchart (gates, foreach, toolbox plan) is `planning/m8m-flowchart.md`.

## Toolbox plan

Tools on each proposed milestone. **Existing toolbox** = already in
`<repo>/flowsteps/tools/` or an M8M seed. **Promote from a skill script** =
skill-private Python becomes that tool. **Generate new** = builder should
develop this tool; a stub is a successful sketch.

| Milestone | Intelligence | Existing toolbox | Promote from a skill script | Generate new |
| --- | --- | --- | --- | --- |
| `prompt_batch_ready` | `none` | `prepare_visual_prompt_batch` | — | — |
| `codex_images_generated_frozen` | `completion` | `freeze_codex_image_batch`<br>`codex_images_generated_judge` | — | — |
| `image_video_prompts_frozen` | `completion` | `image_video_prompts_judge` | — | — |
| `grok_videos_generated_frozen` | `none` | `grok_build_acp_image_video_batch`<br>`validate_grok_image_video_batch`<br>`grok_image_videos_generated_judge` | — | — |
## Teaching contracts

Same rule as tools. Teaching, instruction context, and judge rubrics
live on the **flow** (`flowsteps/flows/<id>/references/`), not in
`~/.codex/skills` or `~/.claude/skills`. Promote markdown from the
skill `references/`.

| Contract | Existing on the flow | Promote from skill references |
| --- | --- | --- |
| `codex_images_generated_frozen` | `references/codex_images_generated_frozen.md` | — |
| `grok_videos_generated_frozen` | `references/grok_videos_generated_frozen.md` | — |
| `image_video_prompts_frozen` | `references/image_video_prompts_frozen.md` | — |
| `prompt_batch_ready` | `references/prompt_batch_ready.md` | — |

| # | Milestone | Declared output ports | Success | Intelligence | Python tools | Output contract | Human inspects |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | `prompt_batch_ready` | `batch` (json, one) | The non-empty source prompt array is preserved verbatim in source order, assigned stable prompt-NNN IDs, and frozen with built-in Codex ImageGen plus fixed 6-second vertical 9:16 720p video settings. | `none` | `prepare_visual_prompt_batch` | `visual_prompt_batch_v1` | PASS payload `visual_prompt_batch_v1` |
| 2 | `codex_images_generated_frozen` | `images` (image, many), `manifest` (json, one) | Exactly one readable 9:16 image generated by Codex built-in ImageGen is frozen for every source prompt, with stable order, original prompt mapping, dimensions, byte count, and checksum. | `completion` | `freeze_codex_image_batch`, `codex_images_generated_judge` | `codex_image_batch_v1` | PASS payload `codex_image_batch_v1` |
| 3 | `image_video_prompts_frozen` | `video_prompts` (json, one), `manifest` (json, one) | The chosen strict JSON array contains exactly one bold 3-second forward animation prompt per frozen infographic image in source order; every prompt uses its corresponding image as the exact final still, specifies a large object-specific transformation, and satisfies the supplied style, continuity, aspect-ratio, final-hold, and negative constraints. | `completion` | `image_video_prompts_judge` | `image_video_prompt_batch_v1` | PASS payload `image_video_prompt_batch_v1` |
| 4 | `grok_videos_generated_frozen` | `videos` (video, many), `receipt` (json, one) | Exactly one playable approximately 3-second vertical 9:16 720p forward MP4 exists for every frozen Codex image; every clip ends on its matching target still, derives from a fresh 6-second Grok reverse master in one authenticated ACP process and session, and the complete receipt proves the ordered mapping and reverse-and-2x transform. | `none` | `grok_build_acp_image_video_batch`, `validate_grok_image_video_batch`, `grok_image_videos_generated_judge` | `grok_image_video_batch_v1` | PASS payload `grok_image_video_batch_v1` |

## Tools to standardize to Python

| Current unit | Proposed tool_id | Destination | Action | Why |
| --- | --- | --- | --- | --- |
| `prepare_visual_prompt_batch` | `prepare_visual_prompt_batch` | `flowsteps/tools/prepare_visual_prompt_batch/` | `already_python` | already listed on the milestone; keep as standardized Python toolbox |
| `freeze_codex_image_batch` | `freeze_codex_image_batch` | `flowsteps/tools/freeze_codex_image_batch/` | `already_python` | already listed on the milestone; keep as standardized Python toolbox |
| `codex_images_generated_judge` | `codex_images_generated_judge` | `flowsteps/tools/codex_images_generated_judge/` | `already_python` | already listed on the milestone; keep as standardized Python toolbox |
| `image_video_prompts_judge` | `image_video_prompts_judge` | `flowsteps/tools/image_video_prompts_judge/` | `already_python` | already listed on the milestone; keep as standardized Python toolbox |
| `grok_build_acp_image_video_batch` | `grok_build_acp_image_video_batch` | `flowsteps/tools/grok_build_acp_image_video_batch/` | `already_python` | already listed on the milestone; keep as standardized Python toolbox |
| `validate_grok_image_video_batch` | `validate_grok_image_video_batch` | `flowsteps/tools/validate_grok_image_video_batch/` | `already_python` | already listed on the milestone; keep as standardized Python toolbox |
| `grok_image_videos_generated_judge` | `grok_image_videos_generated_judge` | `flowsteps/tools/grok_image_videos_generated_judge/` | `already_python` | already listed on the milestone; keep as standardized Python toolbox |

## Schema control

Rule of success lives on each milestone gem. Candidate schema PASS validates declared ports.
judge = stay on this box until the worker accepts the current candidate; only then commit chosen-output.json.
cycle and branch keep their own receipts. Do not wrap them in a shared judge module.

| Milestone | Kind | Criterion | Detail |
| --- | --- | --- | --- |
| `codex_images_generated_frozen` | `judge` | `ok_receipt` | worker `codex_images_generated_judge` receipt `schemas/codex_images_generated_frozen_receipt_v1.json` |
| `grok_videos_generated_frozen` | `judge` | `ok_receipt` | worker `grok_image_videos_generated_judge` receipt `schemas/grok_videos_generated_frozen_receipt_v1.json` |

## FlowStep input and output schemas

### 1. `prompt_batch_ready`

- intelligence: `none`
- toolbox: `prepare_visual_prompt_batch`
- flowsteps (guide): `prepare_visual_prompt_batch`→`prepare_visual_prompt_batch`
- inputs: request=user.request
- output_contract: `visual_prompt_batch_v1`

**Input schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "prompt_batch_ready.input.schema.json",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "request"
  ],
  "properties": {
    "request": {
      "type": "object"
    }
  }
}
```

**Output schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "prompt_batch_ready.output.schema.json",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "outputs"
  ],
  "properties": {
    "outputs": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "batch"
      ],
      "properties": {
        "batch": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "schema",
            "count",
            "image",
            "video",
            "items"
          ],
          "properties": {
            "schema": {
              "const": "visual_prompt_batch_v1"
            },
            "count": {
              "type": "integer",
              "minimum": 1
            },
            "image": {
              "type": "object",
              "additionalProperties": false,
              "required": [
                "provider",
                "aspect_ratio"
              ],
              "properties": {
                "provider": {
                  "const": "codex_builtin_imagegen"
                },
                "aspect_ratio": {
                  "const": "9:16"
                }
              }
            },
            "video": {
              "type": "object",
              "additionalProperties": false,
              "required": [
                "duration_seconds",
                "aspect_ratio",
                "resolution"
              ],
              "properties": {
                "duration_seconds": {
                  "const": 6
                },
                "aspect_ratio": {
                  "const": "9:16"
                },
                "resolution": {
                  "const": "720p"
                }
              }
            },
            "items": {
              "type": "array",
              "minItems": 1,
              "items": {
                "type": "object",
                "additionalProperties": false,
                "required": [
                  "id",
                  "index",
                  "prompt"
                ],
                "properties": {
                  "id": {
                    "type": "string",
                    "pattern": "^prompt-[0-9]{3}$"
                  },
                  "index": {
                    "type": "integer",
                    "minimum": 0
                  },
                  "prompt": {
                    "type": "string",
                    "minLength": 1
                  }
                }
              }
            }
          }
        }
      }
    },
    "receipt": {
      "type": "object"
    }
  }
}
```

### 2. `codex_images_generated_frozen`

- intelligence: `completion`
- toolbox: `freeze_codex_image_batch`, `codex_images_generated_judge`
- flowsteps (guide): `generate_with_codex_builtin_imagegen`→`—`, `freeze_codex_image_batch`→`freeze_codex_image_batch`, `judge_codex_image_batch`→`codex_images_generated_judge`
- inputs: prompt_batch_ready=prompt_batch_ready.visual_prompt_batch_v1
- output_contract: `codex_image_batch_v1`

**Input schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "codex_images_generated_frozen.input.schema.json",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "prompt_batch_ready"
  ],
  "properties": {
    "prompt_batch_ready": {
      "$ref": "prompt_batch_ready.output.schema.json"
    }
  }
}
```

**Output schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "codex_images_generated_frozen.output.schema.json",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "outputs",
    "receipt"
  ],
  "properties": {
    "outputs": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "images",
        "manifest"
      ],
      "properties": {
        "images": {
          "type": "array",
          "minItems": 1,
          "items": {
            "$ref": "#/$defs/image"
          }
        },
        "manifest": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "schema",
            "provider",
            "count",
            "aspect_ratio",
            "items"
          ],
          "properties": {
            "schema": {
              "const": "codex_image_batch_v1"
            },
            "provider": {
              "const": "codex_builtin_imagegen"
            },
            "count": {
              "type": "integer",
              "minimum": 1
            },
            "aspect_ratio": {
              "const": "9:16"
            },
            "items": {
              "type": "array",
              "minItems": 1,
              "items": {
                "$ref": "#/$defs/image"
              }
            }
          }
        }
      }
    },
    "receipt": {
      "type": "object",
      "additionalProperties": true,
      "required": [
        "ok",
        "code",
        "count",
        "provider"
      ],
      "properties": {
        "ok": {
          "const": true
        },
        "code": {
          "const": "pass"
        },
        "count": {
          "type": "integer",
          "minimum": 1
        },
        "provider": {
          "const": "codex_builtin_imagegen"
        }
      }
    }
  },
  "$defs": {
    "image": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "id",
        "stable_id",
        "name",
        "path",
        "index",
        "source_prompt",
        "image_prompt",
        "sha256",
        "bytes",
        "width",
        "height",
        "mime_type",
        "image_format"
      ],
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^prompt_[0-9]{3}$"
        },
        "stable_id": {
          "type": "string",
          "pattern": "^prompt-[0-9]{3}$"
        },
        "name": {
          "type": "string",
          "minLength": 1
        },
        "path": {
          "type": "string",
          "minLength": 1
        },
        "index": {
          "type": "integer",
          "minimum": 0
        },
        "source_prompt": {
          "type": "string",
          "minLength": 1
        },
        "image_prompt": {
          "type": "string",
          "minLength": 1
        },
        "sha256": {
          "type": "string",
          "pattern": "^[a-f0-9]{64}$"
        },
        "bytes": {
          "type": "integer",
          "minimum": 1
        },
        "width": {
          "type": "integer",
          "minimum": 1
        },
        "height": {
          "type": "integer",
          "minimum": 1
        },
        "mime_type": {
          "enum": [
            "image/png",
            "image/jpeg",
            "image/webp"
          ]
        },
        "image_format": {
          "type": "string",
          "minLength": 1
        }
      }
    }
  }
}
```

### 3. `image_video_prompts_frozen`

- intelligence: `completion`
- toolbox: `image_video_prompts_judge`
- flowsteps (guide): `inspect_frozen_images`→`—`, `construct_image_video_prompts`→`—`, `judge_image_video_prompts`→`image_video_prompts_judge`
- inputs: codex_images_generated_frozen=codex_images_generated_frozen.codex_image_batch_v1
- output_contract: `image_video_prompt_batch_v1`

**Input schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "image_video_prompts_frozen.input.schema.json",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "codex_images_generated_frozen"
  ],
  "properties": {
    "codex_images_generated_frozen": {
      "$ref": "codex_images_generated_frozen.output.schema.json"
    }
  }
}
```

**Output schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "image_video_prompts_frozen.output.schema.json",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "outputs",
    "receipt"
  ],
  "properties": {
    "outputs": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "video_prompts",
        "manifest"
      ],
      "properties": {
        "video_prompts": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "string",
            "minLength": 300
          }
        },
        "manifest": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "schema",
            "count",
            "format",
            "prompts",
            "items"
          ],
          "properties": {
            "schema": {
              "const": "image_video_prompt_batch_v1"
            },
            "count": {
              "type": "integer",
              "minimum": 1
            },
            "format": {
              "type": "object",
              "required": [
                "duration_seconds",
                "aspect_ratio",
                "resolution",
                "grok_master_duration_seconds",
                "temporal_transform"
              ]
            },
            "prompts": {
              "type": "array",
              "minItems": 1,
              "items": {
                "type": "string",
                "minLength": 300
              }
            },
            "items": {
              "type": "array",
              "minItems": 1,
              "items": {
                "type": "object",
                "required": [
                  "id",
                  "index",
                  "source_image_path",
                  "source_image_sha256",
                  "source_prompt",
                  "video_prompt"
                ]
              }
            }
          }
        }
      }
    },
    "receipt": {
      "type": "object",
      "required": [
        "ok",
        "code"
      ],
      "properties": {
        "ok": {
          "const": true
        },
        "code": {
          "const": "pass"
        }
      }
    }
  }
}
```

### 4. `grok_videos_generated_frozen`

- intelligence: `none`
- toolbox: `grok_build_acp_image_video_batch`, `validate_grok_image_video_batch`, `grok_image_videos_generated_judge`
- flowsteps (guide): `run_persistent_grok_image_video_batch`→`grok_build_acp_image_video_batch`, `validate_grok_image_video_batch`→`validate_grok_image_video_batch`, `judge_grok_image_video_batch`→`grok_image_videos_generated_judge`
- inputs: image_video_prompts_frozen=image_video_prompts_frozen.image_video_prompt_batch_v1
- output_contract: `grok_image_video_batch_v1`

**Input schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "grok_videos_generated_frozen.input.schema.json",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "image_video_prompts_frozen"
  ],
  "properties": {
    "image_video_prompts_frozen": {
      "$ref": "image_video_prompts_frozen.output.schema.json"
    }
  }
}
```

**Output schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "grok_videos_generated_frozen.output.schema.json",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "outputs",
    "receipt"
  ],
  "properties": {
    "outputs": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "videos",
        "receipt"
      ],
      "properties": {
        "videos": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "object",
            "additionalProperties": true,
            "required": [
              "id",
              "stable_id",
              "name",
              "path",
              "index",
              "source_prompt",
              "source_image_path",
              "source_image_sha256",
              "video_prompt",
              "sha256",
              "bytes",
              "width",
              "height",
              "duration_seconds"
            ],
            "properties": {
              "id": {
                "type": "string",
                "pattern": "^video_[0-9]{3}$"
              },
              "stable_id": {
                "type": "string",
                "pattern": "^prompt-[0-9]{3}$"
              },
              "name": {
                "type": "string",
                "minLength": 1
              },
              "path": {
                "type": "string",
                "minLength": 1
              },
              "index": {
                "type": "integer",
                "minimum": 0
              },
              "source_prompt": {
                "type": "string",
                "minLength": 1
              },
              "source_image_path": {
                "type": "string",
                "minLength": 1
              },
              "source_image_sha256": {
                "type": "string",
                "pattern": "^[a-f0-9]{64}$"
              },
              "video_prompt": {
                "type": "string",
                "minLength": 1
              },
              "sha256": {
                "type": "string",
                "pattern": "^[a-f0-9]{64}$"
              },
              "bytes": {
                "type": "integer",
                "minimum": 1
              },
              "width": {
                "const": 720
              },
              "height": {
                "enum": [
                  1264,
                  1280
                ]
              },
              "duration_seconds": {
                "type": "number",
                "minimum": 2.8,
                "maximum": 3.2
              }
            }
          }
        },
        "receipt": {
          "type": "object",
          "additionalProperties": true,
          "required": [
            "schema",
            "transport",
            "session_id",
            "grok_version",
            "count",
            "format",
            "clips",
            "allowed_tools",
            "validation"
          ],
          "properties": {
            "schema": {
              "const": "grok_image_video_batch_receipt_v1"
            },
            "transport": {
              "const": "acp"
            },
            "session_id": {
              "type": "string",
              "minLength": 1
            },
            "grok_version": {
              "type": "string",
              "minLength": 1
            },
            "count": {
              "type": "integer",
              "minimum": 1
            },
            "format": {
              "type": "object"
            },
            "clips": {
              "type": "array",
              "minItems": 1
            },
            "allowed_tools": {
              "const": [
                "image_to_video"
              ]
            },
            "validation": {
              "type": "object"
            }
          }
        }
      }
    },
    "receipt": {
      "type": "object",
      "additionalProperties": true,
      "required": [
        "ok",
        "code",
        "count",
        "session_id"
      ],
      "properties": {
        "ok": {
          "const": true
        },
        "code": {
          "const": "pass"
        },
        "count": {
          "type": "integer",
          "minimum": 1
        },
        "session_id": {
          "type": "string",
          "minLength": 1
        }
      }
    }
  }
}
```

## Current harness grade

None.

This file is an audit. It does not rewrite the target skill.
