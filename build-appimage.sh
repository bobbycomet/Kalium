#!/usr/bin/env bash
# =============================================================================
# Kalium AppImage builder
# Author: Bobby Comet  |  MIT  |  Inspired by archived NaK (SulfurNitride)
#
# Usage:
#   ./build-appimage.sh              # build from this repo tree
#   ./build-appimage.sh /path/to/out  # optional output directory
#
# Requirements (host):
#   - Linux x86_64
#   - python3 >= 3.10, pip, venv
#   - curl/wget, tar, file
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${1:-$SCRIPT_DIR/dist}"
APP_NAME="Kalium"
APP_ID="com.bobbycomet.kalium"
VERSION="${KALIUM_VERSION:-1.2.1}"
ARCH="x86_64"
BUILD="$SCRIPT_DIR/.appimage-build"
APPDIR="$BUILD/${APP_NAME}.AppDir"

echo "==> Kalium AppImage builder v${VERSION}"
echo "    Source: $SCRIPT_DIR"
echo "    Output: $OUT_DIR"

download() {
  local url="$1" dest="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL -o "$dest" "$url"
  else
    wget -q -O "$dest" "$url"
  fi
}

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: required command not found: $1" >&2
    exit 1
  }
}

need python3
need tar
need file

PYTHON_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "    Python: $PYTHON_VER"

# ---------------------------------------------------------------------------
# Clean / prepare
# ---------------------------------------------------------------------------
rm -rf "$BUILD"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib" "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps" "$OUT_DIR"

# ---------------------------------------------------------------------------
# Bundle Python venv + Kalium into AppDir
# ---------------------------------------------------------------------------
echo "==> Creating portable virtualenv in AppDir..."
python3 -m venv "$APPDIR/usr/venv"
# shellcheck disable=SC1091
source "$APPDIR/usr/venv/bin/activate"

pip install --upgrade pip wheel setuptools >/dev/null
pip install -r "$SCRIPT_DIR/requirements.txt"
pip install "$SCRIPT_DIR"

deactivate || true

mkdir -p "$APPDIR/usr/share/kalium"
cp -a "$SCRIPT_DIR/kalium" "$APPDIR/usr/share/kalium/"
cp -a "$SCRIPT_DIR/pyproject.toml" "$SCRIPT_DIR/requirements.txt" "$SCRIPT_DIR/LICENSE" \
      "$SCRIPT_DIR/README.md" "$APPDIR/usr/share/kalium/" 2>/dev/null || true

# ---------------------------------------------------------------------------
# AppRun
# ---------------------------------------------------------------------------
echo "==> Writing AppRun..."
cat > "$APPDIR/AppRun" << 'APPRUN'
#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

export VIRTUAL_ENV="$HERE/usr/venv"
export PATH="$VIRTUAL_ENV/bin:$PATH"
export PYTHONPATH="$HERE/usr/share/kalium:${PYTHONPATH:-}"

PY_SITE="$("$VIRTUAL_ENV/bin/python" -c 'import site; print(site.getsitepackages()[0])' 2>/dev/null || true)"
if [ -n "${PY_SITE:-}" ]; then
  export QT_PLUGIN_PATH="${PY_SITE}/PyQt6/Qt6/plugins:${QT_PLUGIN_PATH:-}"
  export QT_QPA_PLATFORM_PLUGIN_PATH="${PY_SITE}/PyQt6/Qt6/plugins/platforms:${QT_QPA_PLATFORM_PLUGIN_PATH:-}"
  export LD_LIBRARY_PATH="${PY_SITE}/PyQt6/Qt6/lib:${LD_LIBRARY_PATH:-}"
fi

exec "$VIRTUAL_ENV/bin/python" -m kalium.main "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

# ---------------------------------------------------------------------------
# Desktop entry
# ---------------------------------------------------------------------------
cat > "$APPDIR/${APP_NAME}.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Kalium
GenericName=Linux Modding Helper
Comment=Steam-native MO2 setup for Linux (by Bobby Comet)
Exec=AppRun %F
Icon=kalium
Categories=Game;Utility;
Terminal=false
StartupNotify=true
X-AppImage-Version=${VERSION}
EOF

cp "$APPDIR/${APP_NAME}.desktop" "$APPDIR/usr/share/applications/${APP_ID}.desktop"

# ---------------------------------------------------------------------------
# Icons — use bundled Kalium art
echo "==> Writing icons..."
ICON_SRC=""
for candidate in \
  "$SCRIPT_DIR/kalium/resources/icons/kalium.png" \
  "$SCRIPT_DIR/kalium.png" \
  "$SCRIPT_DIR/resources/icons/kalium.png"
do
  if [ -f "$candidate" ]; then
    ICON_SRC="$candidate"
    break
  fi
done

