#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
VERSION="$(python3 -c "import re; print(re.search(r'__version__ = \"(.+)\"', open('$ROOT/src/soundpad_linux/__init__.py').read()).group(1))")"
BUILD="$ROOT/build/appimage"
APPDIR="$BUILD/Soundpad_Linux-x86_64"
OUT="$ROOT/dist/Soundpad_Linux-$VERSION-x86_64.AppImage"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"

if ! python3 -c "import python_appimage" 2>/dev/null; then
    python3 -m pip install --user python-appimage
fi

rm -rf "$BUILD"
mkdir -p "$BUILD/recipe" "$BUILD/wheel" "$ROOT/dist"

python3 -m pip wheel --no-deps -w "$BUILD/wheel" "$ROOT"
cp "$ROOT/packaging/appimage/"* "$BUILD/recipe/"
cp "$ROOT/data/soundpad_linux.png" "$BUILD/recipe/"
ls "$BUILD"/wheel/*.whl > "$BUILD/recipe/requirements.txt"

ARGS=(-p "$PYTHON_VERSION" --no-packaging)
if [ -n "${BASE_IMAGE:-}" ]; then
    ARGS+=(-b "$BASE_IMAGE")
fi
(cd "$BUILD" && python3 -m python_appimage build app "${ARGS[@]}" recipe)

SITE="$(echo "$APPDIR"/opt/python*/lib/python*/site-packages)"
PYSIDE="$SITE/PySide6"
QT="$PYSIDE/Qt"

rm -rf "$SITE"/pip "$SITE"/pip-*.dist-info
rm -rf "$QT/qml" "$QT/metatypes" "$QT/translations" "$QT/libexec"
rm -rf "$PYSIDE/include" "$PYSIDE/typesystems" "$PYSIDE/scripts" "$PYSIDE/glue" "$PYSIDE/doc"
rm -rf "$QT/plugins/designer" "$QT/plugins/qmltooling" "$QT/plugins/sqldrivers" \
       "$QT/plugins/wayland-graphics-integration-server" "$QT/plugins/egldeviceintegrations" \
       "$QT/plugins/printsupport" "$QT/plugins/vectorimageformats"
rm -f "$QT/plugins/platforms/"libqeglfs* "$QT/plugins/platforms/"libqlinuxfb* \
      "$QT/plugins/platforms/"libqvnc* "$QT/plugins/platforms/"libqvkkhrdisplay*
find "$PYSIDE" -maxdepth 1 -type f \( -name "*.pyi" -o \( -perm -u+x ! -name "*.so*" \) \) -delete
for mod in Designer Help Labs Lottie Qml Quick Sql Test UiTools WaylandCompositor WaylandEgl \
           EglFS EglFs PrintSupport Concurrent; do
    rm -f "$QT/lib/libQt6$mod"*
done
for mod in QtDesigner QtHelp QtLabsStyleKit QtQml QtQmlFeatures QtQuick QtQuickControls2 QtQuickTest \
           QtQuickWidgets QtSql QtTest QtUiTools QtPrintSupport QtConcurrent QtOpenGLWidgets QtXml QtSvgWidgets; do
    rm -f "$PYSIDE/$mod".*
done
rm -f "$PYSIDE"/libpyside6qml*
find "$APPDIR" -name "__pycache__" -type d -prune -exec rm -rf {} +

ln -sfn soundpad_linux.png "$APPDIR/.DirIcon"
for wrapper in "$APPDIR"/usr/bin/python*; do
    if [ -f "$wrapper" ] && head -c 2 "$wrapper" | grep -q '#!'; then
        sed -i 's|^"\$APPDIR/opt/python|exec "$APPDIR/opt/python|' "$wrapper"
    fi
done

if [ -n "${NO_PACKAGING:-}" ]; then
    echo "AppDir left in $APPDIR"
    exit 0
fi

TOOL="${APPIMAGETOOL:-$BUILD/appimagetool}"
if [ ! -x "$TOOL" ]; then
    curl -fsSL -o "$TOOL" "$APPIMAGETOOL_URL"
    chmod +x "$TOOL"
fi

ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" "$OUT"
chmod +x "$OUT"
echo "Built $OUT"
