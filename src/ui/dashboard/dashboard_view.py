from datetime import datetime
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from src.ui import theme
from src.services.member_service import MemberService
from src.services.attendance_service import AttendanceService
from src.ui.icons import icon
from src.ui.members.members_view import MembersView
from src.ui.attendance.attendance_view import AttendanceView


class DashboardView(ctk.CTkFrame):
    def __init__(
        self,
        master,
        user,
        on_logout,
        on_toggle_theme=None,
    ):
        super().__init__(
            master,
            fg_color=theme.BACKGROUND,
            corner_radius=0,
        )

        self.master = master
        self.user = user
        self.on_logout = on_logout
        self.on_toggle_theme = on_toggle_theme

        self.active_menu = "Dashboard"
        self.member_service = MemberService()
        self.attendance_service = AttendanceService()
        self.menu_buttons = {}
        self.logo_image = None

        self.nav_icons = {
            "Dashboard": icon("home", 20, True),
            "Members": icon("users", 20, True),
            "Attendance": icon("attendance", 20, True),
            "Ministries": icon("ministries", 20, True),
            "Sunday School": icon("book", 20, True),
            "Finance": icon("finance", 20, True),
            "Welfare": icon("heart", 20, True),
            "SMS": icon("message", 20, True),
            "Reports": icon("chart", 20, True),
            "Administration": icon("settings", 20, True),
            "Logout": icon("logout", 19, True),
        }

        self.pack(
            fill="both",
            expand=True,
        )

        self.build_shell()
        self.show_dashboard()

    # =====================================================
    # SHELL
    # =====================================================

    def build_shell(self):
        self.grid_rowconfigure(
            0,
            weight=1,
        )

        self.grid_columnconfigure(
            1,
            weight=1,
        )

        self.sidebar = ctk.CTkFrame(
            self,
            width=275,
            corner_radius=0,
            fg_color=theme.SIDEBAR,
        )

        self.sidebar.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.sidebar.grid_propagate(
            False
        )

        self.main = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color=theme.BACKGROUND,
        )

        self.main.grid(
            row=0,
            column=1,
            sticky="nsew",
        )

        self.main.grid_rowconfigure(
            1,
            weight=1,
        )

        self.main.grid_columnconfigure(
            0,
            weight=1,
        )

        self.build_sidebar()
        self.build_topbar()

    # =====================================================
    # SIDEBAR
    # =====================================================

    def build_sidebar(self):
        # -------------------------------------------------
        # Brand
        # -------------------------------------------------

        brand = ctk.CTkFrame(
            self.sidebar,
            fg_color="transparent",
        )

        brand.pack(
            fill="x",
            padx=20,
            pady=(22, 14),
        )

        logo_path = (
            Path(__file__)
            .resolve()
            .parents[3]
            / "assets"
            / "logo"
            / "hopfan_logo_clean.png"
        )

        if not logo_path.exists():
            logo_path = (
                Path(__file__)
                .resolve()
                .parents[3]
                / "assets"
                / "logo"
                / "hopfan_logo.jpg"
            )

        if logo_path.exists():
            image = Image.open(
                logo_path
            ).convert("RGBA")

            self.logo_image = ctk.CTkImage(
                light_image=image,
                dark_image=image,
                size=(64, 64),
            )

            logo_box = ctk.CTkFrame(
                brand,
                width=72,
                height=72,
                corner_radius=19,
                fg_color="#FFFFFF",
            )

            logo_box.pack(
                side="left",
            )

            logo_box.pack_propagate(
                False
            )

            ctk.CTkLabel(
                logo_box,
                text="",
                image=self.logo_image,
            ).place(
                relx=0.5,
                rely=0.5,
                anchor="center",
            )

        brand_text = ctk.CTkFrame(
            brand,
            fg_color="transparent",
        )

        brand_text.pack(
            side="left",
            padx=(13, 0),
        )

        ctk.CTkLabel(
            brand_text,
            text="HOPFAN",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=21,
                weight="bold",
            ),
            text_color="#FFFFFF",
        ).pack(
            anchor="w",
        )

        ctk.CTkLabel(
            brand_text,
            text="Management System",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
            ),
            text_color=theme.SIDEBAR_MUTED,
        ).pack(
            anchor="w",
            pady=(2, 0),
        )

        # -------------------------------------------------
        # Section label
        # -------------------------------------------------

        ctk.CTkLabel(
            self.sidebar,
            text="WORKSPACE",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=9,
                weight="bold",
            ),
            text_color=theme.SIDEBAR_MUTED,
        ).pack(
            anchor="w",
            padx=24,
            pady=(14, 7),
        )

        # -------------------------------------------------
        # Scrollable navigation
        # -------------------------------------------------

        nav = ctk.CTkScrollableFrame(
            self.sidebar,
            fg_color="transparent",
            scrollbar_button_color=theme.PRIMARY_SOFT,
            scrollbar_button_hover_color=theme.SECONDARY,
        )

        nav.pack(
            fill="both",
            expand=True,
            padx=(11, 6),
            pady=(0, 10),
        )

        items = [
            "Dashboard",
            "Members",
            "Attendance",
            "Ministries",
            "Sunday School",
            "Finance",
            "Welfare",
            "SMS",
            "Reports",
            "Administration",
        ]

        for name in items:
            button = ctk.CTkButton(
                nav,
                text=name,
                image=self.nav_icons[name],
                compound="left",
                anchor="w",
                height=46,
                corner_radius=12,
                fg_color=(
                    theme.SECONDARY
                    if name == "Dashboard"
                    else "transparent"
                ),
                hover_color=theme.SIDEBAR_SOFT,
                text_color="#FFFFFF",
                font=ctk.CTkFont(
                    family=theme.FONT_FAMILY,
                    size=11,
                    weight=(
                        "bold"
                        if name == "Dashboard"
                        else "normal"
                    ),
                ),
                command=lambda n=name:
                self.select_menu(n),
            )

            button.pack(
                fill="x",
                pady=2,
                padx=3,
            )

            self.menu_buttons[name] = button

        # -------------------------------------------------
        # Account section
        # -------------------------------------------------

        account = ctk.CTkFrame(
            self.sidebar,
            fg_color=theme.SIDEBAR_SOFT,
            corner_radius=16,
        )

        account.pack(
            fill="x",
            padx=14,
            pady=(5, 10),
        )

        avatar = ctk.CTkLabel(
            account,
            text=self.get_initials(),
            width=42,
            height=42,
            corner_radius=21,
            fg_color=theme.GREEN,
            text_color="#FFFFFF",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=12,
                weight="bold",
            ),
        )

        avatar.pack(
            side="left",
            padx=(12, 10),
            pady=12,
        )

        info = ctk.CTkFrame(
            account,
            fg_color="transparent",
        )

        info.pack(
            side="left",
            fill="both",
            expand=True,
            pady=10,
        )

        ctk.CTkLabel(
            info,
            text=self.user.username,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
                weight="bold",
            ),
            text_color="#FFFFFF",
        ).pack(
            anchor="w",
        )

        ctk.CTkLabel(
            info,
            text=self.get_primary_role(),
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=9,
            ),
            text_color=theme.SIDEBAR_MUTED,
        ).pack(
            anchor="w",
            pady=(2, 0),
        )

        logout = ctk.CTkButton(
            self.sidebar,
            text="Sign out",
            image=self.nav_icons["Logout"],
            compound="left",
            anchor="w",
            height=42,
            corner_radius=11,
            fg_color="transparent",
            hover_color="#873333",
            text_color="#FFFFFF",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
                weight="bold",
            ),
            command=self.on_logout,
        )

        logout.pack(
            fill="x",
            padx=14,
            pady=(0, 16),
        )

    # =====================================================
    # TOP BAR
    # =====================================================

    def build_topbar(self):
        topbar = ctk.CTkFrame(
            self.main,
            height=82,
            corner_radius=0,
            fg_color=theme.SURFACE,
        )

        topbar.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        topbar.grid_propagate(
            False
        )

        left = ctk.CTkFrame(
            topbar,
            fg_color="transparent",
        )

        left.pack(
            side="left",
            padx=28,
            pady=16,
        )

        self.page_title = ctk.CTkLabel(
            left,
            text="Dashboard",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=23,
                weight="bold",
            ),
            text_color=theme.TEXT,
        )

        self.page_title.pack(
            anchor="w",
        )

        self.page_subtitle = ctk.CTkLabel(
            left,
            text="Church operations overview",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
            ),
            text_color=theme.TEXT_MUTED,
        )

        self.page_subtitle.pack(
            anchor="w",
            pady=(2, 0),
        )

        right = ctk.CTkFrame(
            topbar,
            fg_color="transparent",
        )

        right.pack(
            side="right",
            padx=25,
        )

        if self.on_toggle_theme:
            theme_group = ctk.CTkFrame(
                right,
                fg_color=theme.SURFACE_ALT,
                corner_radius=18,
            )

            theme_group.pack(
                side="left",
                padx=(0, 15),
            )

            ctk.CTkLabel(
                theme_group,
                text="Dark",
                font=ctk.CTkFont(
                    family=theme.FONT_FAMILY,
                    size=10,
                    weight="bold",
                ),
                text_color=theme.TEXT,
            ).pack(
                side="left",
                padx=(11, 3),
            )

            switch = ctk.CTkSwitch(
                theme_group,
                text="",
                width=42,
                progress_color=theme.GREEN,
                command=self.on_toggle_theme,
            )

            switch.pack(
                side="left",
                padx=(3, 7),
                pady=7,
            )

            if (
                ctk.get_appearance_mode()
                == "Dark"
            ):
                switch.select()

        ctk.CTkButton(
            right,
            text="",
            image=icon("bell", 19),
            width=40,
            height=40,
            corner_radius=12,
            fg_color=theme.SURFACE_ALT,
            hover_color=theme.BORDER,
        ).pack(
            side="left",
            padx=(0, 14),
        )

        ctk.CTkLabel(
            right,
            text=self.get_initials(),
            width=42,
            height=42,
            corner_radius=21,
            fg_color=theme.SECONDARY,
            text_color="#FFFFFF",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
                weight="bold",
            ),
        ).pack(
            side="left",
        )

    # =====================================================
    # DASHBOARD
    # =====================================================

    def show_dashboard(self):
        self.clear_body()

        body = self.create_body()

        # -------------------------------------------------
        # Welcome area
        # -------------------------------------------------

        welcome = ctk.CTkFrame(
            body,
            fg_color=(
                "#EAF4FA",
                "#10283A",
            ),
            corner_radius=20,
            border_width=1,
            border_color=theme.BORDER,
        )

        welcome.pack(
            fill="x",
            pady=(0, 20),
        )

        text = ctk.CTkFrame(
            welcome,
            fg_color="transparent",
        )

        text.pack(
            side="left",
            fill="both",
            expand=True,
            padx=25,
            pady=22,
        )

        ctk.CTkLabel(
            text,
            text=f"Welcome back, {self.user.username}",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=24,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
        )

        ctk.CTkLabel(
            text,
            text=(
                "Here is a summary of today's "
                "church operations."
            ),
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            anchor="w",
            pady=(5, 0),
        )

        today = datetime.now().strftime(
            "%A, %d %B %Y"
        )

        ctk.CTkLabel(
            welcome,
            text=today,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            side="right",
            padx=25,
        )

        # -------------------------------------------------
        # KPI cards
        # -------------------------------------------------

        metrics = ctk.CTkFrame(
            body,
            fg_color="transparent",
        )

        metrics.pack(
            fill="x",
        )

        for i in range(4):
            metrics.grid_columnconfigure(
                i,
                weight=1,
            )

        # Live dashboard statistics
        member_stats = self.member_service.stats()

        attendance_stats = self.attendance_service.latest_sunday_count()

        cards = [
            (
                "Total Members",
                str(member_stats["total"]),
                f'{member_stats["active"]} active members',
                "users",
            ),
            (
                "Sunday Attendance",
                str(attendance_stats["count"]),
                (
                    "Latest Sunday service"
                    if attendance_stats["date"]
                    else "No attendance recorded yet"
                ),
                "attendance",
            ),
            (
                "Finance",
                "GHS 0.00",
                "Finance module pending",
                "finance",
            ),
            (
                "Welfare Cases",
                "0",
                "Welfare module pending",
                "heart",
            ),
        ]

        for index, card in enumerate(cards):
            self.create_metric_card(
                metrics,
                index,
                *card,
            )

        # -------------------------------------------------
        # Main lower section
        # -------------------------------------------------

        lower = ctk.CTkFrame(
            body,
            fg_color="transparent",
        )

        lower.pack(
            fill="both",
            expand=True,
            pady=(20, 0),
        )

        lower.grid_columnconfigure(
            0,
            weight=2,
        )

        lower.grid_columnconfigure(
            1,
            weight=1,
        )

        activity = self.panel(
            lower,
            "Recent activity",
        )

        activity.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 9),
        )

        self.empty_state(
            activity,
            "No recent activity yet",
            (
                "Member registrations, attendance, "
                "finance and welfare activity will "
                "appear here."
            ),
        )

        quick = self.panel(
            lower,
            "Quick actions",
        )

        quick.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(9, 0),
        )

        actions = [
            (
                "Add member",
                "Members",
                "users",
            ),
            (
                "Take attendance",
                "Attendance",
                "attendance",
            ),
            (
                "Record payment",
                "Finance",
                "finance",
            ),
            (
                "Send SMS",
                "SMS",
                "message",
            ),
        ]

        for label, destination, image_name in actions:
            ctk.CTkButton(
                quick,
                text=label,
                image=icon(
                    image_name,
                    18,
                ),
                compound="left",
                anchor="w",
                height=46,
                corner_radius=11,
                fg_color=theme.SURFACE_ALT,
                hover_color=theme.BORDER,
                text_color=theme.TEXT,
                font=ctk.CTkFont(
                    family=theme.FONT_FAMILY,
                    size=10,
                    weight="bold",
                ),
                command=lambda d=destination:
                self.select_menu(d),
            ).pack(
                fill="x",
                padx=18,
                pady=5,
            )

    # =====================================================
    # MEMBERS WORKSPACE
    # =====================================================

    def show_members(self):
        self.clear_body()

        self.body_frame = MembersView(
            self.main
        )

        self.body_frame.grid(
            row=1,
            column=0,
            sticky="nsew",
        )

    # =====================================================
    # ATTENDANCE WORKSPACE
    # =====================================================

    def show_attendance(self):
        self.clear_body()

        self.body_frame = AttendanceView(
            self.main,
            user=self.user,
        )

        self.body_frame.grid(
            row=1,
            column=0,
            sticky="nsew",
        )

    # =====================================================
    # METRIC CARD
    # =====================================================

    def create_metric_card(
        self,
        parent,
        column,
        title,
        value,
        subtitle,
        image_name,
    ):
        card = ctk.CTkFrame(
            parent,
            fg_color=theme.SURFACE,
            corner_radius=18,
            border_width=1,
            border_color=theme.BORDER,
        )

        card.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=(
                0 if column == 0 else 7,
                0 if column == 3 else 7,
            ),
        )

        inner = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )

        inner.pack(
            fill="both",
            expand=True,
            padx=18,
            pady=17,
        )

        header = ctk.CTkFrame(
            inner,
            fg_color="transparent",
        )

        header.pack(
            fill="x",
        )

        ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
                weight="bold",
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            side="left",
        )

        ctk.CTkLabel(
            header,
            text="",
            image=icon(
                image_name,
                20,
            ),
            width=38,
            height=38,
            corner_radius=11,
            fg_color=theme.SURFACE_ALT,
        ).pack(
            side="right",
        )

        ctk.CTkLabel(
            inner,
            text=value,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=27,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
            pady=(12, 2),
        )

        ctk.CTkLabel(
            inner,
            text=subtitle,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=9,
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            anchor="w",
        )

    # =====================================================
    # GENERIC PAGES
    # =====================================================

    def show_placeholder(
        self,
        name,
    ):
        self.clear_body()

        body = self.create_body()

        panel = ctk.CTkFrame(
            body,
            fg_color=theme.SURFACE,
            corner_radius=20,
            border_width=1,
            border_color=theme.BORDER,
        )

        panel.pack(
            fill="both",
            expand=True,
        )

        ctk.CTkLabel(
            panel,
            text=name,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=27,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            pady=(90, 8),
        )

        ctk.CTkLabel(
            panel,
            text=(
                f"The {name} workspace is ready "
                "for us to build next."
            ),
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=12,
            ),
            text_color=theme.TEXT_MUTED,
        ).pack()

    # =====================================================
    # COMPONENTS
    # =====================================================

    def create_body(self):
        self.body_frame = ctk.CTkScrollableFrame(
            self.main,
            fg_color=theme.BACKGROUND,
            corner_radius=0,
        )

        self.body_frame.grid(
            row=1,
            column=0,
            sticky="nsew",
        )

        body = ctk.CTkFrame(
            self.body_frame,
            fg_color="transparent",
        )

        body.pack(
            fill="both",
            expand=True,
            padx=26,
            pady=24,
        )

        return body

    def clear_body(self):
        if hasattr(
            self,
            "body_frame",
        ):
            self.body_frame.destroy()

    def panel(
        self,
        parent,
        title,
    ):
        panel = ctk.CTkFrame(
            parent,
            fg_color=theme.SURFACE,
            corner_radius=18,
            border_width=1,
            border_color=theme.BORDER,
        )

        ctk.CTkLabel(
            panel,
            text=title,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=14,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
            padx=18,
            pady=(18, 12),
        )

        return panel

    def empty_state(
        self,
        parent,
        title,
        description,
    ):
        box = ctk.CTkFrame(
            parent,
            fg_color="transparent",
        )

        box.pack(
            fill="both",
            expand=True,
            padx=22,
            pady=(30, 50),
        )

        ctk.CTkLabel(
            box,
            text=title,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=13,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack()

        ctk.CTkLabel(
            box,
            text=description,
            wraplength=420,
            justify="center",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            pady=(7, 0),
        )

    # =====================================================
    # NAVIGATION
    # =====================================================

    def select_menu(
        self,
        name,
    ):
        self.active_menu = name

        self.page_title.configure(
            text=name
        )

        subtitles = {
            "Dashboard": "Church operations overview",
            "Members": "Manage church membership",
            "Attendance": "Services and attendance records",
            "Ministries": "Church ministries and leadership",
            "Sunday School": "Children and Sunday School",
            "Finance": "Church financial management",
            "Welfare": "Welfare funds and cases",
            "SMS": "Church communication",
            "Reports": "Analytics and reporting",
            "Administration": "System administration",
        }

        self.page_subtitle.configure(
            text=subtitles.get(
                name,
                "",
            )
        )

        for menu_name, button in (
            self.menu_buttons.items()
        ):
            selected = (
                menu_name == name
            )

            button.configure(
                fg_color=(
                    theme.SECONDARY
                    if selected
                    else "transparent"
                ),
                font=ctk.CTkFont(
                    family=theme.FONT_FAMILY,
                    size=11,
                    weight=(
                        "bold"
                        if selected
                        else "normal"
                    ),
                ),
            )

        if name == "Dashboard":
            self.show_dashboard()

        elif name == "Members":
            self.show_members()

        elif name == "Attendance":
            self.show_attendance()

        else:
            self.show_placeholder(
                name
            )

    # =====================================================
    # HELPERS
    # =====================================================

    def get_primary_role(self):
        if not self.user.roles:
            return "User"

        return self.user.roles[0].name

    def get_initials(self):
        value = (
            self.user.username
            or self.user.email
            or "HU"
        )

        value = (
            value
            .replace(".", " ")
            .replace("_", " ")
        )

        parts = value.split()

        if len(parts) >= 2:
            return (
                parts[0][0]
                + parts[1][0]
            ).upper()

        return value[:2].upper()
