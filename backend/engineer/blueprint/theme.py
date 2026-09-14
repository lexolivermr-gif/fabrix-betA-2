"""
Fabrix — Blueprint theme.

Visual contract (locked by product spec):
  - SHEET ............ white paper (IKEA sheet, not a dark cyan print)
  - LINES ............ IKEA blue  #0058A3
  - CRITICAL ......... red        #CC0008   (new part, cut, force, hazard)
  - CHARACTERS ....... white      #FFFFFF   (always on a navy or red plate)

The user asked for white characters on a white sheet, which is invisible.
The resolution used everywhere in this renderer: every glyph is drawn in white
inside a solid navy (or red, when critical) plate. That keeps the sheet white,
keeps the lettering white, and keeps every label legible.
"""

# --- sheet geometry (sheet units; the whole sheet is SHEET_W x SHEET_H) ------
SHEET_W = 100.0
SHEET_H = 64.0

# layout bands
MARGIN = 2.0
BORDER_INSET = 1.1
HEADER_Y0, HEADER_Y1 = 2.6, 8.0
AREA_X0, AREA_X1 = 5.0, 95.0
AREA_Y0, AREA_Y1 = 9.5, 51.5
FOOTER_Y0, FOOTER_Y1 = 52.5, 61.4

# --- palette ----------------------------------------------------------------
WHITE = "#FFFFFF"
SHEET_BG = "#FFFFFF"

NAVY = "#0B3D6B"        # plate background + frame
NAVY_SOFT = "#1C5489"

INK = "#0058A3"         # IKEA blue — all normal geometry
INK_DARK = "#003C70"
INK_LIGHT = "#9CC2E0"   # construction lines, hidden edges
GRID_MINOR = "#E9F1F9"
GRID_MAJOR = "#D6E6F5"

CRIT = "#CC0008"        # red — critical geometry
CRIT_DARK = "#9E0006"
CRIT_WASH = "#FCE9E7"   # fill for the part introduced by the step

GHOST = "#B8CCE0"       # already-assembled context
GREY = "#6E7F8D"

# --- typography --------------------------------------------------------------
# Every glyph on a drawing is MONOSPACE. Two reasons:
#   1. it is the correct voice for an engineering drawing;
#   2. mono gives an exact, font-independent advance width (MONO_ADV em), so the
#      SVG backend and the PDF backend lay out text identically and the plates
#      that carry the white characters are always the right size.
MONO_FONT = "DejaVu Sans Mono, 'DejaVu Sans Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
MONO_ADV = 0.6015   # em advance of DejaVu Sans Mono (Courier in PDF = 0.600)
BOLD_ADV = 0.6015

# --- stroke weights (sheet units) -------------------------------------------
SW_HAIR = 0.16      # grid, construction
SW_THIN = 0.26      # hatch, secondary
SW_MED = 0.42       # normal geometry
SW_BOLD = 0.60      # the part being assembled
SW_FRAME = 0.50

# --- font sizes (sheet units) ------------------------------------------------
FS_MICRO = 1.35
FS_TINY = 1.55
FS_SMALL = 1.8
FS_BODY = 2.1
FS_LABEL = 2.4
FS_TITLE = 3.0


def text_w(s: str, size: float, bold: bool = False) -> float:
    """Exact advance width of a monospace string, in sheet units."""
    return len(s) * (MONO_ADV if not bold else BOLD_ADV) * size


def plate_w(s: str, size: float, pad: float = 0.55, bold: bool = False) -> float:
    return text_w(s, size, bold) + 2.0 * pad * size


def plate_h(size: float, pad: float = 0.42) -> float:
    return size * (1.0 + 2.0 * pad)
