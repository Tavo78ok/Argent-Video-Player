import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

import json
import threading

from gi.repository import Adw, GLib, Gtk

import os
import subprocess
import shutil
import importlib.util


def ytdlp_cmd():
    if importlib.util.find_spec("yt_dlp"):
        return ["python3", "-m", "yt_dlp"]
    return [shutil.which("yt-dlp") or "yt-dlp"]

MEDIA_EXTS = (".mp4", ".mkv", ".webm", ".mov", ".avi", ".mp3", ".m4a",
              ".opus", ".flac", ".ogg", ".wav", ".aac", ".3gp", ".ts")


class OnlineItem:
    def __init__(self, title="", subtitle="", uri=None, webpage=None, raw=True,
                 label=None, variants=None):
        self.title = title
        self.subtitle = subtitle
        self.uri = uri
        self.webpage = webpage
        self.raw = raw
        self.label = label          # p. ej. "720p"
        self.variants = variants    # lista de OnlineItem (calidades alternativas)

    def display_uri(self):
        return self.webpage if self.raw else self.uri


def has_scheme(url):
    s = url.strip().lower()
    return s.startswith(("http://", "https://", "mms://", "rtsp://", "file://"))


def is_youtube(url):
    u = url.strip().lower()
    return ("youtube.com" in u or "youtu.be" in u) or u.startswith("ytsearch")


def looks_direct_media(url):
    path = url.split("?")[0].split("#")[0].lower()
    return any(path.endswith(x) for x in MEDIA_EXTS) or ".m3u8" in path or ".mpd" in path


def _run(cmd, timeout=45):
    p = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
        env={**os.environ, "LC_ALL": "C.UTF-8"},
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[-300:] or "sin respuesta de yt-dlp")
    return p.stdout


def _fsize(fmt):
    size = fmt.get("filesize") or fmt.get("filesize_approx") or 0
    if not size:
        return ""
    mb = size / 1048576
    return f" · ≈{mb:.0f} MB" if mb >= 1 else f" · ≈{mb * 1024:.0f} KB"


def _is_hls(fmt, proto):
    proto = (proto or "").lower()
    url = (fmt.get("url") or "").split("?")[0].lower()
    return ("m3u8" in proto or "hls" in proto
            or url.endswith(".m3u8") or "mpegurl" in url)


def _hls_cache_dir():
    d = os.path.join(GLib.get_user_cache_dir(), "argent-video")
    os.makedirs(d, exist_ok=True)
    return d


