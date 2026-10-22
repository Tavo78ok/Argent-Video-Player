#!/usr/bin/env python3
"""Renderiza el SVG del icono a PNG usando librsvg vía ctypes.

Uso: python3 render-icons.py [ruta.svg] [dir-salida]
Fallback del build-deb.sh cuando no está rsvg-convert ni ImageMagick+librsvg.
"""
import ctypes
import sys

import cairo

SRC = sys.argv[1] if len(sys.argv) > 1 else "data/icons/scalable/apps/argent-video.svg"
OUT = sys.argv[2] if len(sys.argv) > 2 else "."


class PycairoContext(ctypes.Structure):
    _fields_ = [
        ("PyObject_HEAD", ctypes.c_byte * object.__basicsize__),
        ("ctx", ctypes.c_void_p),
        ("base_obj", ctypes.c_void_p),
    ]


class RsvgRect(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_double), ("y", ctypes.c_double),
        ("width", ctypes.c_double), ("height", ctypes.c_double),
    ]


def load_rsvg():
    for soname in ("librsvg-2.so.2", "librsvg-2.so"):
        try:
            return ctypes.CDLL(soname)
        except OSError:
            pass
    raise SystemExit("librsvg2 no está instalada")


def render(rsvg, handle, size, dst):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surf)
    ptr = PycairoContext.from_address(id(ctx)).ctx
    rect = RsvgRect(0.0, 0.0, float(size), float(size))
    if not rsvg.rsvg_handle_render_document(handle, ptr, ctypes.byref(rect), None):
        raise SystemExit(f"falló el render a {size}px")
    src_ref = cairo.ImageSurface  # pins style noqa
    surf.write_to_png(dst)


def main():
    rsvg = load_rsvg()
    rsvg.rsvg_handle_new_from_file.restype = ctypes.c_void_p
    rsvg.rsvg_handle_render_document.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(RsvgRect), ctypes.c_void_p]
    handle = rsvg.rsvg_handle_new_from_file(SRC.encode(), None)
    if not handle:
        raise SystemExit(f"no se pudo abrir {SRC}")
    for size in (256, 128, 48):
        render(rsvg, handle, size, f"{OUT}/argent-video-{size}.png")
    print("PNGs:", OUT, "256 128 48")


if __name__ == "__main__":
    main()
