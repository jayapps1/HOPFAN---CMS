# =========================================================
# HOPFAN CHURCH MANAGEMENT SYSTEM
# Production UI Theme
# =========================================================

PRIMARY = "#0B3151"
PRIMARY_DARK = "#071F34"
PRIMARY_SOFT = "#123F64"

SECONDARY = "#0A6EA8"
SECONDARY_HOVER = "#085C8D"

GREEN = "#78BE2F"
GREEN_HOVER = "#64A524"

GOLD = "#A97832"

SUCCESS = "#24905E"
WARNING = "#D69A1A"
DANGER = "#D34848"

# ---------------------------------------------------------
# ADAPTIVE SURFACES
# ---------------------------------------------------------

BACKGROUND = (
    "#F3F6FA",
    "#09111A",
)

SURFACE = (
    "#FFFFFF",
    "#101B26",
)

SURFACE_SOFT = (
    "#F8FAFC",
    "#16222E",
)

SURFACE_ALT = (
    "#EDF2F6",
    "#1B2936",
)

INPUT = (
    "#F8FAFC",
    "#17232F",
)

TEXT = (
    "#122235",
    "#F3F7FA",
)

TEXT_MUTED = (
    "#68798A",
    "#A4B3C2",
)

TEXT_FAINT = (
    "#8A98A7",
    "#778797",
)

BORDER = (
    "#DCE4EB",
    "#2B3A4A",
)

SIDEBAR = (
    "#0B3151",
    "#071F34",
)

SIDEBAR_SOFT = (
    "#174767",
    "#102E49",
)

SIDEBAR_TEXT = "#FFFFFF"
SIDEBAR_MUTED = "#C6D6E2"

FONT_FAMILY = "Segoe UI Variable"
SIDEBAR_WIDTH = 220
SPACING = (4, 8, 12, 16, 20, 24, 32)


def configure_typography(root):
    """Resolve the preferred Windows family once; retain a readable fallback."""
    from tkinter.font import families
    global FONT_FAMILY
    installed = set(families(root))
    FONT_FAMILY = next((name for name in ("Segoe UI Variable", "Segoe UI", "Arial")
                        if name in installed), "TkDefaultFont")


def desktop_work_area(root):
    """Available desktop pixels, excluding the Windows taskbar."""
    import os
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        area = wintypes.RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(area), 0):
            return area.left, area.top, area.right-area.left, area.bottom-area.top
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()
