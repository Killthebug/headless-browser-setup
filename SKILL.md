---
name: headless-browser-setup
description: Complete Playwright + Chromium setup for visual screenshots in restricted container/CI environments (no apt, no system fonts, read-only home). Includes a self-bootstrapping script that auto-detects missing libraries, downloads from Debian mirrors, installs fonts, and verifies with a test screenshot. Trigger when the user needs to take screenshots of web pages, set up a headless browser for visual rendering, or resolve Chromium dependency issues in sandboxed/minimal environments.
---

# Playwright + Chromium Setup for Screenshots

Complete end-to-end setup for taking visual screenshots with Chromium in restricted environments — no apt, no system fonts, read-only home directories.

---

## Quick Decision

| Use this skill when... | Don't use when... |
|------------------------|-------------------|
| You need visual PNG screenshots of web pages | You need text/markdown extraction only |
| The environment lacks apt/system fonts | apt and fonts are already available |
| Home directory is read-only | Standard `playwright install` works |
| Container is Debian Bookworm minimal | You need text-only extraction without visual rendering |

---

## Primary Path: Bootstrap Script (Recommended)

The `scripts/bootstrap.py` script handles the entire setup automatically:

```bash
python3 /fluso/user/workspace/skills/headless-browser-setup/scripts/bootstrap.py
```

It goes through 6 phases:
1. **Environment detection** — finds writable root, sets up paths
2. **Chromium install** — installs Playwright Chromium if not present
3. **Library resolution** — runs `ldd`, finds missing .so files, downloads matching .deb packages
4. **Font installation** — downloads DejaVu fonts, creates fontconfig
5. **Environment file** — writes `env.sh` with all required exports
6. **Test screenshot** — takes a real screenshot to verify everything works

After running, source the generated env file for all subsequent screenshot commands:

```bash
source .browser-libs/env.sh
```

### Bootstrap Options

```
--writable-root PATH    Custom writable root (default: auto-detect)
--project-dir PATH      Project directory (default: CWD)
--test-url URL          URL for test screenshot (default: https://example.com)
--skip-test             Skip the verification screenshot
```

### How Library Resolution Works

The script uses a two-tier approach for each missing library:

1. **Known mappings** — 35+ libraries have hardcoded Debian Bookworm package names, pool paths, and filenames. Fast and reliable.
2. **Web lookup fallback** — if a known mapping fails or the lib is unknown, queries `packages.debian.org` to find the correct package and download URL dynamically.

This means the script survives Debian point releases where filenames change.

### After Bootstrap

Every screenshot run needs just two commands:

```bash
source .browser-libs/env.sh
uv run --project /app/skills/webapp-testing python files/screenshot.py
```

## Screenshot Script Template

```python
from playwright.sync_api import sync_playwright

output = "/fluso/user/workspace/projects/Home/files/screenshot.png"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        executable_path="/fluso/user/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell",
        args=["--no-sandbox", "--disable-gpu"]
    )
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("https://target-site.com", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)
    page.screenshot(path=output, full_page=True)
    browser.close()
```

**Use `chrome-headless-shell`, not full `chrome`.** Full Chrome often crashes with SIGTRAP in containers.

---

## Manual Fallback Path

If the bootstrap script can't be used, follow the manual steps in these references:

- [playwright-chromium-setup.md](references/playwright-chromium-setup.md) — 7-step manual walkthrough
- [dependency-resolution.md](references/dependency-resolution.md) — Library-by-library resolution with batch download script
- [font-setup.md](references/font-setup.md) — Font installation and fontconfig with complete XML

---

## Common Pitfalls

1. **Full Chrome vs Headless Shell:** Full Chrome can crash with SIGTRAP. Always use `chrome-headless-shell`.
2. **Fonts are essential:** Without fonts, text renders as blank/invisible rectangles.
3. **LD_LIBRARY_PATH must be set before launch:** The dynamic linker reads it at process start.
4. **Read-only home:** Everything goes under `/fluso/user/` — config, cache, libs, output files.
5. **FONTCONFIG_PATH must point to directory containing fonts.conf, not the file itself.**

## Env Vars (from env.sh)

```bash
export PLAYWRIGHT_BROWSERS_PATH=/fluso/user/.cache/ms-playwright
export LD_LIBRARY_PATH=<project>/.browser-libs/usr/lib/x86_64-linux-gnu:<project>/.browser-libs/lib/x86_64-linux-gnu
export FONTCONFIG_PATH=/tmp/fontconfig
```

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `Executable doesn't exist` | Wrong Chromium path | Re-run bootstrap or check `$PLAYWRIGHT_BROWSERS_PATH` |
| `libglib-2.0.so.0: not found` | Missing system libs | Re-run bootstrap — it resolves all libs |
| Screenshot has no text | No fonts | Re-run bootstrap — it installs DejaVu |
| `Target page closed` / SIGTRAP | Full Chrome crash | Use headless shell (bootstrap auto-selects it) |
| `Read-only file system` | Writing to `~` | Bootstrap auto-detects writable root |
| Bootstrap can't resolve a lib | Unknown/new library | Add it to `KNOWN_LIBS` in the script, or follow manual references |
