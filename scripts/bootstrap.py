#!/usr/bin/env python3
"""
Self-bootstrapping Playwright + Chromium setup for restricted containers.

Detects environment, resolves all missing shared libraries from Debian mirrors,
installs fonts, configures fontconfig, and verifies with a test screenshot.

Dependencies: Python 3 stdlib only (no pip packages needed).
Requires: curl, dpkg-deb (from dpkg), ldd, and Playwright Python bindings.

Usage:
    python3 bootstrap.py [--writable-root /fluso/user] [--test-url https://example.com]

Outputs:
    - All extracted libraries under <writable-root>/.../projects/<project>/.browser-libs/
    - Fonts under .browser-libs/usr/share/fonts/
    - fontconfig at /tmp/fontconfig/fonts.conf
    - Environment file at .browser-libs/env.sh
    - Test screenshot at files/bootstrap-test.png
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
from pathlib import Path

DEBIAN_MIRROR = "https://mirrors.ocf.berkeley.edu/debian"
PACKAGES_BASE = "https://packages.debian.org"
DEBIAN_SUITE = "bookworm"
DEBIAN_ARCH = "amd64"

KNOWN_LIBS = {
    "libglib-2.0.so.0":       ("libglib2.0-0",       "g/glib2.0",     "libglib2.0-0_2.74.6-2+deb12u5_amd64.deb"),
    "libgobject-2.0.so.0":    ("libglib2.0-0",       "g/glib2.0",     "libglib2.0-0_2.74.6-2+deb12u5_amd64.deb"),
    "libgthread-2.0.so.0":    ("libglib2.0-0",       "g/glib2.0",     "libglib2.0-0_2.74.6-2+deb12u5_amd64.deb"),
    "libgio-2.0.so.0":        ("libglib2.0-0",       "g/glib2.0",     "libglib2.0-0_2.74.6-2+deb12u5_amd64.deb"),
    "libgmodule-2.0.so.0":    ("libglib2.0-0",       "g/glib2.0",     "libglib2.0-0_2.74.6-2+deb12u5_amd64.deb"),
    "libatk-1.0.so.0":        ("libatk1.0-0",        "a/at-spi2-core","libatk1.0-0_2.46.0-5_amd64.deb"),
    "libatk-bridge-2.0.so.0": ("libatk-bridge2.0-0", "a/at-spi2-core","libatk-bridge2.0-0_2.46.0-5_amd64.deb"),
    "libdbus-1.so.3":         ("libdbus-1-3",         "d/dbus",        "libdbus-1-3_1.14.10-1~deb12u1_amd64.deb"),
    "libcups.so.2":           ("libcups2",            "c/cups",        "libcups2_2.4.2-3+deb12u9_amd64.deb"),
    "libXext.so.6":           ("libxext6",            "libx/libxext",  "libxext6_1.3.4-1+b1_amd64.deb"),
    "libX11.so.6":            ("libx11-6",            "libx/libx11",   "libx11-6_1.8.4-2+deb12u2_amd64.deb"),
    "libXcomposite.so.1":     ("libxcomposite1",      "libx/libxcomposite","libxcomposite1_0.4.5-1_amd64.deb"),
    "libXdamage.so.1":        ("libxdamage1",         "libx/libxdamage","libxdamage1_1.1.6-1_amd64.deb"),
    "libXfixes.so.3":         ("libxfixes3",          "libx/libxfixes","libxfixes3_6.0.0-2_amd64.deb"),
    "libXrandr.so.2":         ("libxrandr2",          "libx/libxrandr","libxrandr2_1.5.2-2+b1_amd64.deb"),
    "libXrender.so.1":        ("libxrender1",         "libx/libxrender","libxrender1_0.9.10-1.1_amd64.deb"),
    "libxcb.so.1":            ("libxcb1",             "libx/libxcb",   "libxcb1_1.15-1_amd64.deb"),
    "libxkbcommon.so.0":      ("libxkbcommon0",       "libx/libxkbcommon","libxkbcommon0_1.5.0-1_amd64.deb"),
    "libgbm.so.1":            ("libgbm1",             "m/mesa",        "libgbm1_22.3.6-1+deb12u1_amd64.deb"),
    "libasound.so.2":         ("libasound2",          "a/alsa-lib",    "libasound2_1.2.8-1+b1_amd64.deb"),
    "libXi.so.6":             ("libxi6",              "libx/libxi",    "libxi6_1.8-1+b1_amd64.deb"),
    "libXtst.so.6":           ("libxtst6",            "libx/libxtst",  "libxtst6_1.2.4-1+deb12u1_amd64.deb"),
    "libthai.so.0":           ("libthai0",            "libt/libthai",  "libthai0_0.1.29-1_amd64.deb"),
    "libharfbuzz.so.0":       ("libharfbuzz0b",       "h/harfbuzz",    "libharfbuzz0b_6.0.0+dfsg-3_amd64.deb"),
    "libdatrie.so.1":         ("libdatrie1",          "libd/libdatrie","libdatrie1_0.2.13-2+b1_amd64.deb"),
    "libdrm.so.2":            ("libdrm2",             "libd/libdrm",   "libdrm2_2.4.114-1+b1_amd64.deb"),
    "libpango-1.0.so.0":      ("libpango-1.0-0",     "p/pango1.0",    "libpango-1.0-0_1.50.12+ds-1_amd64.deb"),
    "libpangocairo-1.0.so.0": ("libpango-1.0-0",     "p/pango1.0",    "libpango-1.0-0_1.50.12+ds-1_amd64.deb"),
    "libcairo.so.2":          ("libcairo2",           "c/cairo",       "libcairo2_1.16.0-7_amd64.deb"),
    "libpixman-1.so.0":       ("libpixman-1-0",       "p/pixman",      "libpixman-1-0_0.42.2-1_amd64.deb"),
    "libfontconfig.so.1":     ("libfontconfig1",      "f/fontconfig",  "libfontconfig1_2.14.1-4_amd64.deb"),
    "libfreetype.so.6":       ("libfreetype6",        "f/freetype",    "libfreetype6_2.12.1+dfsg-5+deb12u3_amd64.deb"),
    "libexpat.so.1":          ("libexpat1",           "e/expat",       "libexpat1_2.5.0-1+deb12u1_amd64.deb"),
    "libnss3.so":             ("libnss3",             "n/nss",         "libnss3_3.87.1-1+deb12u1_amd64.deb"),
    "libnspr4.so":            ("libnspr4",            "n/nspr",        "libnspr4_4.35-1_amd64.deb"),
    "libnssutil3.so":         ("libnss3",             "n/nss",         "libnss3_3.87.1-1+deb12u1_amd64.deb"),
    "libsmime3.so":           ("libnss3",             "n/nss",         "libnss3_3.87.1-1+deb12u1_amd64.deb"),
    "libssl3.so":             ("libnss3",             "n/nss",         "libnss3_3.87.1-1+deb12u1_amd64.deb"),
    "libatspi.so.0":          ("libatspi2.0-0",       "a/at-spi2-core","libatspi2.0-0_2.46.0-5_amd64.deb"),
}

FONT_PACKAGES = {
    "dejavu-core":  "fonts-dejavu-core_2.37-2_all.deb",
    "dejavu-extra": "fonts-dejavu-extra_2.37-2_all.deb",
}


def log(msg: str, level: str = "INFO") -> None:
    prefix = {"INFO": "  \u2022", "OK": "  \u2713", "ERR": "  \u2717", "WARN": "  \u26a0", "HDR": "\n\u2500\u2500", "SUB": "    \u21b3"}
    print(f"{prefix.get(level, '  ')} {msg}", flush=True)


def run(cmd, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def http_get(url: str, timeout: int = 15) -> tuple[int, bytes]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "headless-browser-setup/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()


def download_deb(url: str, dest: Path) -> bool:
    code, body = http_get(url)
    if code == 200 and len(body) > 1000:
        dest.write_bytes(body)
        return True
    return False


def detect_writable_root() -> Path:
    candidates = [Path("/fluso/user"), Path(os.path.expanduser("~")), Path("/tmp")]
    for p in candidates:
        try:
            test = p / ".writability_test"
            test.write_text("ok")
            test.unlink()
            log(f"Writable root: {p}", "OK")
            return p
        except (OSError, PermissionError):
            continue
    log("No writable root found!", "ERR")
    sys.exit(1)


def find_chromium_binary(playwright_browsers: Path) -> Path | None:
    shells = sorted(playwright_browsers.glob("chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"))
    if shells:
        return shells[-1]
    chromes = sorted(playwright_browsers.glob("chromium-*/chrome-linux64/chrome"))
    if chromes:
        log("No headless shell found; falling back to full chrome", "WARN")
        return chromes[-1]
    return None


def find_missing_libs(binary: Path) -> list[str]:
    result = run(["ldd", str(binary)])
    missing = []
    for line in result.stdout.splitlines():
        if "not found" in line:
            missing.append(line.strip().split()[0])
    return missing


def resolve_package_from_web(so_name: str) -> tuple[str, str] | None:
    search_url = f"{PACKAGES_BASE}/search?suite={DEBIAN_SUITE}&arch={DEBIAN_ARCH}&mode=path&searchon=contents&keywords={so_name}"
    code, body = http_get(search_url, timeout=20)
    if code != 200:
        return None
    text = body.decode("utf-8", errors="replace")
    pkg_match = re.search(r'href="/bookworm/amd64/([^/"]+)/download"', text)
    if not pkg_match:
        pkg_match = re.search(r'href="/bookworm/([^/"]+)"', text)
    if not pkg_match:
        return None
    pkg_name = pkg_match.group(1)
    dl_url = f"{PACKAGES_BASE}/bookworm/amd64/{pkg_name}/download"
    code2, body2 = http_get(dl_url, timeout=20)
    if code2 != 200:
        return None
    text2 = body2.decode("utf-8", errors="replace")
    dl_match = re.search(r'href="([^"]*\.deb)"', text2)
    if not dl_match:
        return None
    return pkg_name, dl_match.group(1)


def try_download_lib(so_name: str, libs_dir: Path, known_files: set) -> bool:
    if so_name in known_files:
        return True
    for root, dirs, files in os.walk(str(libs_dir)):
        if so_name in files:
            known_files.add(so_name)
            return True
    if so_name in KNOWN_LIBS:
        _pkg, pool, filename = KNOWN_LIBS[so_name]
        url = f"{DEBIAN_MIRROR}/pool/main/{pool}/{filename}"
        dest = Path(tempfile.gettempdir()) / filename
        if download_deb(url, dest):
            run(["dpkg-deb", "-x", str(dest), str(libs_dir)])
            dest.unlink(missing_ok=True)
            known_files.add(so_name)
            log(f"Downloaded and extracted {filename}", "SUB")
            return True
        log(f"Known mapping download failed for {filename}, trying web lookup", "WARN")
    log(f"Looking up package for {so_name}...", "SUB")
    result = resolve_package_from_web(so_name)
    if result is None:
        log(f"Could not resolve {so_name} via web lookup", "ERR")
        return False
    pkg_name, dl_url = result
    dl_url = dl_url.replace("http://", "https://")
    dest = Path(tempfile.gettempdir()) / f"{pkg_name}.deb"
    if download_deb(dl_url, dest):
        run(["dpkg-deb", "-x", str(dest), str(libs_dir)])
        dest.unlink(missing_ok=True)
        log(f"Extracted {pkg_name}", "OK")
        return True
    log(f"Download failed for {pkg_name}", "ERR")
    return False


def install_fonts(libs_dir: Path) -> bool:
    fonts_dir = libs_dir / "usr" / "share" / "fonts" / "truetype" / "dejavu"
    if fonts_dir.exists() and any(fonts_dir.glob("*.ttf")):
        log("Fonts already installed", "OK")
        return True
    for name, filename in FONT_PACKAGES.items():
        url = f"{DEBIAN_MIRROR}/pool/main/f/fonts-dejavu/{filename}"
        dest = Path(tempfile.gettempdir()) / filename
        log(f"Downloading {name} fonts...", "SUB")
        if download_deb(url, dest):
            run(["dpkg-deb", "-x", str(dest), str(libs_dir)])
            dest.unlink(missing_ok=True)
            log(f"Installed {name} fonts", "OK")
        else:
            log(f"Failed to download {name} fonts", "ERR")
            return False
    return True


def create_fontconfig(libs_dir: Path, fontconfig_dir: Path) -> bool:
    fonts_dir = libs_dir / "usr" / "share" / "fonts"
    fontconfig_dir.mkdir(parents=True, exist_ok=True)
    (fontconfig_dir / "cache").mkdir(exist_ok=True)
    conf = fontconfig_dir / "fonts.conf"
    conf.write_text(f"""<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>{fonts_dir}</dir>
  <cachedir>{fontconfig_dir}/cache</cachedir>
  <config><rescan><int>30</int></rescan></config>
  <match target="pattern">
    <test qual="any" name="family"><string>sans-serif</string></test>
    <edit name="family" mode="prepend" binding="same"><string>DejaVu Sans</string></edit>
  </match>
  <match target="pattern">
    <test qual="any" name="family"><string>serif</string></test>
    <edit name="family" mode="prepend" binding="same"><string>DejaVu Serif</string></edit>
  </match>
  <match target="pattern">
    <test qual="any" name="family"><string>monospace</string></test>
    <edit name="family" mode="prepend" binding="same"><string>DejaVu Sans Mono</string></edit>
  </match>
