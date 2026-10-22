<div align="center">

<img src="data/icons/hicolor/256x256/apps/argent-video.png" alt="Argent Video" width="128" height="128"/>

# ▶ Argent Video

**Reproductor de video moderno para OpenArgentOS / Debian 13**

GTK4 + libadwaita · GStreamer · Contenido en línea (YouTube, HLS, radio/TV) · Ligero y acelerado

[![Debian 13 trixie](https://img.shields.io/badge/Debian-13%20trixie-A81D33)](https://www.debian.org/releases/trixie/)
[![GTK4 + libadwaita](https://img.shields.io/badge/GTK4-libadwaita-4A90D9)](https://gnome.pages.gitlab.gnome.org/libadwaita/)
[![GStreamer](https://img.shields.io/badge/GStreamer-1.0-57B756)](https://gstreamer.freedesktop.org/)
[![Python + PyGObject](https://img.shields.io/badge/Python-PyGObject-3776AB)](https://pygobject.readthedocs.io/)
[![Paquete .deb](https://img.shields.io/badge/Instalar-.deb-FDB824)](#-instalar-como-paquete-deb)

</div>

---

## 🚀 Características

| | |
|---|---|
| 🎬 **Interfaz nativa GTK4** | libadwaita, integrada al estilo de OpenArgentOS |
| ⚡ **Video acelerado** | Pipeline GStreamer con `gtk4paintablesink`: renderiza dentro de la ventana vía `Gtk.Picture`, sin XEmbed ni ventanas X embebidas |
| 🌐 **Contenido en línea** | Búsqueda en YouTube, URLs de YouTube/`youtu.be`, HLS (`m3u8`), DASH (`mpd`), `mp4`/`webm` directo, radio y TV en vivo |
| 🎚️ **Selección de calidad** | Elige la resolución al reproducir contenido online (auto, 1080p, 720p…) y cambia de calidad desde la cabecera conservando la posición |
| 🔎 **Resolución con yt-dlp** | Elige automáticamente la mejor pista combinada (avc+aac) o stream HLS que `playbin` reproduce sin transcodificar |
| 🖱️ **No te interrumpe** | Inhibe el salvapantallas y la suspensión mientras reproduce (D-Bus `org.freedesktop.ScreenSaver`), al pausar se libera |
| 📁 **Archivos locales** | Diálogo de archivos o arrastrar y soltar sobre la ventana |
| ⭐ **Favoritos e historial** | Persistencia en JSON (`~/.local/share/argent-video/library.json`) |
| 🫥 **Controles flotantes** | Auto-ocultado durante la reproducción, banner de estado y búfer, pantalla completa con doble clic o `F` |
| ⌨️ **Atajos completos** | Play/pausa, ±10 s, volumen, silencio, pantalla completa |

## 📷 Capturas

| Inicio | Reproduciendo |
|---|---|
| ![Pantalla de inicio](docs/screenshot-inicio.png) | ![Reproduciendo](docs/screenshot-reproduciendo.png) |

> 📌 Las imágenes van en `docs/`: guardá tus capturas con los nombres
> `screenshot-inicio.png` y `<img width="1440" height="900" alt="screenshot-inicio" src="https://github.com/user-attachments/assets/e2e91ed0-abcd-49af-a2d2-97d05a58b448" /><img width="1440" height="900" alt="screenshot-reproduciendo" src="https://github.com/user-attachments/assets/9e05bf0a-855c-47d3-a18c-bcc7879b9080" />
.png`.

## 📦 Instalar como paquete .deb

```bash
git clone https://github.com/Tavo78ok/argent-video
cd argent-video
./build-deb.sh
sudo dpkg -i argent-video_*_all.deb && sudo apt -f install
```

Después buscá **Argent Video** en el menú, o desde la terminal:

```bash
argent-video                        # abre sin archivo
argent-video /ruta/al/video.mp4     # abre un archivo local
argent-video https://youtu.be/…     # abre una URL en línea
```

## ▷ Ejecutar sin instalar

```bash
git clone https://github.com/Tavo78ok/argent-video
cd argent-video
./argent-video
```

## ⚙️ Dependencias (Debian 13)

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 \
    python3-gst-1.0 gstreamer1.0-gtk4 \
    gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
    gstreamer1.0-libav yt-dlp
# Opcionales (códecs extra y mejor render GL):
sudo apt install gstreamer1.0-plugins-ugly gstreamer1.0-gl
# Para empaquetar el .deb desde la fuente:
sudo apt install dpkg-dev librsvg2-bin python3-cairo
```

## 🌐 Contenido en línea

Pulsá el botón **En línea** (🔍) y:

- **Buscá en YouTube** — 14 resultados por consulta (`yt-dlp --flat-playlist`)
- **Pegá una URL** — YouTube/`youtu.be` (resuelve la entrada, no la playlist completa), HLS, DASH o radio/TV en vivo
- **Apretá una fila** — se resuelve en segundo plano con `yt-dlp`, en modo usuario y sin cookies
- **Elegí la calidad** — si hay variantes (auto/1080p/720p/480p…) aparece la lista de calidades; más tarde podés cambiarla desde el botón de calidad de la cabecera, que retoma la reproducción donde estaba

También acepta una URL como argumento al abrir la app (`./argent-video <url>`)
o pegada en el botón **Abrir archivo** de la barra: la detecta y la maneja igual.

## ⌨️ Atajos de teclado

| Tecla | Acción |
|-----------------|------------------------------------------|
| <kbd>Espacio</kbd> | Reproducir / Pausar |
| <kbd>←</kbd> / <kbd>→</kbd> | Retroceder / avanzar 10 s |
| <kbd>↑</kbd> / <kbd>↓</kbd> | Subir / bajar volumen (5 %) |
| <kbd>M</kbd> | Silencio |
| <kbd>F</kbd> / <kbd>F11</kbd> | Pantalla completa |
| <kbd>Esc</kbd> | Salir de pantalla completa / cerrar |

## 🗂️ Estructura del proyecto

```
argent-video
├── argent-video                 # launcher sin instalar (PYTHONPATH local)
├── build-deb.sh                 # empaquetado .deb, estilo Argent Apps
├── render-icons.py              # SVG → PNG usando librsvg vía ctypes
├── src/argent_video/
│   ├── main.py                  # Adw.Application + HANDLES_OPEN
│   ├── window.py                # ventana, controles, drag&drop, pantalla completa
│   ├── player.py                # playbin + gtk4paintablesink + señales GObject
│   ├── online.py                # yt-dlp búsqueda / resolución + OnlineDialog
│   └── library.py               # favoritos + historial + LibraryDialog
├── data/
│   ├── argent-video.desktop     # entrada de menú
│   └── icons/…                  # SVG scalable + PNG 48/128/256
└── README.md
```

## 🧠 Notas técnicas

- **Un solo pipeline reutilizable**: cada reproducción reconfigura el `playbin`
  existente y, si no hay, crea uno nuevo con un sink GTK4 fresco (el sink
  entrega un `GdkPaintable` que se asigna al `Gtk.Picture`).
- **Elección de pista**: se ordenan los formatos por altura y se prioriza
  *muxed* (video+audio en una sola URL mp4/webm) o HLS que `playbin` maneja
  nativo; los formatos DASH *video-only* quedan de reserva.
- **Búfering**: bajo el 100 % el pipeline se autopausa y el banner muestra el
  porcentaje; al completar retoma solo.
- **Íconos**: `render-icons.py` rasteriza el SVG con `librsvg` (aun sin
  `rsvg-convert` o ImageMagick con delegados correctos), mismo estilo
  Argent Apps (48/128/256 + SVG scalable).
- Si falta el sink (`gstreamer1.0-gtk4`), al arrancar aparece un banner con el
  comando de instalación; `yt-dlp` es opcional y los streams directos siguen
  funcionando sin él.

## 🧩 Parte de la colección Argent Apps

<p align="center">
  🎵 <a href="https://github.com/Tavo78ok/argent-music-player">Argent Music Player</a> &nbsp;·&nbsp;
  🎬 <a href="https://github.com/Tavo78ok/argent-video">Argent Video</a> &nbsp;·&nbsp;
  Otras apps de la familia OpenArgentOS
</p>

<sub>Ajustá los enlaces a los nombres reales de tus repos.</sub>

> Hecho a mano para **OpenArgentOS**, desde Santa Fe de la Vera Cruz, Argentina 🇦🇷

---

<div align="center">

⭐ Si te sirve, dejá una estrella en el repo.

</div>
