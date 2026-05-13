# Font Setup for Headless Chromium

Headless Chromium needs fonts to render text. Without fonts, all text appears as blank/invisible rectangles in screenshots. This guide covers installing DejaVu fonts (minimal, widely compatible) and configuring fontconfig to find them.

---

## Why Text Goes Missing

When Chromium can't find any fonts:
- Text elements still exist in the DOM
- Layout still happens (boxes, spacing, positions are correct)
- But glyphs can't be rasterized → transparent rectangles
- Webfonts won't help if the browser can't render the fallback system font

---

## Step 1: Download DejaVu Fonts

DejaVu is a minimal, free font family that covers Latin, Greek, Cyrillic, and many symbols. The core package is ~1MB.

```bash
curl -sL --connect-timeout 5 --max-time 15 \
    "https://mirrors.ocf.berkeley.edu/debian/pool/main/f/fonts-dejavu/fonts-dejavu-core_2.37-2_all.deb" \
    -o /tmp/fonts.deb
```

---

## Step 2: Extract to Custom Location

Extract into the same browser-libs directory used for system libraries:

```bash
LIBS_DIR=/fluso/user/workspace/projects/Home/.browser-libs
dpkg-deb -x /tmp/fonts.deb "$LIBS_DIR"
```

This places fonts at:
```
$LIBS_DIR/usr/share/fonts/truetype/dejavu/
├── DejaVuSans.ttf
├── DejaVuSans-Bold.ttf
├── DejaVuSerif.ttf
├── DejaVuSerif-Bold.ttf
├── DejaVuSansMono.ttf
└── DejaVuSansMono-Bold.ttf
```

---

## Step 3: Create fontconfig Configuration

fontconfig is the library Chromium uses to discover fonts. Create a minimal `fonts.conf`:

```bash
mkdir -p /tmp/fontconfig /tmp/fontconfig-cache

cat > /tmp/fontconfig/fonts.conf << 'XMLEOF'
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>/fluso/user/workspace/projects/Home/.browser-libs/usr/share/fonts</dir>
  <cachedir>/tmp/fontconfig-cache</cachedir>
  <config>
    <rescan><int>30</int></rescan>
  </config>

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
XMLEOF
```

The `FONTCONFIG_PATH` env var must point to the **directory containing fonts.conf**, not the file itself:

```bash
export FONTCONFIG_PATH=/tmp/fontconfig
```

---

## Step 4: Verify

```bash
ls /fluso/user/workspace/projects/Home/.browser-libs/usr/share/fonts/truetype/dejavu/
```

---

## Additional Font Options

### Noto Fonts (Broader Coverage)

If DejaVu doesn't cover the needed scripts (CJK, Arabic, etc.):

```bash
curl -sL "https://mirrors.ocf.berkeley.edu/debian/pool/main/f/fonts-noto/fonts-noto-core_20201225-1_all.deb" \
    -o /tmp/noto.deb
dpkg-deb -x /tmp/noto.deb /fluso/user/workspace/projects/Home/.browser-libs
```

### Liberation Fonts (Metric-Compatible)

Metric-compatible with Arial, Times New Roman, Courier New:

```bash
curl -sL "https://mirrors.ocf.berkeley.edu/debian/pool/main/f/fonts-liberation2/fonts-liberation2_2.1.5-1_all.deb" \
    -o /tmp/liberation.deb
dpkg-deb -x /tmp/liberation.deb /fluso/user/workspace/projects/Home/.browser-libs
```

---

## How fontconfig Discovery Works

1. Chromium links against `libfontconfig.so`
2. fontconfig reads `$FONTCONFIG_PATH/fonts.conf` (or system default if not set)
3. It scans all `<dir>` entries for font files
4. Caches results in `<cachedir>`
5. When Chromium needs to render text, it queries fontconfig for the best matching font

Without this configuration:
- Chromium looks in `/usr/share/fonts/`, `/usr/local/share/fonts/`, `~/.fonts/`
- If those don't exist (minimal container), no fonts are found
- All text renders invisible

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Text still missing after setup | Verify `FONTCONFIG_PATH` is set and points to directory with `fonts.conf` |
| fontconfig "No fonts found" | The `<dir>` path in fonts.conf must exactly match where fonts are extracted |
| Webfonts also missing | System font fallback must work first |
| Screenshot has boxes instead of text | Try a broader font like Noto |
| `libfontconfig.so` not found | Add the browser-libs dir to `LD_LIBRARY_PATH` |
