# Dependency Resolution for Headless Browsers

How to get Chromium running in a minimal Debian container when `apt-get install` fails.

---

## Strategy: Manual .deb Extraction

When the system package manager is non-functional (read-only apt lists, no network access to repos):

1. Identify missing libraries with `ldd`
2. Find the correct Debian package name and version
3. Download the `.deb` from an HTTPS mirror
4. Extract to a custom library directory
5. Point `LD_LIBRARY_PATH` at that directory

---

## Step 1: Identify What's Missing

```bash
ldd /path/to/chrome-or-headless-shell 2>&1 | grep "not found"
```

Example output:
```
libglib-2.0.so.0 => not found
libatk-1.0.so.0 => not found
libatk-bridge-2.0.so.0 => not found
```

---

## Step 2: Find the Right Debian Package

For each missing `.so`, find which package provides it on Debian Bookworm:

```bash
curl -sL "https://packages.debian.org/bookworm/amd64/<libname>/download" | \
    grep -oP 'href="[^"]*\.deb"' | head -3
```

Example for `libglib2.0-0`:
```bash
curl -sL "https://packages.debian.org/bookworm/amd64/libglib2.0-0/download" | grep -oP 'href="[^"]*\.deb"'
# href="http://ftp.us.debian.org/debian/pool/main/g/glib2.0/libglib2.0-0_2.74.6-2+deb12u5_amd64.deb"
```

The URL tells you:
- **Pool path:** `pool/main/g/glib2.0/`
- **Exact version:** `2.74.6-2+deb12u5`
- **Architecture:** `amd64`

**Important:** packages.debian.org returns HTTP URLs. Convert to HTTPS:
`http://ftp.us.debian.org/debian/...` → `https://mirrors.ocf.berkeley.edu/debian/...`

---

## Step 3: Download and Extract

```bash
LIBS_DIR=/fluso/user/workspace/projects/Home/.browser-libs
MIRROR="https://mirrors.ocf.berkeley.edu/debian"

curl -sL --connect-timeout 5 --max-time 15 \
    "$MIRROR/pool/main/g/glib2.0/libglib2.0-0_2.74.6-2+deb12u5_amd64.deb" \
    -o /tmp/pkg.deb -w "HTTP %{http_code}"

ls -la /tmp/pkg.deb  # real .deb files are >10KB; 404 pages are <1KB

dpkg-deb -x /tmp/pkg.deb "$LIBS_DIR"
```

---

## Complete Library List for Chromium Headless Shell

All libraries typically missing on Debian Bookworm minimal containers:

| Library | Package | Pool Path |
|---------|---------|-----------|
| libglib-2.0.so.0 | libglib2.0-0 | g/glib2.0 |
| libatk-1.0.so.0 | libatk1.0-0 | a/at-spi2-core |
| libatk-bridge-2.0.so.0 | libatk-bridge2.0-0 | a/at-spi2-core |
| libdbus-1.so.3 | libdbus-1-3 | d/dbus |
| libcups.so.2 | libcups2 | c/cups |
| libXext.so.6 | libxext6 | libx/libxext |
| libXrandr.so.2 | libxrandr2 | libx/libxrandr |
| libgbm.so.1 | libgbm1 | m/mesa |
| libasound.so.2 | libasound2 | a/alsa-lib |
| libXi.so.6 | libxi6 | libx/libxi |
| libthai.so.0 | libthai0 | libt/libthai |
| libharfbuzz.so.0 | libharfbuzz0b | h/harfbuzz |
| libdatrie.so.1 | libdatrie1 | libd/libdatrie |
| libdrm.so.2 | libdrm2 | libd/libdrm |
| libX11.so.6 | libx11-6 | libx/libx11 |
| libXcomposite.so.1 | libxcomposite1 | libx/libxcomposite |
| libXdamage.so.1 | libxdamage1 | libx/libxdamage |
| libXfixes.so.3 | libxfixes3 | libx/libxfixes |
| libxcb.so.1 | libxcb1 | libx/libxcb |
| libxkbcommon.so.0 | libxkbcommon0 | libx/libxkbcommon |
| libnss3.so | libnss3 | n/nss |
| libnspr4.so | libnspr4 | n/nspr |
| libatspi.so.0 | libatspi2.0-0 | a/at-spi2-core |
| libpango-1.0.so.0 | libpango-1.0-0 | p/pango1.0 |
| libcairo.so.2 | libcairo2 | c/cairo |
| libfontconfig.so.1 | libfontconfig1 | f/fontconfig |
| libfreetype.so.6 | libfreetype6 | f/freetype |

