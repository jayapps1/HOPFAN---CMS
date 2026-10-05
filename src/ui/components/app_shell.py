"""Shared navigation, account bar, page heading and desktop workspace."""
import customtkinter as ctk
from src.ui import theme
from src.ui.icons import icon
from src.ui.components.modern import ActionButton, Avatar, font, label


class PageHeader(ctk.CTkFrame):
    def __init__(self, master, title, subtitle=""):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        label(self, title, 24, True, anchor="w").grid(row=0, column=0, sticky="ew")
        if subtitle:
            label(self, subtitle, 12, muted=True, anchor="w").grid(row=1, column=0, sticky="ew", pady=(2, 0))
        self.actions = ctk.CTkFrame(self, fg_color="transparent", width=1, height=1)
        self.actions.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, destinations, on_select, on_logout, context):
        super().__init__(master, width=theme.SIDEBAR_WIDTH, fg_color=theme.SIDEBAR, corner_radius=0)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        brand = ctk.CTkFrame(self, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=20, pady=(24, 20))
        ctk.CTkLabel(brand, text="HOPFAN", font=font(25, True), text_color="#FFFFFF", anchor="w").pack(fill="x")
        ctk.CTkLabel(brand, text="CHURCH MANAGEMENT", font=font(10, True), text_color=theme.SIDEBAR_MUTED, anchor="w").pack(fill="x")
        ctk.CTkLabel(self, text=context, font=font(11), text_color=theme.SIDEBAR_MUTED,
                     wraplength=theme.SIDEBAR_WIDTH-36, anchor="w", justify="left").grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 12))
        nav = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0,
                                    scrollbar_button_color=theme.PRIMARY_SOFT)
        nav.grid(row=2, column=0, sticky="nsew", padx=10)
        self.buttons = {}
        for name, image in destinations:
            button = ctk.CTkButton(nav, text=name, image=icon(image, 19, True), anchor="w",
                height=39, corner_radius=8, font=font(13), fg_color="transparent",
                hover_color=theme.SIDEBAR_SOFT, text_color="#FFFFFF",
                command=lambda n=name: on_select(n))
            button.pack(fill="x", pady=3)
            self.buttons[name] = button
        ctk.CTkButton(self, text="Sign out", image=icon("logout", 19, True), anchor="w", height=40,
            fg_color="transparent", hover_color=theme.SIDEBAR_SOFT, font=font(), command=on_logout
        ).grid(row=3, column=0, sticky="ew", padx=16, pady=16)

    def select(self, name):
        for title, button in self.buttons.items():
            button.configure(fg_color=theme.SIDEBAR_SOFT if title == name else "transparent",
                             font=font(13, title == name))


class TopBar(ctk.CTkFrame):
    def __init__(self, master, user, context, toggle_theme):
        super().__init__(master, fg_color=theme.SURFACE, corner_radius=0, height=52)
        self.grid_columnconfigure(0, weight=1)
        label(self, context, 12, muted=True, anchor="w").grid(row=0, column=0, sticky="ew", padx=24, pady=10)
        self.theme_button = ActionButton(self, "Dark mode" if ctk.get_appearance_mode() == "Light" else "Light mode",
                                        lambda: self.toggle(toggle_theme), width=100)
        self.theme_button.grid(row=0, column=1, padx=12)
        Avatar(self, user.username, size=32).grid(row=0, column=2, padx=(0, 8))
        label(self, user.username, 12, True).grid(row=0, column=3, padx=(0, 24))

    def toggle(self, callback):
        if callback:
            callback()
        self.theme_button.configure(text="Dark mode" if ctk.get_appearance_mode() == "Light" else "Light mode")


class AppShell(ctk.CTkFrame):
    def __init__(self, master, user, destinations, context, on_select, on_logout, toggle_theme):
        super().__init__(master, fg_color=theme.BACKGROUND, corner_radius=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar = Sidebar(self, destinations, on_select, on_logout, context)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.main = ctk.CTkFrame(self, fg_color=theme.BACKGROUND, corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(2, weight=1)
        self.topbar = TopBar(self.main, user, context, toggle_theme)
        self.topbar.grid(row=0, column=0, sticky="ew")
        self.heading = PageHeader(self.main, "Dashboard")
        self.heading.grid(row=1, column=0, sticky="ew", padx=24, pady=(12, 10))
        self.content = ctk.CTkFrame(self.main, fg_color="transparent", corner_radius=0)
        self.content.grid(row=2, column=0, sticky="nsew")

    def page(self, title, subtitle=""):
        self.heading.destroy()
        self.heading = PageHeader(self.main, title, subtitle)
        self.heading.grid(row=1, column=0, sticky="ew", padx=24, pady=(12, 10))
        return self.heading.actions
