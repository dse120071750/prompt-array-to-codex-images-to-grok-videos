# Grok image-derived videos generated and frozen

Start exactly one `grok agent stdio` ACP process and authenticate only with
`cached_token`. Create exactly one session and reuse its session ID for the full
batch. Disable updates, memory, subagents, default tools, inherited skills, MCP,
and web search. Expose and approve only `image_to_video`.

For each item in source order, copy the exact frozen Codex image to the isolated
ACP scratch directory as `images/prompt-NNN.<ext>`. Send one ACP turn that tells
Grok to call `image_to_video` exactly once with that relative image path, a
deterministic reverse-master instruction containing the matching frozen
forward motion prompt verbatim, duration `6`, and resolution name `720p`.
The source image is the target final still: hold it unchanged for the first
second, then generate the reverse of the requested large action over the next
five seconds. Do not call `image_gen`, edit the source, synthesize a
replacement, parse a media path from assistant prose, or use another image.

Compare the exact session media directory before and after each turn and require
exactly one new non-empty MP4. Preserve that 6-second provider result as the
reverse master, then use the repository-bundled FFmpeg to reverse it and apply
2x temporal acceleration, producing canonical `prompt-NNN.mp4`. Record both
master and final checksums, the source image checksum, forward and Grok prompts,
temporal transform, stop reason, assistant text, and byte counts, then continue.
Validate every final clip with bundled ffprobe as MP4, 720 pixels wide with
either Grok's native 1264-pixel height or a 1280-pixel height (both accepted as
approximately vertical 9:16), about three seconds, and containing a video
stream. The final clip must end on the exact target-reference composition.

Any failure invalidates the full milestone; publish no partial chosen bundle.
Preserve the failed attempt for diagnostics. Never fall back to the xAI REST
API, another provider, a one-shot Grok command, or an earlier clip. Require
cached login and either privacy off or valid user-hosted ZDR video storage before
opening the session. Never change privacy or provision storage automatically.
