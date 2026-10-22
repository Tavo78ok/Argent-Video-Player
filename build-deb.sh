#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  Argent Video v1.0 — GTK4/libadwaita — build-deb.sh
#  Uso: chmod +x build-deb.sh && ./build-deb.sh
# ═══════════════════════════════════════════════════════════
set -e

PKG="argent-video"
VERSION="1.1"
ARCH="all"
DEB="${PKG}_${VERSION}_${ARCH}.deb"
DIR="deb_build/${PKG}_${VERSION}_${ARCH}"
BIN="argent-video"
LIB="usr/lib/argent-video"
PKGDIR="argent_video"
SRC="src/argent_video"
ICO="data/icons/scalable/apps/argent-video.svg"

G='\033[0;32m'; C='\033[0;36m'; Y='\033[1;33m'; R='\033[0;31m'; N='\033[0m'

echo -e "\n${C}╔══════════════════════════════════════════╗"
echo -e "║  Argent Video v${VERSION} — GTK4 .deb       ║"
echo -e "╚══════════════════════════════════════════╝${N}\n"

[ ! -f "${SRC}/main.py" ] && echo -e "${R}✗ $SRC no encontrado en el directorio actual${N}" && exit 1

echo -e "${Y}▶ Herramientas...${N}"
MISS=()
command -v dpkg-deb &>/dev/null || MISS+=("dpkg-dev")
command -v rsvg-convert &>/dev/null || { command -v convert &>/dev/null || MISS+=("librsvg2-bin"); }
[ ${#MISS[@]} -gt 0 ] && sudo apt-get install -y "${MISS[@]}" -q
echo -e "${G}  ✓${N}"

echo -e "${Y}▶ Estructura...${N}"
rm -rf deb_build
mkdir -p "${DIR}/DEBIAN" "${DIR}/usr/bin" "${DIR}/${LIB}/${PKG}"
mkdir -p "${DIR}/usr/share/applications"
mkdir -p "${DIR}/usr/share/icons/hicolor/scalable/apps"
mkdir -p "${DIR}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${DIR}/usr/share/icons/hicolor/128x128/apps"
mkdir -p "${DIR}/usr/share/icons/hicolor/48x48/apps"
echo -e "${G}  ✓${N}"

echo -e "${Y}▶ Copiando código...${N}"
cp -r "${SRC}/." "${DIR}/${LIB}/${PKGDIR}/"
rm -rf "${DIR}/${LIB}/${PKGDIR}/__pycache__"
find "${DIR}/${LIB}" -type d -exec chmod 755 {} +
find "${DIR}/${LIB}" -type f -exec chmod 644 {} +
echo -e "${G}  ✓${N}"

if [ -f "$ICO" ]; then
    cp "$ICO" "${DIR}/usr/share/icons/hicolor/scalable/apps/argent-video.svg"
    if command -v rsvg-convert &>/dev/null; then
        rsvg-convert -w 256 -h 256 "$ICO" -o "${DIR}/usr/share/icons/hicolor/256x256/apps/argent-video.png"
        rsvg-convert -w 128 -h 128 "$ICO" -o "${DIR}/usr/share/icons/hicolor/128x128/apps/argent-video.png"
        rsvg-convert -w 48  -h 48  "$ICO" -o "${DIR}/usr/share/icons/hicolor/48x48/apps/argent-video.png"
    elif python3 render-icons.py "$ICO" . &>/dev/null; then
        mv "argent-video-256.png" "${DIR}/usr/share/icons/hicolor/256x256/apps/argent-video.png"
        mv "argent-video-128.png" "${DIR}/usr/share/icons/hicolor/128x128/apps/argent-video.png"
        mv "argent-video-48.png"  "${DIR}/usr/share/icons/hicolor/48x48/apps/argent-video.png"
    else
        convert -background none "$ICO" -resize 256x256 "${DIR}/usr/share/icons/hicolor/256x256/apps/argent-video.png"
        convert -background none "$ICO" -resize 128x128 "${DIR}/usr/share/icons/hicolor/128x128/apps/argent-video.png"
        convert -background none "$ICO" -resize 48x48   "${DIR}/usr/share/icons/hicolor/48x48/apps/argent-video.png"
    fi
    echo -e "${G}  ✓ Íconos${N}"
fi

cat > "${DIR}/usr/bin/${BIN}" << EOF
#!/bin/bash
export PYTHONPATH="/${LIB}:\${PYTHONPATH}"
exec python3 -m ${PKGDIR} "\$@"
EOF
chmod 755 "${DIR}/usr/bin/${BIN}"
echo -e "${G}  ✓ Launcher${N}"

cat > "${DIR}/usr/share/applications/argent-video.desktop" << DESKTOP
[Desktop Entry]
Version=1.1
Type=Application
Name=Argent Video
GenericName=Reproductor de Video
Comment=Reproductor moderno GTK4/libadwaita con YouTube y streams en línea
Exec=${BIN} %U
Icon=argent-video
Terminal=false
Categories=AudioVideo;Video;GTK;
Keywords=video;player;reproductor;youtube;stream;hls;m3u8;musica;streaming;
StartupNotify=true
StartupWMClass=os.argentos.ArgentVideo
DESKTOP

cat > "${DIR}/DEBIAN/control" << CONTROL
Package: ${PKG}
Version: ${VERSION}
Section: video
Priority: optional
Architecture: ${ARCH}
Depends: python3 (>= 3.11), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, python3-gst-1.0, gstreamer1.0-gtk4, gstreamer1.0-plugins-good, gstreamer1.0-plugins-bad, gstreamer1.0-libav
Recommends: yt-dlp, gstreamer1.0-plugins-ugly, gstreamer1.0-gl
Maintainer: Tavo (Tavo78ok) <tavo78ok@github.com>
Homepage: https://github.com/Tavo78ok
Description: Argent Video v${VERSION} - Reproductor moderno GTK4/libadwaita
 Reproductor de video para Debian con interfaz libadwaita.
 Reproduce archivos locales, URLs directas, HLS/DASH (m3u8/mpd)
 y contenido de YouTube en línea usando yt-dlp.
 Incluye historial, favoritos, pantalla completa y atajos de teclado.
CONTROL

cat > "${DIR}/DEBIAN/postinst" << 'POSTINST'
#!/bin/bash
set -e
G='\033[0;32m'; C='\033[0;36m'; Y='\033[1;33m'; N='\033[0m'
echo -e "\n${C}╔══════════════════════════════════════════╗"
echo -e "║   Argent Video v1.0                      ║"
echo -e "║   GTK4 + libadwaita                      ║"
echo -e "╚══════════════════════════════════════════╝${N}\n"
apt_q() { DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$@" 2>/dev/null; }

for pkg in python3-gst-1.0 gstreamer1.0-gtk4 gstreamer1.0-plugins-good \
           gstreamer1.0-plugins-bad gstreamer1.0-libav gstreamer1.0-plugins-ugly \
           gstreamer1.0-gl yt-dlp; do
    if [ "$pkg" = "yt-dlp" ]; then
        command -v yt-dlp &>/dev/null || apt_q yt-dlp || true
    else
        dpkg -l "$pkg" 2>/dev/null | grep -q '^ii' || apt_q "$pkg" || true
    fi
done

ok_ok() { python3 - << 'PYCHK'
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
raise SystemExit(0 if Gst.ElementFactory.find('gtk4paintablesink') else 1)
PYCHK
}

if ok_ok; then
    echo -e "${G}▶ Backend de video: ✓ (gtk4paintablesink activo)${N}"
else
    echo -e "${Y}▶ Instalando backend de video gstreamer gtk4...${N}"
    apt_q python3-gst-1.0 gstreamer1.0-gtk4 \
        && echo -e "${G}  ✓ listo${N}" \
        || echo -e "${Y}  ⚠ ejecutar: sudo apt install python3-gst-1.0 gstreamer1.0-gtk4${N}"
fi

chmod +x /usr/bin/argent-video
gtk-update-icon-cache -f /usr/share/icons/hicolor/ 2>/dev/null || true
update-desktop-database /usr/share/applications/ 2>/dev/null || true
chmod +x /usr/bin/argent-video

echo -e "\n${G}╔══════════════════════════════════════════╗"
echo -e "║  ✅ Argent Video v1.0 instalado          ║"
echo -e "║  Terminal:  argent-video                  ║"
echo -e "║  Menú:      buscar Argent Video          ║"
echo -e "╚══════════════════════════════════════════╝${N}\n"
exit 0
POSTINST
chmod 755 "${DIR}/DEBIAN/postinst"

printf '#!/bin/bash\nupdate-desktop-database /usr/share/applications/ 2>/dev/null || true\nexit 0\n' \
    > "${DIR}/DEBIAN/prerm"
chmod 755 "${DIR}/DEBIAN/prerm"

echo -e "${Y}▶ Construyendo ${DEB}...${N}"
dpkg-deb --build --root-owner-group "${DIR}" "${DEB}"

SZ=$(du -h "${DEB}" | cut -f1)
echo -e "\n${G}╔══════════════════════════════════════════════════╗"
echo -e "║  ✅ ${DEB} (${SZ}) listo"
echo -e "╚══════════════════════════════════════════════════╝${N}\n"
echo "  Instalar:     sudo dpkg -i ${DEB} && sudo apt -f install"
echo "  Ejecutar:     argent-video"
echo "  Limpiar:      rm -rf deb_build"
