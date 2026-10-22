import gi

gi.require_version("Gst", "1.0")
gi.require_version("Gio", "2.0")
from gi.repository import GObject, GLib, Gio, Gst

Gst.init(None)


class IdleGuard:
    """Inhibe el salvapantallas mientras la reproducción está activa.

    Usa la interfaz estándar org.freedesktop.ScreenSaver por D-Bus
    (csd-screensaver en Cinnamon / gnome-screensaver / org.gnome.ScreenSaver).
    """

    SERVICES = (
        ("org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver"),
        ("org.gnome.ScreenSaver", "/org/gnome/ScreenSaver"),
    )

    def __init__(self, app_name="argent-video"):
        self._app = app_name
        self._proxy = None
        self._cookie = None
        self._want = False

    def _ensure_proxy(self):
        if self._proxy is not None:
            return True
        try:
            conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error:
            return False
        for name, path in self.SERVICES:
            try:
                proxy = Gio.DBusProxy.new_sync(
                    conn, Gio.DBusProxyFlags.NONE, None, name, path, name, None)
                if proxy.get_name_owner() is None:
                    continue
                # validar que el nombre tenga la interfaz correcta si hay varios dueños
                owner = proxy.get_name_owner()
                iface = name.rsplit(".ScreenSaver", 1)[0] + ".ScreenSaver"
                try:
                    res = conn.call_sync(
                        name, path, "org.freedesktop.DBus.Introspectable",
                        "Introspect", GLib.Variant("(s)", (path,)),
                        GLib.VariantType("(s)"), Gio.DBusCallFlags.NONE, -1, None)
                    xml = res.unpack()[0]
                    if f'"{iface}"' not in xml:
                        proxy = None
                        continue
                except GLib.Error:
                    pass
                self._proxy = proxy
                return True
            except GLib.Error:
                continue
        return False

    def set_active(self, active):
        self._want = bool(active)
        self._apply()

    def _apply(self):
        want = self._want
        if not self._ensure_proxy():
            return
        if want and self._cookie is None:
            try:
                res = self._proxy.call_sync(
                    "Inhibit",
                    GLib.Variant("(ss)", (self._app, "Reproducción en curso")),
                    Gio.DBusCallFlags.NONE, -1, None)
                self._cookie = res.unpack()[0]
            except GLib.Error:
                self._cookie = None
        elif not want and self._cookie is not None:
            try:
                self._proxy.call_sync(
                    "UnInhibit", GLib.Variant("(u)", (self._cookie,)),
                    Gio.DBusCallFlags.NONE, -1, None)
            except GLib.Error:
                pass
            self._cookie = None

    @property
    def active(self):
        return self._cookie is not None


class Player(GObject.Object):
    __gsignals__ = {
        "state-changed": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "position-changed": (GObject.SignalFlags.RUN_FIRST, None, (float, float)),
        "buffering": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "error": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "ended": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()
        factory = Gst.ElementFactory.find("gtk4paintablesink")
        self.available = factory is not None
        self.paintable = None
        self.pipeline = None
        self._timer = None
        self._state = Gst.State.NULL
        self._buffer_paused = False
        self.guard = IdleGuard()

    def open(self, uri):
        self.close()
        if not self.available:
            return
        sink = Gst.ElementFactory.make("gtk4paintablesink")
        if sink is None:
            self.available = False
            return
        self.paintable = sink.get_property("paintable")
        self.pipeline = Gst.ElementFactory.make("playbin")
        self.pipeline.set_property("uri", uri)
        self.pipeline.set_property("video-sink", sink)
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos", self._on_eos)
        bus.connect("message::error", self._on_error)
        bus.connect("message::buffering", self._on_buffering)
        bus.connect("message::state-changed", self._on_state)
        self._timer = GLib.timeout_add(200, self._tick)
        self.pipeline.set_state(Gst.State.PAUSED)

    def close(self):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = None
        if self.pipeline:
            try:
                self.pipeline.get_bus().remove_signal_watch()
            except Exception:
                pass
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
        self.paintable = None
        self._state = Gst.State.NULL
        self._buffer_paused = False
        self.guard.set_active(False)

    def play(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PLAYING)

    def pause(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PAUSED)

    def toggle(self):
        if not self.pipeline:
            return
        if self._state == Gst.State.PLAYING:
            self.pause()
        else:
            self.play()

    def stop(self):
        self.close()
        self.emit("position-changed", 0.0, 0.0)
        self.emit("state-changed", int(Gst.State.NULL))

    def seek(self, seconds):
        if not self.pipeline:
            return
        ns = int(max(seconds, 0) * Gst.SECOND)
        self.pipeline.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            ns,
        )

    def seek_by(self, delta):
        ok, pos = self.pipeline.query_position(Gst.Format.TIME) if self.pipeline else (False, 0)
        if ok:
            self.seek(max(0, pos / Gst.SECOND + delta))

    def set_volume(self, v):
        if self.pipeline:
            self.pipeline.set_property("volume", max(0.0, min(1.0, v)))

    def set_mute(self, m):
        if self.pipeline:
            self.pipeline.set_property("mute", bool(m))

    def get_mute(self):
        if self.pipeline:
            return bool(self.pipeline.get_property("mute"))
        return False

    def _on_eos(self, bus, msg):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PAUSED)
            self.pipeline.seek_simple(
                Gst.Format.TIME,
                Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                0,
            )
        self.emit("ended")

    def _on_error(self, bus, msg):
        err, debug = msg.parse_error()
        self.emit("error", str(err))

    def _on_buffering(self, bus, msg):
        percent = msg.parse_buffering()
        self.emit("buffering", int(percent))
        if not self.pipeline:
            return
        if percent < 100:
            if self._state == Gst.State.PLAYING:
                self.pipeline.set_state(Gst.State.PAUSED)
                self._buffer_paused = True
        elif self._buffer_paused:
            self.pipeline.set_state(Gst.State.PLAYING)
            self._buffer_paused = False

    def _on_state(self, bus, msg):
        if msg.src == self.pipeline:
            old, new, pending = msg.parse_state_changed()
            self._state = new
            self.guard.set_active(new == Gst.State.PLAYING)
            self.emit("state-changed", int(new))

    def position(self):
        """Posición actual en segundos (0.0 si no es consultable)."""
        if not self.pipeline:
            return 0.0
        ok, pos = self.pipeline.query_position(Gst.Format.TIME)
        return pos / Gst.SECOND if ok and pos >= 0 else 0.0

    def is_playing(self):
        return self._state == Gst.State.PLAYING

    def is_paused(self):
        return self._state == Gst.State.PAUSED

    def _tick(self):
        pipe = self.pipeline
        if not pipe:
            return False
        okd, dur = pipe.query_duration(Gst.Format.TIME)
        okp, pos = pipe.query_position(Gst.Format.TIME)
        d = dur / Gst.SECOND if okd and dur >= 0 else 0.0
        p = pos / Gst.SECOND if okp and pos >= 0 else 0.0
        self.emit("position-changed", p, d)
        return True
