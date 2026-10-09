#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

VER=$(python -c "import pdf_dictation as p; print(p.__version__)")
pyinstaller --noconfirm packaging/pdfdictation.spec
APPDIR="build/PDFDictation.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/scalable/apps"
cp -r dist/PDFDictation/* "$APPDIR/usr/bin/"
cp packaging/pdfdictation.desktop "$APPDIR/usr/share/applications/"
cp pdf_dictation/assets/pdf_dictation.svg "$APPDIR/usr/share/icons/hicolor/scalable/apps/pdf-dictation.svg"
cp packaging/pdf_dictation.desktop "$APPDIR/pdf-dictation.desktop"
sed -i 's#^Exec=.*#Exec=PDFDictation#' "$APPDIR/pdf-dictation.desktop"
cp pdf_dictation/assets/pdf_dictation.svg "$APPDIR/pdf-dictation.svg"
cat > "$APPDIR/AppRun" <<'RUN'
#!/usr/bin/env sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/PDFDictation" "$@"
RUN
chmod +x "$APPDIR/AppRun"

if ! command -v appimagetool >/dev/null 2>&1; then
    echo "AppImage staging directory created at $APPDIR."
    echo "Install appimagetool, then run: appimagetool $APPDIR dist/PDFDictation-${VER}-x86_64.AppImage"
    exit 0
fi
appimagetool "$APPDIR" "dist/PDFDictation-${VER}-x86_64.AppImage"
