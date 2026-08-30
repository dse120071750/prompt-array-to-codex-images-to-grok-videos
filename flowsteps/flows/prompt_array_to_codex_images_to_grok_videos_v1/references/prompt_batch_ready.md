# Prompt batch ready

PASS only when `prompts` is a non-empty array of non-blank strings. Preserve
every string byte-for-byte and preserve source order. Assign `prompt-001`,
`prompt-002`, and subsequent IDs. Freeze image generation to Codex built-in
ImageGen and request vertical 9:16 output. Freeze video generation to 6 seconds,
vertical 9:16, and 720p. Reject all provider, path, duration, aspect-ratio,
resolution, credential, and API overrides.
