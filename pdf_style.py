"""Estilo compartido para los PDFs del proyecto (resumen del paciente,
guías de instalación) -- misma identidad visual que la app ("Identidad
Botánica", ver theme.py): Fraunces para títulos, Karla para texto, IBM
Plex Mono para cifras, fondo crema, símbolo "Balance en Movimiento" en el
encabezado."""

import os

from fpdf import FPDF
from fpdf.drawing import color_from_hex_string

OLIVE = "#3a6b28"
INK = (34, 30, 20)
INK_SOFT = (138, 128, 100)
LINE = (231, 226, 211)
CREAM = (250, 248, 244)
OLIVE_RGB = (58, 107, 40)
TERRACOTTA_RGB = (201, 103, 63)

PAGE_W = 210
MARGIN = 18
CONTENT_W = PAGE_W - 2 * MARGIN

FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")


def draw_logo(pdf: FPDF, cx: float, cy: float, r: float = 6.0):
    """El símbolo "Balance en Movimiento" -- mismo trazo que theme.py."""
    scale = r / 17.0

    def tx(x):
        return cx + (x - 17) * scale

    def ty(y):
        return cy + (y - 17) * scale

    pdf.set_draw_color(*OLIVE_RGB)
    pdf.set_line_width(0.35)
    pdf.circle(cx, cy, r, style="D")

    with pdf.new_path() as path:
        path.style.stroke_color = color_from_hex_string(OLIVE)
        path.style.stroke_width = 0.45
        path.style.fill_color = None
        path.move_to(tx(7), ty(21))
        path.quadratic_curve_to(tx(13), ty(9), tx(17), ty(15))
        path.quadratic_curve_to(tx(21), ty(21), tx(27), ty(10))

    pdf.set_fill_color(*OLIVE_RGB)
    pdf.circle(tx(27), ty(10), 1.6 * scale, style="F")


class BrandedPDF(FPDF):
    """FPDF con el fondo crema puesto en header() -- fpdf2 llama header()
    automáticamente después de cada add_page(), incluidas las páginas que
    crea solo el salto de página automático (documentos de varias
    páginas, como las guías). Sin esto, cualquier página después de la
    primera sale en blanco en vez de color crema."""

    def header(self):
        self.set_fill_color(*CREAM)
        self.rect(0, 0, self.w, self.h, style="F")


def new_branded_pdf(auto_page_break: bool = True) -> FPDF:
    """Página A4 en blanco con las fuentes ya registradas, fondo crema y
    márgenes estándar."""
    pdf = BrandedPDF(format="A4", unit="mm")
    pdf.add_font("Fraunces", "", os.path.join(FONTS_DIR, "Fraunces-SemiBold.ttf"))
    pdf.add_font("FrauncesMedium", "", os.path.join(FONTS_DIR, "Fraunces-Medium.ttf"))
    pdf.add_font("Karla", "", os.path.join(FONTS_DIR, "Karla-Regular.ttf"))
    pdf.add_font("Karla", "B", os.path.join(FONTS_DIR, "Karla-Bold.ttf"))
    pdf.add_font("Mono", "", os.path.join(FONTS_DIR, "IBMPlexMono-Medium.ttf"))
    pdf.add_font("MonoSemiBold", "", os.path.join(FONTS_DIR, "IBMPlexMono-SemiBold.ttf"))
    pdf.set_auto_page_break(auto=auto_page_break, margin=MARGIN)
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    pdf.add_page()
    return pdf


def draw_header(pdf: FPDF, titulo: str, subtitulo: str):
    """Logo + título Fraunces + subtítulo IBM Plex Mono mayúsculas -- mismo
    encabezado que usa resumen_pdf.py."""
    draw_logo(pdf, MARGIN + 6, MARGIN + 5, r=6.0)
    pdf.set_xy(MARGIN + 15, MARGIN - 2)
    pdf.set_text_color(*INK)
    pdf.set_font("Fraunces", "", 20)
    pdf.cell(0, 9, titulo, new_x="LMARGIN", new_y="NEXT")

    pdf.set_x(MARGIN + 15)
    pdf.set_font("Mono", "", 8.5)
    pdf.set_char_spacing(0.3)
    pdf.set_text_color(*INK_SOFT)
    pdf.cell(0, 6, subtitulo.upper(), new_x="LMARGIN", new_y="NEXT")
    pdf.set_char_spacing(0)
    pdf.set_y(MARGIN + 12)


def section_title(pdf: FPDF, texto: str, size: float = 13):
    pdf.ln(2)
    pdf.set_text_color(*INK)
    pdf.set_font("FrauncesMedium", "", size)
    pdf.cell(0, 8, texto, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*LINE)
    pdf.set_line_width(0.25)
    y = pdf.get_y()
    pdf.line(MARGIN, y, PAGE_W - MARGIN, y)
    pdf.ln(4)


def pinned_footer(pdf: FPDF, texto: str):
    """Pie de página fijo cerca del final de la hoja actual -- apaga el
    salto de página automático mientras lo dibuja, porque fpdf2 interpreta
    cualquier set_y() dentro del margen inferior como "hace falta una
    página nueva" y manda el texto a una hoja en blanco aparte."""
    auto, margin = pdf.auto_page_break, pdf.b_margin
    pdf.set_auto_page_break(auto=False)
    pdf.set_y(pdf.h - 25)
    pdf.set_draw_color(*LINE)
    pdf.line(MARGIN, pdf.get_y(), PAGE_W - MARGIN, pdf.get_y())
    pdf.set_font("Karla", "", 8)
    pdf.set_text_color(*INK_SOFT)
    pdf.set_y(pdf.h - 20)
    pdf.cell(0, 6, texto, new_x="LMARGIN", new_y="NEXT")
    pdf.set_auto_page_break(auto=auto, margin=margin)