if [ -n "$ICON_SRC" ]; then
  cp "$ICON_SRC" "$APPDIR/kalium.png"
  mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
  mkdir -p "$APPDIR/usr/share/icons/hicolor/512x512/apps"
  mkdir -p "$APPDIR/usr/share/icons/hicolor/128x128/apps"
  cp "$ICON_SRC" "$APPDIR/usr/share/icons/hicolor/256x256/apps/kalium.png"
  cp "$ICON_SRC" "$APPDIR/usr/share/icons/hicolor/512x512/apps/kalium.png"
  cp "$ICON_SRC" "$APPDIR/usr/share/icons/hicolor/128x128/apps/kalium.png"
  # Also ship inside the Python package path for the running app
  mkdir -p "$APPDIR/usr/share/kalium/kalium/resources/icons"
  cp "$ICON_SRC" "$APPDIR/usr/share/kalium/kalium/resources/icons/kalium.png"
  echo "    Icon: $ICON_SRC"
else
  echo "WARNING: kalium.png not found — generating placeholder"
  python3 - "$APPDIR" << 'ICONPY'
import struct, zlib, sys
from pathlib import Path
appdir = Path(sys.argv[1])
w = h = 64
pixel = bytes([0x64, 0x96, 0xFF, 0xFF])
raw = b"".join(b"\x00" + pixel * w for _ in range(h))
compressed = zlib.compress(raw, 9)
def chunk(tag, data):
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
png = (b"\x89PNG\r\n\x1a\n"
    + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    + chunk(b"IDAT", compressed)
    + chunk(b"IEND", b""))
(appdir / "kalium.png").write_bytes(png)
(appdir / "usr/share/icons/hicolor/256x256/apps").mkdir(parents=True, exist_ok=True)
(appdir / "usr/share/icons/hicolor/256x256/apps/kalium.png").write_bytes(png)
print("placeholder icon written")
ICONPY
fi

ln -sfn kalium.png "$APPDIR/.DirIcon"

# Download appimagetool
# ---------------------------------------------------------------------------
echo "==> Fetching appimagetool..."
TOOL_DIR="$BUILD/tools"
mkdir -p "$TOOL_DIR"
APPIMAGETOOL="$TOOL_DIR/appimagetool-${ARCH}.AppImage"
if [ ! -x "$APPIMAGETOOL" ]; then
  download \
    "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage" \
    "$APPIMAGETOOL" || download \
    "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${ARCH}.AppImage" \
    "$APPIMAGETOOL"
  chmod +x "$APPIMAGETOOL"
fi

# ---------------------------------------------------------------------------
# Build AppImage
# ---------------------------------------------------------------------------
echo "==> Building AppImage..."
export ARCH
export VERSION

run_appimagetool() {
  local err
  err="$(mktemp)"
  if "$APPIMAGETOOL" "$@" 2>"$err"; then
    rm -f "$err"
    return 0
  fi
  if grep -qiE 'fuse|fusermount|permission|AppImages require' "$err" 2>/dev/null; then
    echo "    FUSE not available — extracting appimagetool..."
    (
      cd "$TOOL_DIR"
      rm -rf squashfs-root
      # Type-2 AppImages support this without FUSE when APPIMAGE_EXTRACT_AND_RUN is set
      APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" --appimage-extract >/dev/null 2>&1 || true
    )
    if [ -x "$TOOL_DIR/squashfs-root/AppRun" ]; then
      "$TOOL_DIR/squashfs-root/AppRun" "$@"
      local rc=$?
      rm -f "$err"
      return $rc
    fi
    echo "    Trying APPIMAGE_EXTRACT_AND_RUN=1 on pack step..."
    APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" "$@"
    local rc=$?
    rm -f "$err"
    return $rc
  fi
  cat "$err" >&2
  rm -f "$err"
  return 1
}

OUT_NAME="${APP_NAME}-${VERSION}-${ARCH}.AppImage"
OUT_PATH="$OUT_DIR/$OUT_NAME"

(
  cd "$BUILD"
  run_appimagetool "$APPDIR" "$OUT_PATH"
)

if [ ! -f "$OUT_PATH" ]; then
  alt="$BUILD/$OUT_NAME"
  if [ -f "$alt" ]; then
    mv "$alt" "$OUT_PATH"
  else
    # search nearby
    found="$(find "$BUILD" "$OUT_DIR" -maxdepth 2 -name '*.AppImage' -type f 2>/dev/null | head -n 1 || true)"
    if [ -n "$found" ]; then
      mv "$found" "$OUT_PATH"
    else
      echo "ERROR: AppImage not produced" >&2
      echo "AppDir listing:" >&2
      ls -la "$APPDIR" >&2 || true
      ls -la "$BUILD" >&2 || true
      exit 1
    fi
  fi
fi

chmod +x "$OUT_PATH"
echo ""
echo "==> Done."
echo "    AppImage: $OUT_PATH"
echo "    Size:     $(du -h "$OUT_PATH" | cut -f1)"
echo ""
echo "Run with:"
echo "    $OUT_PATH"
echo "CLI example:"
echo "    $OUT_PATH list-protons"
