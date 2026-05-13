# Playwright + Chromium Setup for Screenshots — Full Step-by-Step

## Overview

This guide produces a working Playwright + Chromium setup that can take full-page screenshots of any website from within a restricted container. Every path uses `/fluso/user/` as the writable root.

---

## Step 1: Find Your Writable Root

```bash
touch /fluso/user/test && rm /fluso/user/test && echo "OK"
```

If this fails, find an alternative writable location. All paths below should be adjusted.

---

## Step 2: Install Playwright Browsers

The webapp-testing skill already bundles Playwright Python bindings. Install Chromium to a writable cache:

```bash
export PLAYWRIGHT_BROWSERS_PATH=/fluso/user/.cache/ms-playwright
mkdir -p $PLAYWRIGHT_BROWSERS_PATH
uv run --project /app/skills/webapp-testing playwright install chromium
```

This downloads:
- Chromium browser: `$PLAYWRIGHT_BROWSERS_PATH/chromium-1208/chrome-linux64/chrome`
- Headless shell: `$PLAYWRIGHT_BROWSERS_PATH/chromium_headless_shell-1208/.../chrome-headless-shell`
- FFmpeg: `$PLAYWRIGHT_BROWSERS_PATH/ffmpeg-1011/`

**Version note:** The version number (1208, 1011) changes with Playwright releases. Check with `ls $PLAYWRIGHT_BROWSERS_PATH`.

---

## Step 3: Resolve Missing Libraries

Chromium needs many shared libraries that may not exist in minimal containers. See [dependency-resolution.md](dependency-resolution.md) for the full list and download approach.

```bash
LIBS_DIR=/fluso/user/workspace/projects/Home/.browser-libs
```

After resolving all libraries, verify:

```bash
LD_LIBRARY_PATH=$LIBS_DIR/usr/lib/x86_64-linux-gnu:$LIBS_DIR/lib/x86_64-linux-gnu \
    ldd /path/to/chrome-headless-shell | grep "not found"
```

---

## Step 4: Install Fonts

See [font-setup.md](font-setup.md). Without fonts, all text renders as invisible rectangles.

---

## Step 5: Write Screenshot Script

```python
from playwright.sync_api import sync_playwright

output = "/fluso/user/workspace/projects/Home/files/screenshot.png"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        executable_path="/fluso/user/.cache/ms-playwright/chromium_headless_shell-1208/chrome-headless-shell-linux64/chrome-headless-shell",
        args=["--no-sandbox", "--disable-gpu"]
    )
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("https://target-site.com", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)
    page.screenshot(path=output, full_page=True)
    browser.close()
```

**Why headless shell, not full Chrome:** In restricted containers, the full `chrome` binary often crashes with SIGTRAP due to Crashpad handler failures. The headless shell renders identically for screenshots but skips the crash reporting infrastructure.

---

## Step 6: Run the Screenshot

```bash
export PLAYWRIGHT_BROWSERS_PATH=/fluso/user/.cache/ms-playwright
LIBS_DIR=/fluso/user/workspace/projects/Home/.browser-libs
export LD_LIBRARY_PATH=$LIBS_DIR/usr/lib/x86_64-linux-gnu:$LIBS_DIR/lib/x86_64-linux-gnu
export FONTCONFIG_PATH=/tmp/fontconfig

uv run --project /app/skills/webapp-testing python screenshot.py
```

---

## Step 7: Verify Output

```bash
ls -lh /fluso/user/workspace/projects/Home/files/screenshot.png
```

If the file is suspiciously small (<50KB), check:
1. Are fonts installed and FONTCONFIG_PATH set?
2. Are all shared libraries resolved?
3. Does the URL return a valid page? (test with curl first)

---

## Full Environment Summary

```bash
export PLAYWRIGHT_BROWSERS_PATH=/fluso/user/.cache/ms-playwright
export LD_LIBRARY_PATH=/fluso/user/workspace/projects/Home/.browser-libs/usr/lib/x86_64-linux-gnu:/fluso/user/workspace/projects/Home/.browser-libs/lib/x86_64-linux-gnu
export FONTCONFIG_PATH=/tmp/fontconfig
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `Executable doesn't exist` | Wrong Chromium path | `ls $PLAYWRIGHT_BROWSERS_PATH` to find correct version dir |
| `libglib-2.0.so.0: not found` | Missing system libs | Run dependency resolution |
| Screenshot has no text / blank areas | No fonts | Run font setup |
| `Target page closed` / SIGTRAP | Full Chrome crash | Use headless shell instead |
| `Read-only file system` on mkdir | Writing to `~` | Use `/fluso/user/` paths |
| `FONTCONFIG_PATH` not working | fonts.conf missing or wrong | Verify `/tmp/fontconfig/fonts.conf` exists |
