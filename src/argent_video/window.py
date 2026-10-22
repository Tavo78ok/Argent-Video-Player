import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GLib, Gio, Gtk

from .library import LibraryDialog, Library
from .online import OnlineDialog, resolve_url
from .player import Player


def fmt_time(sec):
    sec = int(sec or 0)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class VideoWindow(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application, title="Argent Video")
        self.set_default_size(1000, 640)
        self.set_title("Argent Video")

        self.lib = Library()
        self.player = Player()
        self._dragging = False
        self._hide_id = 0
        self._current_title = ""
        self._current_uri = ""
        self._variants = []
        self._q_label = ""

        self.build_ui()
        self.bind_player()

    def build_ui(self):
        self.picture = Gtk.Picture()
        self.picture.set_hexpand(True)
        self.picture.set_vexpand(True)
        self.picture.set_can_focus(True)

        self.status = Adw.StatusPage(
            icon_name="folder-videos-symbolic",
            title="Argent Video",
            description="Arrastra un archivo aquí, abre uno local o pulsa En línea para YouTube y streams.",
        )

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.add_named(self.status, "empty")
        self.stack.add_named(self.picture, "video")
        self.stack.set_visible_child_name("empty")

        self.banner = Adw.Banner()
        self.banner.set_button_label("Cerrar")
        self.banner.connect("button-clicked", lambda b: b.set_revealed(False))

        self.build_header()
        self.build_controls()

        overlay = Gtk.Overlay()
        overlay.set_child(self.stack)
        overlay.add_overlay(self.controls)

        view = Adw.ToolbarView()
        view.set_content(overlay)
        view.add_top_bar(self.banner)
        view.add_top_bar(self.header)

        self.set_content(view)

        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.connect("drop", self._on_drop)
        self.add_controller(drop)

        click = Gtk.GestureClick()
        click.set_button(1)
        click.connect("pressed", self._on_pressed_video)
        self.picture.add_controller(click)

        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        self.add_controller(motion)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)

        self.lib_dialog = None
        self.online_dialog = None

    def build_header(self):
        self.header = Adw.HeaderBar()

        open_btn = Gtk.Button(icon_name="document-open-symbolic",
                              tooltip_text="Abrir archivo local")
        open_btn.connect("clicked", self._on_open)
        self.header.pack_start(open_btn)

        online_btn = Gtk.Button(icon_name="system-search-symbolic",
                                tooltip_text="Contenido en línea")
        online_btn.connect("clicked", self._on_online)
        self.header.pack_start(online_btn)

        self.q_btn = Gtk.MenuButton()
        self.q_lbl = Gtk.Label(label="Calidad")
        self.q_lbl.add_css_class("caption")
        self.q_btn.set_child(self.q_lbl)
        self.q_btn.set_tooltip_text("Calidad del video en línea")
        self.q_list = Gtk.ListBox()
        self.q_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.q_list.add_css_class("boxed-list")
        self.q_list.connect("row-activated", self._on_quality_row)
        q_scroll = Gtk.ScrolledWindow()
        q_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        q_scroll.set_child(self.q_list)
        q_scroll.set_max_content_height(420)
        self.q_pop = Gtk.Popover()
        self.q_pop.set_child(q_scroll)
        self.q_btn.set_popover(self.q_pop)
        self.q_btn.connect("notify::active", self._on_q_btn_toggle)
        self.q_btn.set_visible(False)

        self.fav_btn = Gtk.Button(icon_name="non-starred-symbolic",
                                  tooltip_text="Añadir/Quitar de favoritos")
        self.fav_btn.connect("clicked", self._on_fav)
        self.fav_btn.set_sensitive(False)
        self.header.pack_end(self.fav_btn)

        lib_btn = Gtk.Button(icon_name="document-open-recent-symbolic",
                             tooltip_text="Historial y favoritos")
        lib_btn.connect("clicked", self._on_library)
        self.header.pack_end(lib_btn)

        fs_btn = Gtk.Button(icon_name="view-fullscreen-symbolic",
                            tooltip_text="Pantalla completa (F)")
        fs_btn.connect("clicked", lambda b: self._toggle_fullscreen())
        self.header.pack_end(fs_btn)

        self.header.pack_end(self.q_btn)

        if not self.player.available:
            self.banner.set_title(
                "Falta el sink de video: sudo apt install python3-gst-1.0 gstreamer1.0-gtk4")
            self.banner.set_revealed(True)

    def build_controls(self):
        self.controls = Gtk.Revealer()
        self.controls.set_transition_type(Gtk.RevealerTransitionType.CROSSFADE)
        self.controls.set_valign(Gtk.Align.END)
        self.controls.set_halign(Gtk.Align.CENTER)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.add_css_class("osd")
        box.add_css_class("toolbar")
        box.add_css_class("player-controls")
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        self.btn_play = Gtk.Button(icon_name="media-playback-start-symbolic",
                                   tooltip_text="Reproducir/Pausa (Espacio)")
        self.btn_play.connect("clicked", lambda b: self.player.toggle())
        self.btn_play.set_sensitive(bool(self.player.available))
        box.append(self.btn_play)

        back_btn = Gtk.Button(icon_name="media-seek-backward-symbolic",
                              tooltip_text="Atrás 10s (←)")
        back_btn.connect("clicked", lambda b: self.player.seek_by(-10))
        back_btn.set_sensitive(bool(self.player.available))
        box.append(back_btn)

        fwd_btn = Gtk.Button(icon_name="media-seek-forward-symbolic",
                             tooltip_text="Adelante 10s (→)")
        fwd_btn.connect("clicked", lambda b: self.player.seek_by(10))
        fwd_btn.set_sensitive(bool(self.player.available))
        box.append(fwd_btn)

        self.lbl_pos = Gtk.Label(label="0:00", xalign=0.5)
        self.lbl_pos.add_css_class("monospace")
        box.append(self.lbl_pos)

        self.seek = Gtk.Scale()
        self.seek.set_hexpand(True)
        self.seek.set_size_request(240, -1)
        self.seek.set_draw_value(False)
        self.seek.set_range(0, 1)
        self.seek.add_css_class("seek-scale")
        self.seek.set_sensitive(bool(self.player.available))
        seek_click = Gtk.GestureClick()
        seek_click.connect("pressed", self._on_seek_press)
        seek_click.connect("released", self._on_seek_release)
        self.seek.add_controller(seek_click)
        box.append(self.seek)

        self.lbl_dur = Gtk.Label(label="0:00")
        self.lbl_dur.add_css_class("monospace")
        box.append(self.lbl_dur)

        self.volume = Gtk.VolumeButton()
        self.volume.set_valign(Gtk.Align.CENTER)
        self.volume.set_value(1.0)
        self.volume.connect("value-changed", self._on_volume)
        self.volume.set_sensitive(bool(self.player.available))
        box.append(self.volume)

        fs_btn = Gtk.Button(icon_name="view-restore-symbolic",
                            tooltip_text="Salir de pantalla completa (Esc)")
        fs_btn.connect("clicked", lambda b: self._toggle_fullscreen())
        fs_btn.set_visible(False)
        self.fs_btn = fs_btn
        box.append(fs_btn)

        self.controls.set_child(box)
        self._wake_controls()

    def bind_player(self):
        self.player.connect("state-changed", self._on_state)
        self.player.connect("position-changed", self._on_position_tick)
        self.player.connect("buffering", self._on_buffering)
        self.player.connect("error", self._on_error)
        self.player.connect("ended", self._on_ended)

    # ---------- acciones de uso ----------
    def play_uri(self, uri, title="", variants=None, label=None):
        if not self.player.available:
            self.banner.set_title(
                "Falta el sink de video: sudo apt install python3-gst-1.0 gstreamer1.0-gtk4")
            self.banner.set_revealed(True)
            return False
        self.player.open(uri)
        if self.player.paintable:
            self.picture.set_paintable(self.player.paintable)
        self.player.play()
        self.stack.set_visible_child_name("video")
        self._current_uri = uri
        self._current_title = title or uri
        self._variants = list(variants) if variants else []
        self._q_label = label or ""
        self._update_q_button()
        self.fav_btn.set_sensitive(True)
        self._update_fav_icon()
        self.banner.set_revealed(False)
        self.lib.add_history(uri, self._current_title)
        return True

    def play_online(self, item, keep_variants=False):
        variants = item.variants
        label = item.label or ""
        if keep_variants and not variants:
            variants = self._variants or None
        self.play_uri(item.uri, item.title or self._current_title,
                      variants=variants, label=label)

    def _update_q_button(self):
        show = bool(self._variants) and self.player.available
        self.q_btn.set_visible(show)
        self.q_lbl.set_text(self._q_label or "Calidad")

    def _on_q_btn_toggle(self, btn, pspec):
        if btn.get_active():
            self._rebuild_q_menu()

    def _rebuild_q_menu(self):
        while self.q_list.get_first_child():
            self.q_list.remove(self.q_list.get_first_child())
        for it in self._variants:
            row = Gtk.ListBoxRow(activatable=True, selectable=False)
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10,
                          margin_top=4, margin_bottom=4, margin_start=12, margin_end=12)
            lbl = Gtk.Label(label=it.label or "?", xalign=0, hexpand=True)
            lbl.add_css_class("body")
            chk = Gtk.Image.new_from_icon_name("object-select-symbolic")
            chk.set_visible(it.uri == self._current_uri)
            chk.set_valign(Gtk.Align.CENTER)
            box.append(lbl)
            box.append(chk)
            row.set_child(box)
            row.online_item = it
            self.q_list.append(row)

    def _on_quality_row(self, box, row):
        item = row.online_item
        self.q_pop.popdown()
        self._switch_quality(item)

    def _switch_quality(self, item):
        if not item or item.uri == self._current_uri:
            return
        pos = self.player.position()
        self.player.open(item.uri)
        if self.player.paintable:
            self.picture.set_paintable(self.player.paintable)
        self.player.play()
        if pos > 3.0:
            self._resume_seek(pos + 1.5)
        self._current_uri = item.uri
        self._q_label = item.label or self._q_label
        self._update_q_button()
        self.banner.set_revealed(False)
        self._wake_controls()

    def _resume_seek(self, seconds):
        def try_seek():
            if self.player.is_playing() or self.player.is_paused():
                self.player.seek(seconds)
                return False
            return True
        GLib.timeout_add(700, try_seek)

    def play_open_arg(self, file):
        uri = file.get_uri()
        scheme = (file.get_uri_scheme() or "").lower()
        path = file.get_path()
        if scheme not in ("file", "resource", "trash") and path is None:
            self.banner.set_title("Resolviendo URL en línea…")
            self.banner.set_revealed(True)
            t = threading.Thread(target=self._open_arg_thread,
                                 args=(uri, file.get_basename()), daemon=True)
            t.start()
        else:
            self.play_uri(uri, file.get_basename())

    def _open_arg_thread(self, uri, base):
        ok, item, err = False, None, ""
        try:
            item = resolve_url(uri)
            ok = True
        except Exception as e:
            err = str(e)
        GLib.idle_add(self._open_arg_done, item, ok, err)

    def _open_arg_done(self, item, ok, err):
        if not ok:
            self.banner.set_title(f"Error al abrir URL: {err}")
            self.banner.set_revealed(True)
            return False
        self.play_uri(item.uri, item.title)
        return False

    def _on_open(self, btn):
        dlg = Gtk.FileDialog()
        filters = Gtk.FileFilter()
        filters.set_name("Video y audio")
        for pat in ("*.mp4", "*.mkv", "*.webm", "*.mov", "*.avi", "*.mp3",
                    "*.m4a", "*.opus", "*.flac", "*.ogg", "*.wav", "*.m3u8",
                    "*.ts", "*.3gp"):
            filters.add_pattern(pat)
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(filters)
        dlg.set_filters(store)
        dlg.open(self, None, self._on_open_done)

    def _on_open_done(self, dlg, result):
        try:
            fobj = dlg.open_finish(result)
        except Exception:
            return
        if fobj is None:
            return
        name = fobj.get_basename()
        self.play_uri(fobj.get_uri(), name)

    def _on_online(self, btn):
        if self.online_dialog is None:
            self.online_dialog = OnlineDialog(self)
        self.online_dialog.present(self)

    def _on_library(self, btn):
        if self.lib_dialog is not None:
            self.lib_dialog.force_close()
        self.lib_dialog = LibraryDialog(self)
        self.lib_dialog.present(self)

    def _on_fav(self, btn):
        if not self._current_uri:
            return
        self.lib.toggle_fav(self._current_uri, self._current_title)
        self._update_fav_icon()

    def _update_fav_icon(self):
        fav = self.lib.is_fav(self._current_uri)
        self.fav_btn.set_icon_name("starred-symbolic" if fav else "non-starred-symbolic")

    def _on_drop(self, target, value, x, y):
        files = value.get_files()
        if not files:
            return False
        fobj = files[0]
        return self.play_uri(fobj.get_uri(), fobj.get_basename())

    # ---------- reproducción / UI ----------
    def _on_state(self, player, state_int):
        from gi.repository import Gst
        state = Gst.State(state_int)
        self.set_title(self._current_title or "Argent Video")
        if state == Gst.State.PLAYING:
            self.btn_play.set_icon_name("media-playback-pause-symbolic")
        else:
            self.btn_play.set_icon_name("media-playback-start-symbolic")
        self._wake_controls()

    def _on_position_tick(self, player, pos, dur):
        adj = self.seek.get_adjustment()
        if not self._dragging:
            upper = max(dur, 0.001)
            adj.set_upper(upper)
            adj.set_step_increment(5)
            self.seek.set_value(pos)
        self.lbl_pos.set_text(fmt_time(pos))
        self.lbl_dur.set_text(fmt_time(dur))

    def _on_buffering(self, player, percent):
        if percent < 100:
            self.banner.set_title(f"Almacenando en búfer… {percent}%")
            self.banner.set_revealed(True)
        else:
            self.banner.set_revealed(False)

    def _on_error(self, player, message):
        self.banner.set_title(f"Error de reproducción: {message}")
        self.banner.set_revealed(True)
        self.stack.set_visible_child_name("empty")

    def _on_ended(self, player):
        self.banner.set_revealed(False)

    def _on_seek_press(self, gesture, n, x, y):
        self._dragging = True
        gesture.set_state(Gtk.EventSequenceState.CLAIM)

    def _on_seek_release(self, gesture, n, x, y):
        if not self._dragging:
            return
        self._dragging = False
        self.player.seek(self.seek.get_value())

    def _on_volume(self, btn, value):
        self.player.set_volume(value)

    # ---------- pantalla completa / controles ----------
    def _toggle_fullscreen(self):
        if self.is_fullscreen():
            self.unfullscreen()
        else:
            self.fullscreen()
        self.fs_btn.set_visible(True)
        self._wake_controls()

    def _on_pressed_video(self, gesture, n_press, x, y):
        if n_press == 2:
            gesture.set_state(Gtk.EventSequenceState.CLAIM)
            self._toggle_fullscreen()
        self._wake_controls()

    def _on_motion(self, motion, x, y):
        self._wake_controls()

    def _wake_controls(self):
        if self._hide_id:
            GLib.source_remove(self._hide_id)
            self._hide_id = 0
        self.controls.set_reveal_child(True)
        self._hide_id = GLib.timeout_add_seconds(3, self._auto_hide)
        return False

    def _auto_hide(self):
        self._hide_id = 0
        from gi.repository import Gst
        playing = self.player._state == Gst.State.PLAYING
        self.controls.set_reveal_child(not playing)
        return False

    def _on_key(self, ctl, keyval, keycode, state):
        name = Gdk.keyval_name(keyval)
        if name == "Escape":
            if self.is_fullscreen():
                self.unfullscreen()
            else:
                self.close()
            return True
        if name == "space" or name == "KP_space":
            self.player.toggle()
            return True
        if name in ("f", "F", "F11"):
            self._toggle_fullscreen()
            return True
        if name in ("m", "M"):
            nw = self.player.get_mute()
            self.player.set_mute(not nw)
            return True
        if name in ("Left", "KP_Left"):
            self.player.seek_by(-10)
            return True
        if name in ("Right", "KP_Right"):
            self.player.seek_by(10)
            return True
        if name in ("Up", "KP_Up"):
            v = min(1.0, self.volume.get_value() + 0.05)
            self.volume.set_value(v)
            self.player.set_volume(v)
            return True
        if name in ("Down", "KP_Down"):
            v = max(0.0, self.volume.get_value() - 0.05)
            self.volume.set_value(v)
            self.player.set_volume(v)
            return True
        return False
