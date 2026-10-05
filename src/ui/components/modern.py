"""Shared desktop surfaces, inputs, badges, avatars and fixed-footer dialogs."""
from pathlib import Path
import logging

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

from src.ui import theme

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def font(size=13, bold=False):
    return ctk.CTkFont(family=theme.FONT_FAMILY, size=size, weight="bold" if bold else "normal")


def label(master, text, size=13, bold=False, muted=False, **kwargs):
    kwargs.setdefault("height", max(18, size+4))
    return ctk.CTkLabel(master, text=text, font=font(size, bold),
                       text_color=theme.TEXT_MUTED if muted else theme.TEXT, **kwargs)


def fit_dialog_window(dialog, master, width, height, min_width=560, min_height=420):
    """Keep dialogs inside the application viewport and the active monitor."""
    parent = master.winfo_toplevel()
    parent.update_idletasks()
    scale = dialog._get_window_scaling()
    # Tk reports physical client pixels; CTk geometry takes scaled logical pixels.
    caption = max(28, parent.winfo_rooty()-parent.winfo_y())
    available_width = min(dialog.winfo_screenwidth()-60, parent.winfo_width()-32) / scale
    available_height = min(dialog.winfo_screenheight()-90, parent.winfo_height()-caption-32) / scale
    width, height = min(width, available_width), min(height, available_height)
    width, height = max(300, int(width)), max(300, int(height))
    x = max(0, int(parent.winfo_rootx()+(parent.winfo_width()-width*scale)//2))
    y = max(0, int(parent.winfo_rooty()+(parent.winfo_height()-height*scale-caption)//2))
    dialog.geometry(f"{width}x{height}+{x}+{y}")
    dialog.minsize(min(width, min_width), min(height, min_height))


class AppCard(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=theme.SURFACE, border_color=theme.BORDER,
                         border_width=1, corner_radius=14, **kwargs)


class ModernEntry(ctk.CTkEntry):
    def __init__(self, master, **kwargs):
        super().__init__(master, height=38, corner_radius=8, fg_color=theme.INPUT,
                         border_color=theme.BORDER, text_color=theme.TEXT,
                         placeholder_text_color=theme.TEXT_MUTED, font=font(), **kwargs)


class ModernComboBox(ctk.CTkComboBox):
    def __init__(self, master, values, **kwargs):
        super().__init__(master, values=values, height=38, corner_radius=8,
                         fg_color=theme.INPUT, border_color=theme.BORDER,
                         button_color=theme.SURFACE_ALT, button_hover_color=theme.BORDER,
                         text_color=theme.TEXT, dropdown_fg_color=theme.SURFACE,
                         dropdown_text_color=theme.TEXT, dropdown_hover_color=theme.SURFACE_ALT,
                         font=font(), dropdown_font=font(), state="readonly", **kwargs)
        self.set(values[0] if values else "")


class ActionButton(ctk.CTkButton):
    def __init__(self, master, text, command=None, variant="secondary", **kwargs):
        palettes = {"primary": (theme.SECONDARY, theme.SECONDARY_HOVER, "#FFFFFF"),
                    "secondary": (theme.SURFACE_ALT, theme.BORDER, theme.TEXT),
                    "danger": (theme.DANGER, "#AD3636", "#FFFFFF")}
        bg, hover, fg = palettes[variant]
        super().__init__(master, text=text, command=command, height=36, corner_radius=8,
                         fg_color=bg, hover_color=hover, text_color=fg, font=font(13, True), **kwargs)


class StatCard(AppCard):
    def __init__(self, master, title, subtitle="", icon_name=None):
        super().__init__(master)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(10, 0))
        label(header, title, size=12, muted=True).pack(side="left")
        if icon_name:
            from src.ui.icons import icon
            ctk.CTkLabel(header, text="", image=icon(icon_name, 20)).pack(side="right")
        self.value = label(self, "0", size=24, bold=True)
        self.value.pack(anchor="w", padx=14, pady=(0, 6))
        self.detail = label(self, subtitle, size=11, muted=True, anchor="w", justify="left", wraplength=210)
        if subtitle:
            self.detail.pack(fill="x", padx=14, pady=(0, 12))
        else:
            self.value.pack_configure(pady=(0, 10))

    def set(self, value):
        self.value.configure(text=str(value))

    def set_detail(self, text):
        self.detail.configure(text=text)
        if not self.detail.winfo_manager():
            self.detail.pack(fill="x", padx=14, pady=(0, 12))


class StatusBadge(ctk.CTkLabel):
    COLORS = {"PRESENT": (("#E5F4ED", "#17392E"), ("#176442", "#8CD5B1")),
              "LATE": (("#FFF2D9", "#3A301B"), ("#825300", "#F1CC82")),
              "EXCUSED": (("#E6EFF9", "#1C3249"), ("#205E94", "#9DCBF5")),
              "ABSENT": (("#FAE9EA", "#402329"), ("#94363D", "#EFA7AE")),
              "OPEN": (("#E5F4ED", "#17392E"), ("#176442", "#8CD5B1"))}

    def __init__(self, master, status):
        bg, fg = self.COLORS.get(status, (theme.SURFACE_ALT, theme.TEXT_MUTED))
        super().__init__(master, text=(status or "UNMARKED").replace("_", " ").title(),
                         fg_color=bg, text_color=fg, corner_radius=7,
                         width=83, height=27, font=font(11, True))


class Avatar(ctk.CTkLabel):
    def __init__(self, master, name, photo_path="", size=42):
        initials = "".join(part[0] for part in name.split()[:2]).upper() or "M"
        self.avatar_image = None
        if photo_path:
            path = Path(photo_path)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            try:
                with Image.open(path) as source:
                    image = ImageOps.fit(source.convert("RGBA"), (size*2, size*2))
                mask = Image.new("L", image.size, 0)
                ImageDraw.Draw(mask).ellipse((0, 0, size*2-1, size*2-1), fill=255)
                image.putalpha(mask)
                self.avatar_image = ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
            except (OSError, UnidentifiedImageError):
                logger.debug("A member avatar was unavailable.")
        super().__init__(master, text="" if self.avatar_image else initials,
                         image=self.avatar_image, width=size, height=size,
                         corner_radius=size//2, fg_color=theme.SURFACE_ALT,
                         text_color=theme.TEXT, font=font(13, True))


class EmptyState(ctk.CTkFrame):
    def __init__(self, master, title, detail=""):
        super().__init__(master, fg_color="transparent")
        label(self, title, 17, True).pack(pady=(32, 6))
        label(self, detail, muted=True, wraplength=520).pack(pady=(0, 32))


class FixedFooterDialog(ctk.CTkToplevel):
    def __init__(self, master, title, subtitle="", width=720, height=640):
        super().__init__(master)
        self.title(title)
        self.configure(fg_color=theme.BACKGROUND)
        self.transient(master.winfo_toplevel())
        fit_dialog_window(self, master, width, height)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.header = AppCard(self)
        self.header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        label(self.header, title, 24, True).pack(anchor="w", padx=18, pady=(14, 0))
        if subtitle:
            label(self.header, subtitle, muted=True, wraplength=width-85).pack(anchor="w", padx=18, pady=(2, 14))
        self.content = ctk.CTkScrollableFrame(self, fg_color=theme.SURFACE, corner_radius=12)
        self.content.grid(row=1, column=0, sticky="nsew", padx=18)
        self.error_var = ctk.StringVar(master=self, value="")
        self.error_label = ctk.CTkLabel(self, textvariable=self.error_var, text_color=theme.DANGER,
                                      font=font(12), wraplength=width-60)
        self.error_label.grid(row=2, column=0, sticky="ew", padx=18, pady=(5, 0))
        self.footer = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=0)
        self.footer.grid(row=3, column=0, sticky="ew", pady=(5, 0))
        self.cancel_button = ActionButton(self.footer, "Cancel", self.destroy, width=100)
        self.cancel_button.pack(side="left", padx=18, pady=14)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.after(80, self._activate)

    def _activate(self):
        if self.winfo_exists():
            self.grab_set()
            self.focus_set()


class ConfirmationDialog(FixedFooterDialog):
    def __init__(self, master, title, detail, on_confirm, require_reason=False):
        super().__init__(master, title, width=580, height=440)
        label(self.content, detail, wraplength=480, justify="left").pack(anchor="w", padx=14, pady=16)
        self.reason = ModernEntry(self.content, placeholder_text="Reason for this change")
        if require_reason:
            label(self.content, "Reason *", 12, True).pack(anchor="w", padx=14)
            self.reason.pack(fill="x", padx=14, pady=(4, 14))
        self.on_confirm = on_confirm
        self.require_reason = require_reason
        self.confirm_button = ActionButton(self.footer, "Confirm", self.confirm, "primary", width=120)
        self.confirm_button.pack(side="right", padx=18, pady=14)

    def confirm(self):
        reason = self.reason.get().strip()
        if self.require_reason and not reason:
            self.error_var.set("Enter a reason before continuing.")
            return
        self.on_confirm(reason, self)
