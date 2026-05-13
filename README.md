# headless-browser-setup

**Self-bootstrapping Playwright + Chromium setup for visual screenshots in restricted container environments.**

No `apt-get`. No system fonts. Read-only home directory. This script handles everything — library resolution, font installation, fontconfig, and verification — in one command.

```bash
python3 scripts/bootstrap.py
```

---

## What It Solves

Taking screenshots with headless Chromium in a minimal Debian container typically fails because:

- **Missing shared libraries** — `libglib-2.0.so.0`, `libatk-1.0.so.0`, `libX11.so.6`, and 30+ others aren't installed
- **No fonts** — text renders as invisible rectangles even when the page loads perfectly
- **Read-only filesystem** — `~/.cache`, `~/.config`, and `~/.local` may not be writable
- **No package manager** — `apt-get` has read-only apt lists or no network access to repos

This script detects all of these issues and fixes them automatically.

---

## Quick Start

### Prerequisites

- Python 3.11+
- `curl`, `dpkg-deb`, `ldd` (available on any Debian-based system)
- Playwright Python bindings (the script can install Chromium via `uv run playwright install chromium`)

### One Command

```bash
git clone https://github.com/Killthebug/headless-browser-setup.git
cd headless-browser-setup
python3 scripts/bootstrap.py
```

### What Happens

The script runs through 6 phases:

```
── Phase 1: Environment detection
  ✓ Writable root: /fluso/user
  • Project:     /fluso/user/workspace/projects/Home
  • Libs dir:    /fluso/user/workspace/projects/Home/.browser-libs
  • Browsers:    /fluso/user/.cache/ms-playwright

── Phase 2: Playwright Chromium
  ✓ Chromium found at .../chrome-headless-shell

── Phase 3: Resolving shared libraries
  • Found 20 missing libraries
  • libglib-2.0.so.0, libX11.so.6, libnss3.so, ...
  • [1/20] Resolving libglib-2.0.so.0...
  • [2/20] Resolving libgobject-2.0.so.0...
  ...
  ✓ All 20 libraries resolved!

── Phase 4: Fonts
  ✓ DejaVu fonts installed
  ✓ fontconfig written to /tmp/fontconfig/fonts.conf

── Phase 5: Environment file
  ✓ Written: .browser-libs/env.sh

── Phase 6: Test screenshot
  ✓ Test screenshot: files/bootstrap-test.png (13KB)
  ✓ Setup complete and verified!
```

### After Bootstrap

Every subsequent screenshot run just needs:

```bash
source .browser-libs/env.sh
uv run --project /app/skills/webapp-testing python your_screenshot_script.py
```

---

## Options

```
--writable-root PATH    Custom writable root (default: auto-detect)
--project-dir PATH      Project directory (default: CWD)
--test-url URL          URL for test screenshot (default: https://example.com)
--skip-test             Skip the verification screenshot
```

---

## How Library Resolution Works

Two-tier approach for each missing `.so` file:

**Tier 1 — Known mappings (fast):** The script has 39 hardcoded mappings from `.so` names to Debian Bookworm package names, pool paths, and exact filenames. For example:

```python
"libglib-2.0.so.0": ("libglib2.0-0", "g/glib2.0", "libglib2.0-0_2.74.6-2+deb12u5_amd64.deb")
"libX11.so.6":      ("libx11-6",     "libx/libx11", "libx11-6_1.8.4-2+deb12u2_amd64.deb")
"libnss3.so":       ("libnss3",      "n/nss",       "libnss3_3.87.1-1+deb12u1_amd64.deb")
```

It downloads from `https://mirrors.ocf.berkeley.edu/debian/pool/main/` and extracts with `dpkg-deb -x`.

**Tier 2 — Web lookup (fallback):** If a mapping is unknown or the download 404s (e.g., after a Debian point release changes filenames), the script queries `packages.debian.org` to find the current package name and download URL dynamically.

### Complete Library Map

