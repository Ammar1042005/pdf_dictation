#!/usr/bin/env bash
# Produces a Debian package and a portable tarball.
set -euo pipefail
cd "$(dirname "$0")/.."
VER=$(python -c "import pdf_dictation as p; print(p.__version__)")
pyinstaller --noconfirm packaging/pdfdictation.spec
P=build/deb/pdf-dictation_${VER}_amd64
rm -rf build/deb; mkdir -p "$P/DEBIAN" "$P/opt/pdfdictation" "$P/usr/bin" "$P/usr/share/applications"
cp -r dist/PDFDictation/* "$P/opt/pdfdictation/"
ln -s /opt/pdfdictation/PDFDictation "$P/usr/bin/pdfdictation"
cp packaging/pdfdictation.desktop "$P/usr/share/applications/"
cat > "$P/DEBIAN/control" <<CTL
Package: pdf-dictation
Version: $VER
Architecture: amd64
Maintainer: ${PDFDICTATION_MAINTAINER:?Set PDFDICTATION_MAINTAINER before building}
Depends: espeak-ng, libegl1, libxkbcommon0, libxcb-cursor0
Description: Controlled PDF dictation for copying textbooks by hand
CTL
dpkg-deb --build --root-owner-group "$P" dist/
tar czf "dist/PDFDictation-${VER}-linux-x86_64.tar.gz" -C dist PDFDictation