</fontconfig>
""")
    log(f"fontconfig written to {conf}", "OK")
    return True


def install_playwright_chromium(browsers_path: Path) -> bool:
    binary = find_chromium_binary(browsers_path)
    if binary:
        log(f"Chromium found at {binary}", "OK")
        return True
    log("Installing Playwright Chromium...", "INFO")
    result = run(["uv", "run", "--project", "/app/skills/webapp-testing", "playwright", "install", "chromium"],
                 env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": str(browsers_path)})
    if result.returncode != 0:
        log(f"Playwright install failed: {result.stderr}", "ERR")
        return False
    binary = find_chromium_binary(browsers_path)
    if binary:
        log(f"Chromium installed at {binary}", "OK")
        return True
    log("Chromium not found after install", "ERR")
    return False


def test_screenshot(binary: Path, libs_dir: Path, fontconfig_dir: Path, output_path: Path, test_url: str) -> bool:
    script = output_path.parent / "_screenshot_test.py"
    script.write_text(f"""from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path="{binary}", args=["--no-sandbox", "--disable-gpu"])
    page = browser.new_page(viewport={{"width": 1280, "height": 720}})
    page.goto("{test_url}", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)
    page.screenshot(path="{output_path}", full_page=True)
    browser.close()
    print("SCREENSHOT_OK")