| .so File | Debian Package |
|----------|---------------|
| libglib-2.0.so.0 | libglib2.0-0 |
| libgobject-2.0.so.0 | libglib2.0-0 |
| libgio-2.0.so.0 | libglib2.0-0 |
| libatk-1.0.so.0 | libatk1.0-0 |
| libatk-bridge-2.0.so.0 | libatk-bridge2.0-0 |
| libdbus-1.so.3 | libdbus-1-3 |
| libcups.so.2 | libcups2 |
| libX11.so.6 | libx11-6 |
| libXext.so.6 | libxext6 |
| libXcomposite.so.1 | libxcomposite1 |
| libXdamage.so.1 | libxdamage1 |
| libXfixes.so.3 | libxfixes3 |
| libXrandr.so.2 | libxrandr2 |
| libXrender.so.1 | libxrender1 |
| libXi.so.6 | libxi6 |
| libXtst.so.6 | libxtst6 |
| libxcb.so.1 | libxcb1 |
| libxkbcommon.so.0 | libxkbcommon0 |
| libgbm.so.1 | libgbm1 |
| libasound.so.2 | libasound2 |
| libdrm.so.2 | libdrm2 |
| libthai.so.0 | libthai0 |
| libharfbuzz.so.0 | libharfbuzz0b |
| libdatrie.so.1 | libdatrie1 |
| libpango-1.0.so.0 | libpango-1.0-0 |
| libpangocairo-1.0.so.0 | libpango-1.0-0 |
| libcairo.so.2 | libcairo2 |
| libpixman-1.so.0 | libpixman-1-0 |
| libfontconfig.so.1 | libfontconfig1 |
| libfreetype.so.6 | libfreetype6 |
| libexpat.so.1 | libexpat1 |
| libnss3.so | libnss3 |
| libnssutil3.so | libnss3 |
| libnspr4.so | libnspr4 |
| libsmime3.so | libnss3 |
| libssl3.so | libnss3 |
| libatspi.so.0 | libatspi2.0-0 |

---

## Font Setup

The script installs **DejaVu fonts** (DejaVu Sans, Serif, Mono — all with Bold variants) and creates a fontconfig configuration that maps the generic CSS families (`sans-serif`, `serif`, `monospace`) to them.

Without this step, headless Chromium finds zero fonts and renders all text as invisible rectangles — the DOM is there, the layout is correct, but glyphs can't be rasterized.

Optional: swap in **Noto** (broader script coverage) or **Liberation** (metric-compatible with Arial / Times New Roman / Courier New) by editing the font download URLs in `scripts/bootstrap.py`.

---

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

**Always use `chrome-headless-shell`, not full `chrome`.** Full Chrome often crashes with SIGTRAP in containers due to Crashpad handler failures. The headless shell renders identically for screenshots.

---

## Why Not Just apt-get?

In many CI/CD and sandboxed environments:

- `apt-get update` fails because `/var/lib/apt/lists/` is read-only
- Package installation requires root, but the container runs as non-root
- Network policy blocks connections to apt repositories
- You need libraries in a specific directory, not system-wide

This script works around all of these constraints by downloading `.deb` packages directly from HTTPS mirrors and extracting them to a local directory — no root, no apt, no system modifications.

---

## Environment Variables

After bootstrap, source the generated env file:

```bash
source .browser-libs/env.sh
```

This exports:

| Variable | Value |
|----------|-------|
| `PLAYWRIGHT_BROWSERS_PATH` | Path to Playwright's browser cache |
| `LD_LIBRARY_PATH` | Paths to extracted `.so` files |
| `FONTCONFIG_PATH` | Path to fontconfig directory with `fonts.conf` |

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Screenshot has no text | No fonts installed | Re-run bootstrap |
| `Target page closed` / SIGTRAP | Using full Chrome, not headless shell | Bootstrap auto-selects headless shell |
| `lib*.so: not found` even after bootstrap | New library not in known mappings | Falls back to web lookup; add to `KNOWN_LIBS` if persistent |
| `Read-only file system` error | Writing to `~` instead of `/fluso/user/` | Bootstrap auto-detects writable root |
| Download 404s for a known library | Debian point release changed filenames | Web lookup fallback handles this |

---

## Files

```
.
├── README.md
├── SKILL.md                              # Fluso skill definition
├── scripts/
│   └── bootstrap.py                      # Self-bootstrapping setup script
└── references/
    ├── playwright-chromium-setup.md      # 7-step manual walkthrough
    ├── dependency-resolution.md          # Library-by-library resolution guide
    └── font-setup.md                     # Font installation & fontconfig guide
```

---

## License

MIT
