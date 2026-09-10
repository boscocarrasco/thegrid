# DECISIONS.md

Every decision taken autonomously, with a one-line justification. Newest at the
bottom of each section.

## D0 — Budget

**D0.1 `MAX_WALL_CLOCK_HOURS` and `MAX_API_SPEND_USD` are unset in this
container, so the defaults from the brief apply: 8 h and 40 USD.**
The brief specifies those fallbacks explicitly; wall clock starts at the first
command of the session (2026-09-10 04:25 UTC), so the 85 % stop line is
≈11:13 UTC / 34 USD.

## D1 — Environment

**D1.1 Project interpreter is `/usr/bin/python3.12`, not the `python3` on
`PATH` (3.11).** The image ships a 3.11 that shadows the system interpreter,
but the Debian `gir1.2-atspi-2.0` / `python3-gi` bindings are compiled for
3.12 — `import gi` fails on 3.11 and works on 3.12, and without AT-SPI there
is no experiment.

**D1.2 Desktop is Xvfb `:99` at 1920×1080×24, DPI pinned to 96, `-noreset`.**
The spec requires fixed resolution and scale so coordinates never change
meaning between runs; `-noreset` stops the server from wiping state when the
last client exits between tasks.

**D1.3 One shared D-Bus session bus is created by `scripts/env_up.sh` and
exported through `/tmp/grid-env/env.sh`.** AT-SPI is a bus protocol: the
observer and the applications must sit on the same session bus or the tree
comes back empty, and `dbus-run-session` per-process would give each its own.

**D1.4 GUI applications are mousepad (GTK3 editor), pcmanfm (GTK3 file
manager), LibreOffice Calc (gtk3 VCL plugin) and Chromium.** They are the
lightest real GTK/Qt apps that cover the coverage classes the brief demands
(files, text, spreadsheet, browser) and all four populate AT-SPI; heavier
choices (GNOME Files, gedit) pull a full desktop session into the image.

**D1.5 `SAL_USE_VCLPLUGIN=gtk3` + `OOO_FORCE_DESKTOP=gnome` are forced for
LibreOffice.** Under the default `gen` VCL plugin LibreOffice exposes almost
nothing over AT-SPI; with the gtk3 plugin the gate check sees 753 actionable
elements.

## D2 — Model access

**D2.1 Model calls go through the `claude` CLI in headless
(`--print`) mode rather than a raw `POST /v1/messages`.** No
`ANTHROPIC_API_KEY` exists in this container and the Anthropic endpoint
returns 401 without one; the CLI is authenticated by the host and returns
per-call `usage` (input, output, `cache_creation_input_tokens`,
`cache_read_input_tokens`) plus `total_cost_usd`, which is exactly the
accounting the brief asks for.

**D2.2 The CLI is stripped to a bare model call with
`--system-prompt … --tools "" --strict-mcp-config --setting-sources ""
--disable-slash-commands`.** The default Claude Code preamble costs ~41 k
tokens per call (~$0.038); stripped it costs ~1.1 k (~$0.0045), which both
fits the 40 USD budget and stops the harness's own prompt from swamping the
observation tokens being measured. The residual ~1.1 k is identical across
arms, so it cannot bias the comparison, and it is recorded per run.

**D2.3 Temperature is not settable through the CLI, so it is held constant by
construction instead of being pinned to a value.** All arms go through the
identical call path with identical decoding settings; the brief's requirement
is that temperature not differ *between arms*, which is satisfied. Recorded as
a threat to validity because it is not 0.

## D3 — Experiment design

*(filled in as the harness is built)*