""")
    ld_path = ":".join([str(libs_dir / "usr" / "lib" / "x86_64-linux-gnu"), str(libs_dir / "lib" / "x86_64-linux-gnu"), os.environ.get("LD_LIBRARY_PATH", "")])
    env = {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": str(binary.parent.parent.parent.parent), "LD_LIBRARY_PATH": ld_path, "FONTCONFIG_PATH": str(fontconfig_dir)}
    result = run(["uv", "run", "--project", "/app/skills/webapp-testing", "python", str(script)], env=env, timeout=60)
    script.unlink(missing_ok=True)
    success = "SCREENSHOT_OK" in result.stdout
    if success and output_path.exists():
        log(f"Test screenshot: {output_path} ({output_path.stat().st_size / 1024:.0f}KB)", "OK")
        return True
    else:
        log(f"Screenshot test failed: {result.stderr}", "ERR")
        return False


def main():
    parser = argparse.ArgumentParser(description="Bootstrap headless Chromium for Playwright")
    parser.add_argument("--writable-root", default=None)
    parser.add_argument("--test-url", default="https://example.com")
    parser.add_argument("--skip-test", action="store_true")
    parser.add_argument("--project-dir", default=None)
    args = parser.parse_args()

    log("Phase 1: Environment detection", "HDR")
    writable_root = Path(args.writable_root) if args.writable_root else detect_writable_root()
    project_dir = Path(args.project_dir) if args.project_dir else Path.cwd()
    libs_dir = project_dir / ".browser-libs"
    libs_dir.mkdir(parents=True, exist_ok=True)
    playwright_browsers = writable_root / ".cache" / "ms-playwright"
    fontconfig_dir = Path("/tmp/fontconfig")
    log(f"Project:     {project_dir}")
    log(f"Libs dir:    {libs_dir}")
    log(f"Browsers:    {playwright_browsers}")

    log("Phase 2: Playwright Chromium", "HDR")
    if not install_playwright_chromium(playwright_browsers):
        log("Cannot proceed without Chromium", "ERR")
        sys.exit(1)
    binary = find_chromium_binary(playwright_browsers)
    if not binary:
        log("Chromium binary not found", "ERR")
        sys.exit(1)

    log("Phase 3: Resolving shared libraries", "HDR")
    missing = find_missing_libs(binary)
    if not missing:
        log("All libraries resolved!", "OK")
    else:
        log(f"Found {len(missing)} missing libraries", "INFO")
        for so in missing:
            log(f"  Missing: {so}")
        failed = []
        known_files = set()
        for i, so in enumerate(missing):
            log(f"[{i+1}/{len(missing)}] Resolving {so}...", "INFO")
            if not try_download_lib(so, libs_dir, known_files):
                failed.append(so)
        if failed:
            log(f"Failed to resolve: {', '.join(failed)}", "ERR")
        else:
            log(f"All {len(missing)} libraries resolved!", "OK")

    log("Phase 4: Fonts", "HDR")
    install_fonts(libs_dir)
    create_fontconfig(libs_dir, fontconfig_dir)

    log("Phase 5: Environment file", "HDR")
    ld_path = ":".join([str(libs_dir / "usr" / "lib" / "x86_64-linux-gnu"), str(libs_dir / "lib" / "x86_64-linux-gnu")])
    env_file = libs_dir / "env.sh"
    env_file.write_text(f"""# Auto-generated by headless-browser-setup bootstrap.py