For exact filenames, see the `KNOWN_LIBS` dict in `scripts/bootstrap.py`.

---

## Batch Download Script

```bash
LIBS_DIR=/fluso/user/workspace/projects/Home/.browser-libs
MIRROR="https://mirrors.ocf.berkeley.edu/debian"
mkdir -p /tmp/debs

declare -A PKGS
PKGS=(
    ["libglib2.0-0"]="g/glib2.0/libglib2.0-0_2.74.6-2+deb12u5_amd64.deb"
    ["libatk1.0-0"]="a/at-spi2-core/libatk1.0-0_2.46.0-5_amd64.deb"
    ["libatk-bridge2.0-0"]="a/at-spi2-core/libatk-bridge2.0-0_2.46.0-5_amd64.deb"
    ["libdbus-1-3"]="d/dbus/libdbus-1-3_1.14.10-1~deb12u1_amd64.deb"
    ["libxext6"]="libx/libxext/libxext6_1.3.4-1+b1_amd64.deb"
    ["libxrandr2"]="libx/libxrandr/libxrandr2_1.5.2-2+b1_amd64.deb"
    ["libgbm1"]="m/mesa/libgbm1_22.3.6-1+deb12u1_amd64.deb"
    ["libasound2"]="a/alsa-lib/libasound2_1.2.8-1+b1_amd64.deb"
    ["libxi6"]="libx/libxi/libxi6_1.8-1+b1_amd64.deb"
    ["libthai0"]="libt/libthai/libthai0_0.1.29-1_amd64.deb"
    ["libharfbuzz0b"]="h/harfbuzz/libharfbuzz0b_6.0.0+dfsg-3_amd64.deb"
    ["libdatrie1"]="libd/libdatrie/libdatrie1_0.2.13-2+b1_amd64.deb"
    ["libdrm2"]="libd/libdrm/libdrm2_2.4.114-1+b1_amd64.deb"
    ["libcups2"]="c/cups/libcups2_2.4.2-3+deb12u9_amd64.deb"
    ["libx11-6"]="libx/libx11/libx11-6_1.8.4-2+deb12u2_amd64.deb"
    ["libnss3"]="n/nss/libnss3_3.87.1-1+deb12u1_amd64.deb"
)

for lib in "${!PKGS[@]}"; do
    pkg_path="${PKGS[$lib]}"
    url="$MIRROR/pool/main/$pkg_path"
    out="/tmp/debs/${lib}.deb"
    
    code=$(curl -sL --connect-timeout 5 --max-time 15 -o "$out" -w "%{http_code}" "$url")
    size=$(stat -c%s "$out" 2>/dev/null || echo 0)
    
    if [ "$code" = "200" ] && [ "$size" -gt 1000 ]; then
        dpkg-deb -x "$out" "$LIBS_DIR"
        echo "  OK $lib installed"
    else
        echo "  FAIL $lib (HTTP $code, size $size)"
        rm -f "$out"
    fi
done

# Verify
LD_LIBRARY_PATH=$LIBS_DIR/usr/lib/x86_64-linux-gnu:$LIBS_DIR/lib/x86_64-linux-gnu \
    ldd /path/to/chromium | grep "not found"
```

---

## Notes

- **Version numbers change** with Debian point releases. Always verify by checking packages.debian.org first.
- **Package names may differ** from library names: `libcups.so.2` → package `libcups2`.
- **Pool paths** group related packages: `libatk1.0-0` and `libatk-bridge2.0-0` are both in `a/at-spi2-core/`.
- **If a download fails**, try alternate mirrors: `mirrors.kernel.org` (may use HTTP only).
- **LD_LIBRARY_PATH order matters**: Put the custom lib dir first so it takes precedence over any system libs.
