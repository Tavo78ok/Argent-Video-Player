import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gst", "1.0")

from gi.repository import Adw, Gio

from .window import VideoWindow

APP_ID = "os.argentos.ArgentVideo"


class ArgentVideoApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.win = None

    def do_activate(self):
        if self.win is None:
            self.win = VideoWindow(self)
        self.win.present()

    def do_open(self, files, n, hint):
        self.do_activate()
        if self.win is not None and files:
            self.win.play_open_arg(files[0])


def main():
    Adw.init()
    app = ArgentVideoApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