export PLAYWRIGHT_BROWSERS_PATH="{playwright_browsers}"
export LD_LIBRARY_PATH="{ld_path}${{LD_LIBRARY_PATH:+:}}$LD_LIBRARY_PATH"
export FONTCONFIG_PATH="{fontconfig_dir}"
""")
    log(f"Written: {env_file}", "OK")
    log("Source it: source .browser-libs/env.sh", "INFO")

    if not args.skip_test:
        log("Phase 6: Test screenshot", "HDR")
        files_dir = project_dir / "files"
        files_dir.mkdir(parents=True, exist_ok=True)
        output_path = files_dir / "bootstrap-test.png"
        if test_screenshot(binary, libs_dir, fontconfig_dir, output_path, args.test_url):
            log("Setup complete and verified!", "OK")
        else:
            log("Setup may be incomplete \u2014 test screenshot failed", "WARN")
    else:
        log("Skipping test screenshot (--skip-test)", "INFO")

    log("Summary", "HDR")
    log(f"Chromium:  {binary}")
    log(f"Libs dir:  {libs_dir}")
    log(f"Env file:  {env_file}")
    log(f"Fonts:     {fontconfig_dir}/fonts.conf")
    log("")
    log("To use in subsequent commands:", "INFO")
    log(f"  source {env_file}", "INFO")
    log(f"  uv run --project /app/skills/webapp-testing python your_script.py", "INFO")


if __name__ == "__main__":
    main()
