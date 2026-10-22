import os
import json

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk


class Library:
    def __init__(self):
        self.dir = os.path.join(GLib.get_user_data_dir(), "argent-video")
        self.path = os.path.join(self.dir, "library.json")
        self.history = []
        self.favorites = []
        self.load()

    def load(self):
        self.history = []
        self.favorites = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.history = [dict(x) for x in data.get("history", [])]
            self.favorites = [dict(x) for x in data.get("favorites", [])]
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            os.makedirs(self.dir, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({
                    "history": self.history[:200],
                    "favorites": self.favorites[:200],
                }, f, ensure_ascii=False, indent=1)
        except OSError:
            pass

    def add_history(self, uri, title):
        if not uri:
            return
        self.history = [x for x in self.history if x.get("uri") != uri]
        self.history.insert(0, {"uri": uri, "title": title or uri})
        self.save()

    def is_fav(self, uri):
        return any(x.get("uri") == uri for x in self.favorites)

    def toggle_fav(self, uri, title):
        if self.is_fav(uri):
            self.favorites = [x for x in self.favorites if x.get("uri") != uri]
            added = False
        else:
            self.favorites.insert(0, {"uri": uri, "title": title or uri})
            added = True
        self.save()
        return added

    def remove_uri(self, uri):
        self.history = [x for x in self.history if x.get("uri") != uri]
        self.favorites = [x for x in self.favorites if x.get("uri") != uri]
        self.save()


def empty_page(name):
    return Adw.StatusPage(
        icon_name="folder-videos-symbolic",
        title=name,
        description="Nada aquí todavía.",
    )


class LibraryDialog(Adw.Dialog):
    def __init__(self, win):
        super().__init__(title="Biblioteca", content_width=600, content_height=620)
        self.win = win
        self.lib = win.lib

        self.box_hist = Gtk.ListBox()
        self.box_hist.set_selection_mode(Gtk.SelectionMode.NONE)
        self.box_hist.add_css_class("boxed-list")
        self.box_fav = Gtk.ListBox()
        self.box_fav.set_selection_mode(Gtk.SelectionMode.NONE)
        self.box_fav.add_css_class("boxed-list")

        sl = Gtk.ScrolledWindow()
        sl.set_child(self.box_hist)
        sl.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sf = Gtk.ScrolledWindow()
        sf.set_child(self.box_fav)
        sf.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        stack = Adw.ViewStack()
        p1 = stack.add_titled_with_icon(sl, "history", "Historial", "document-open-recent-symbolic")
        p2 = stack.add_titled_with_icon(sf, "favorites", "Favoritos", "starred-symbolic")

        switch = Adw.ViewSwitcher()
        switch.set_stack(stack)
        switch.set_policy(Adw.ViewSwitcherPolicy.WIDE)

        page = Adw.ToolbarView()
        header = Adw.HeaderBar()
        page.add_top_bar(header)
        head_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                           margin_top=6, margin_bottom=12, margin_start=12, margin_end=12)
        head_box.append(switch)
        head_box.append(stack)
        page.set_content(head_box)
        self.set_child(page)

        self.refresh()
        self.box_hist.connect("row-activated", self._on_row)
        self.box_fav.connect("row-activated", self._on_row)
        stack.connect("notify::visible-page", lambda s, p: self.refresh())

    def refresh(self):
        for box, items in ((self.box_hist, self.lib.history),
                           (self.box_fav, self.lib.favorites)):
            while box.get_first_child():
                box.remove(box.get_first_child())
            for it in items[:80]:
                box.append(self._row(it))
            if not items:
                label = Gtk.Label(label="— vacío —")
                label.add_css_class("dim-label")
                row = Gtk.ListBoxRow(selectable=False, activatable=False)
                row.set_child(label)
                box.append(row)

    def _row(self, it):
        title = it.get("title") or it.get("uri") or ""
        row = Gtk.ListBoxRow(activatable=True, selectable=False)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8,
                      margin_top=6, margin_bottom=6, margin_start=12, margin_end=12)
        lbl = Gtk.Label(label=title, xalign=0, ellipsize=3, hexpand=True)
        lbl.set_tooltip_text(it.get("uri") or title)
        is_fav = any(x.get("uri") == it.get("uri") for x in self.lib.favorites)

        star = Gtk.Button(icon_name="starred-symbolic" if is_fav else "non-starred-symbolic",
                          valign=Gtk.Align.CENTER)
        star.add_css_class("flat")
        star.connect("clicked", self._on_star, it)
        del_btn = Gtk.Button(icon_name="edit-delete-symbolic", valign=Gtk.Align.CENTER)
        del_btn.add_css_class("flat")
        del_btn.connect("clicked", self._on_delete, it)
        box.append(lbl)
        box.append(star)
        box.append(del_btn)
        row.set_child(box)
        row.library_item = it
        return row

    def _on_star(self, btn, it):
        self.lib.toggle_fav(it.get("uri"), it.get("title"))
        self.refresh()

    def _on_delete(self, btn, it):
        self.lib.remove_uri(it.get("uri"))
        self.refresh()

    def _on_row(self, box, row):
        it = getattr(row, "library_item", None)
        if not it:
            return
        uri = it.get("uri")
        if not uri:
            return
        self.force_close()
        self.win.play_uri(uri, it.get("title") or uri)