def _pin_master(audio_url, video_url, res=None):
    """Crea un manifest maestro local con la variante de video elegida y la
    pista de audio HLS aparte (EXT-X-MEDIA), porque los manifests por calidad
    de YouTube traen video sin audio."""
    import hashlib
    base = os.path.basename(video_url.split("?")[0])[:60]
    h = hashlib.sha1(f"{audio_url or ''}|{video_url}".encode()).hexdigest()[:16]
    path = os.path.join(_hls_cache_dir(), f"hls-{base[:24]}-{h}.m3u8")
    try:
        if not os.path.exists(path):
            stream_info = "#EXT-X-STREAM-INF:BANDWIDTH=9999999"
            if res:
                stream_info += f',RESOLUTION={res}'
            with open(path, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                if audio_url:
                    f.write('#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud",NAME="Audio",'
                            f'DEFAULT=YES,URI="{audio_url}"\n')
                    f.write(stream_info + ',AUDIO="aud"\n')
                else:
                    f.write(stream_info + "\n")
                f.write(video_url + "\n")
    except OSError:
        return video_url
    return "file://" + path


def variants_from_info(info):
    """Arma la lista de calidades reproducibles por playbin.

    Formatos muxed (mp4/webm con audio embebido) y variantes HLS por
    resolución; para HLS se genera un manifest maestro local uniendo
    la pista de video elegida con la pista de audio HLS separada, ya
    que YouTube entrega el video por calidad sin audio."""
    fmts = info.get("formats") or []
    muxed_by_h, hls_by_h = {}, {}
    audio_hls = None
    for f in fmts:
        v = f.get("vcodec")
        a = f.get("acodec")
        h = f.get("height") or 0
        proto = (f.get("protocol") or "").lower()
        url = f.get("url") or ""
        if not url:
            continue
        muxed = v not in (None, "none") and a not in (None, "none")
        is_hls = ("m3u8" in proto or "hls" in proto
                  or url.split("?")[0].lower().endswith(".m3u8"))
        if muxed:
            slot = muxed_by_h.setdefault(h, f)
            if (f.get("tbr") or 0) > (slot.get("tbr") or 0):
                muxed_by_h[h] = f
        elif is_hls and h > 0 and v not in (None, "none"):
            slot = hls_by_h.setdefault(h, f)
            if (f.get("tbr") or 0) > (slot.get("tbr") or 0):
                hls_by_h[h] = f
        elif is_hls and h == 0 and v in (None, "none"):
            # manifest HLS de audio puro (el acodec suele venir ausente);
            # se usa como pista de audio al fijar cada calidad
            if audio_hls is None:
                audio_hls = url
    if not muxed_by_h and not hls_by_h:
        # radio/videos solo-audio o directos sin video: una sola entrada
        if audio_hls:
            return [OnlineItem(
                title=info.get("title") or "En línea",
                subtitle="solo audio · HLS",
                uri=audio_hls,
                webpage=info.get("webpage_url"),
                raw=False,
                label="audio",
            )]
        return None

    title = info.get("title") or "En línea"
    page = info.get("webpage_url")

    def _entry(label, f, kind):
        return OnlineItem(
            title=title,
            subtitle=f"{label} · {kind}{_fsize(f)}",
            uri=f.get("url"),
            webpage=page,
            raw=False,
            label=label,
        )

    out = []
    for h in sorted(muxed_by_h):
        f = muxed_by_h[h]
        kind = f.get("ext") or "muxed"
        out.append(_entry(f"{h}p" if h else "auto", f, kind))
    if hls_by_h:
        heights = sorted(hls_by_h, reverse=True)
        for idx, h in enumerate(heights):
            f = hls_by_h[h]
            w = f.get("width")
            res = f"{w}x{h}" if w else None
            kind = "HLS (video+audio)" if audio_hls else "HLS (sin audio)"
            if not audio_hls and not muxed_by_h and len(heights) == 1:
                # la variante es lo único que hay y quedaría muda: sin sentido
                continue
            uri = _pin_master(audio_hls, f.get("url"), res)
            label = "auto" if idx == 0 and len(heights) > 1 else f"{h}p"
            out.append(OnlineItem(
                title=title,
                subtitle=f"{label} · {kind}",
                uri=uri,
                webpage=page,
                raw=False,
                label=label,
            ))

    def _order_key(it):
        lbl = it.label or ""
        h = int(lbl[:-1]) if lbl.endswith("p") else (0 if lbl == "auto" else -1)
        return (0 if (h == 0 or lbl == "auto") else 1, -h if h and h != 0 else 0)

    out.sort(key=_order_key)
    return out


def pick_url(info):
    fmts = info.get("formats") or []
    cands = []
    for f in fmts:
        v = f.get("vcodec")
        a = f.get("acodec")
        h = f.get("height") or 0
        proto = f.get("protocol") or ""
        muxed = v not in (None, "none") and a not in (None, "none")
        if muxed:
            cands.append((h, f.get("url")))
        elif "m3u8" in proto or "hls" in proto:
            cands.append((h, f.get("url")))
        elif v not in (None, "none") and info.get("webpage", "").startswith(("https://", "http://")):
            cands.append((h // 2, f.get("url")))
    cands = [(h, u) for h, u in cands if u]
    if cands:
        cands.sort(key=lambda x: x[0])
        return cands[-1][1]
    return info.get("url")


def search_youtube(query, limit=14):
    out = _run(ytdlp_cmd() + ["--no-warnings", "--flat-playlist", "-J",
                              f"ytsearch{limit}:{query}"])
    data = json.loads(out)
    items = []
    for e in data.get("entries", []):
        eid = e.get("id")
        if not eid and not e.get("url"):
            continue
        page = e.get("url") if e.get("url") else f"https://www.youtube.com/watch?v={eid}"
        if not page:
            page = f"https://www.youtube.com/watch?v={eid}"
        dur = e.get("duration")
        dur_s = f"{int(dur) // 60}:{int(dur) % 60:02d} " if isinstance(dur, (int, float)) and dur > 0 else ""
        items.append(OnlineItem(
            title=e.get("title") or "Desconocido",
            subtitle=f"{e.get('uploader') or ''} · {dur_s}YouTube".strip(),
            webpage=page,
        ))
    if not items:
        raise RuntimeError("sin resultados")
    return items


def probe_page(url):
    try:
        out = _run(ytdlp_cmd() + ["--no-warnings", "--no-playlist", "-j", url],
                   timeout=60)
    except RuntimeError as e:
        if "youtube" in url.lower():
            out = _run(ytdlp_cmd() + ["--no-warnings", "--no-playlist", "-j",
                                      "--extractor-args",
                                      "youtube:player_client=android", url],
                       timeout=60)
        else:
            raise
    info = json.loads(out)
    return item_from_info(info)


def item_from_info(info):
    variants = variants_from_info(info)
    uri = variants[0].uri if variants else pick_url(info)
    if not uri:
        raise RuntimeError("no se encontró una pista reproducible")
    dur = info.get("duration")
    extra = ""
    if info.get("channel") or info.get("uploader"):
        extra += f"{info.get('channel') or info.get('uploader')}"
    if isinstance(dur, (int, float)) and dur > 0:
        extra += f" · {int(dur) // 3600}:{(int(dur) % 3600) // 60:02d}:{int(dur) % 60:02d}"
    item = OnlineItem(
        title=info.get("title") or "En línea",
        subtitle=extra.strip(" ·"),
        uri=uri,
        webpage=info.get("webpage_url"),
        raw=False,
    )
    if variants:
        item.label = variants[0].label
        if len(variants) > 1:
            item.variants = variants
    return item


def resolve(item):
    if not item.raw:
        return item
    return probe_page(item.webpage)


def resolve_url(url):
    if looks_direct_media(url):
        name = url.split("?")[0].split("#")[0].split("://", 1)[-1]
        return OnlineItem(
            title=os.path.basename(name) or url,
            subtitle="Directo",
            uri=url,
            raw=False,
        )
    return probe_page(url)


def _row_for(item):
    row = Gtk.ListBoxRow(activatable=True, selectable=False)
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                  margin_top=6, margin_bottom=6, margin_start=12, margin_end=12)
    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    title = Gtk.Label(label=item.title, xalign=0, ellipsize=3, hexpand=True)
    title.add_css_class("body")
    sub = Gtk.Label(label=item.subtitle or " ", xalign=0, ellipsize=3, hexpand=True)
    sub.add_css_class("dim-label")
    sub.set_wrap(True)
    vbox.append(title)
    vbox.append(sub)
    img = Gtk.Image.new_from_icon_name("media-playback-start-symbolic")
    box.append(vbox)
    box.append(img)
    row.set_child(box)
    row.online_item = item
    return row


class OnlineDialog(Adw.Dialog):
    def __init__(self, win):
        super().__init__(title="En línea", content_width=580, content_height=680)
        self.win = win
        self._busy = False
        self._mode = "search"       # "search" | "quality"
        self._results_items = []    # filas de la última búsqueda
        self._current = None        # item resuelto en curso (para variantes)

        self.entry = Gtk.SearchEntry()
        self.entry.set_placeholder_text(
            "Buscar en YouTube o pegar URL (mp4, m3u8, YouTube, radio/TV…)")
        self.entry.connect("activate", self._on_go)

        self.status = Gtk.Label(xalign=0, wrap=True)
        self.status.add_css_class("dim-label")
        self.status.set_opacity(0.0)

        self.spin = Gtk.Spinner()
        self.spin.set_tooltip_text("Resolviendo en línea…")

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.connect("row-activated", self._on_row)
        self.listbox.add_css_class("boxed-list")

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(self.listbox)
        scroll.set_vexpand(True)

        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                        margin_top=6, margin_bottom=12, margin_start=12, margin_end=12)
        inner.append(self.entry)
        inner.append(self.status)
        inner.append(scroll)

        page = Adw.ToolbarView()
        header = Adw.HeaderBar()
        self.back_btn = Gtk.Button(icon_name="go-previous-symbolic",
                                   tooltip_text="Volver a los resultados")
        self.back_btn.connect("clicked", self._on_back)
        self.back_btn.set_visible(False)
        header.pack_start(self.back_btn)
        header.pack_end(self.spin)
        page.add_top_bar(header)
        page.set_content(inner)
        self.set_child(page)

    def present(self, parent=None):
        super().present(parent)

    def _clear_rows(self):
        while self.listbox.get_first_child():
            self.listbox.remove(self.listbox.get_first_child())

    def _on_go(self, entry):
        q = entry.get_text().strip()
        if not q or self._busy:
            return
        self._mode = "search"
        self.back_btn.set_visible(False)
        self._set_status("", 0.0)
        self._clear_rows()
        self._busy = True
        self.spin.start()
        self.entry.set_sensitive(False)
        t = threading.Thread(target=self._worker, args=(q,), daemon=True)
        t.start()

    def _worker(self, q):
        ok, data, err = False, None, ""
        try:
            low = q.lower()
            if low.startswith("ytsearch"):
                data = search_youtube(q.split(":", 1)[-1])
            elif not has_scheme(q):
                data = search_youtube(q)
            elif is_youtube(q):
                data = [probe_page(q)]
            elif looks_direct_media(q):
                data = [resolve_url(q)]
            else:
                data = [resolve_url(q)]
            ok = True
        except Exception as e:
            err = str(e)
        GLib.idle_add(self._done, q, ok, data, err)

    def _done(self, q, ok, data, err):
        self._busy = False
        self.spin.stop()
        self.entry.set_sensitive(True)
        if not ok:
            self._set_status(f"Error: {err}", 1.0)
            return False
        self._results_items = list(data)
        self._show_results()
        self.entry.grab_focus()
        return False

    def _show_results(self):
        self._clear_rows()
        for it in self._results_items:
            self.listbox.append(_row_for(it))
        self._set_status("", 0.0)

    def _show_quality(self, final):
        self._mode = "quality"
        self._current = final
        self._clear_rows()
        variants = final.variants or [final]
        for it in variants:
            row = _row_for(it)
            if it.uri == final.uri:
                img = Gtk.Image.new_from_icon_name("object-select-symbolic")
                img.set_valign(Gtk.Align.CENTER)
                img.add_css_class("accent")
                box = row.get_child()
                box.append(img)
            self.listbox.append(row)
        title = (final.title or "video")[:44]
        self._set_status(f"Elegí la calidad para «{title}»", 1.0)
        self.back_btn.set_visible(True)

    def _on_back(self, btn):
        if self._busy or self._mode != "quality":
            return
        self._mode = "search"
        self._current = None
        self.back_btn.set_visible(False)
        self._show_results()

    def _on_row(self, box, row):
        item = row.online_item
        if self._mode == "quality":
            if self._current is not None:
                item.variants = self._current.variants
            self.win.play_online(item, keep_variants=True)
            self.force_close()
            return
        self.spin.start()
        self._set_status("Resolviendo…", 1.0)
        self.entry.set_sensitive(False)
        t = threading.Thread(target=self._play_worker, args=(item,), daemon=True)
        t.start()

    def _play_worker(self, item):
        ok, final, err = False, None, ""
        try:
            final = resolve(item)
            ok = True
        except Exception as e:
            err = str(e)
        GLib.idle_add(self._play_done, final, ok, err)

    def _play_done(self, final, ok, err):
        self._busy = False
        self.spin.stop()
        self.entry.set_sensitive(True)
        if not ok:
            self._set_status(f"Error: {err}", 1.0)
            return False
        if final is not None and getattr(final, "variants", None):
            self._show_quality(final)
        else:
            self.win.play_online(final)
            self.force_close()
        return False

    def _set_status(self, text, opacity):
        self.status.set_text(text)
        self.status.set_opacity(opacity)
