import calendar
from datetime import date, datetime
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageOps
from tkinter import filedialog, messagebox

from src.services.member_service import (
    MemberServiceError,
)
from src.ui import theme


PROJECT_ROOT = Path(__file__).resolve().parents[3]


# =========================================================
# DATE PICKER
# =========================================================

class DatePickerDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        initial_date=None,
        on_select=None,
    ):
        super().__init__(master)

        self.on_select = on_select
        self.selected_date = (
            initial_date
            or date.today()
        )

        self.year = self.selected_date.year
        self.month = self.selected_date.month

        self.title("Select Date")
        self.resizable(False, False)
        self.configure(
            fg_color=theme.BACKGROUND
        )

        self.transient(
            master.winfo_toplevel()
        )
        self.grab_set()

        self.center_window(
            430,
            485,
        )

        self.build_ui()

    # -----------------------------------------------------

    def center_window(
        self,
        width,
        height,
    ):
        self.update_idletasks()

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        x = max(
            10,
            (screen_w - width) // 2,
        )

        y = max(
            10,
            (screen_h - height) // 2,
        )

        self.geometry(
            f"{width}x{height}+{x}+{y}"
        )

    # -----------------------------------------------------

    def build_ui(self):
        card = ctk.CTkFrame(
            self,
            corner_radius=22,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )

        card.pack(
            fill="both",
            expand=True,
            padx=16,
            pady=16,
        )

        ctk.CTkLabel(
            card,
            text="Select Date",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=20,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
            padx=20,
            pady=(20, 3),
        )

        ctk.CTkLabel(
            card,
            text=(
                "Choose the month, year and day."
            ),
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            anchor="w",
            padx=20,
            pady=(0, 15),
        )

        selectors = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )

        selectors.pack(
            fill="x",
            padx=20,
            pady=(0, 15),
        )

        selectors.grid_columnconfigure(
            0,
            weight=2,
        )

        selectors.grid_columnconfigure(
            1,
            weight=1,
        )

        month_names = [
            calendar.month_name[i]
            for i in range(1, 13)
        ]

        self.month_var = ctk.StringVar(
            value=calendar.month_name[
                self.month
            ]
        )

        self.month_combo = ctk.CTkComboBox(
            selectors,
            values=month_names,
            variable=self.month_var,
            state="readonly",
            height=44,
            corner_radius=11,
            fg_color=theme.INPUT,
            border_color=theme.BORDER,
            button_color=theme.SECONDARY,
            button_hover_color=(
                theme.SECONDARY_HOVER
            ),
            dropdown_fg_color=theme.SURFACE,
            dropdown_hover_color=(
                theme.SURFACE_ALT
            ),
            dropdown_text_color=theme.TEXT,
            text_color=theme.TEXT,
            command=self.month_changed,
        )

        self.month_combo.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(0, 7),
        )

        current_year = date.today().year

        years = [
            str(year)
            for year in range(
                current_year + 5,
                1899,
                -1,
            )
        ]

        self.year_var = ctk.StringVar(
            value=str(
                self.year
            )
        )

        self.year_combo = ctk.CTkComboBox(
            selectors,
            values=years,
            variable=self.year_var,
            state="readonly",
            height=44,
            corner_radius=11,
            fg_color=theme.INPUT,
            border_color=theme.BORDER,
            button_color=theme.SECONDARY,
            button_hover_color=(
                theme.SECONDARY_HOVER
            ),
            dropdown_fg_color=theme.SURFACE,
            dropdown_hover_color=(
                theme.SURFACE_ALT
            ),
            dropdown_text_color=theme.TEXT,
            text_color=theme.TEXT,
            command=self.year_changed,
        )

        self.year_combo.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(7, 0),
        )

        self.calendar_frame = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )

        self.calendar_frame.pack(
            fill="both",
            expand=True,
            padx=20,
        )

        footer = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )

        footer.pack(
            fill="x",
            padx=20,
            pady=(8, 20),
        )

        ctk.CTkButton(
            footer,
            text="Today",
            width=90,
            height=40,
            corner_radius=10,
            fg_color=theme.SURFACE_ALT,
            hover_color=theme.BORDER,
            text_color=theme.TEXT,
            command=self.select_today,
        ).pack(
            side="left",
        )

        ctk.CTkButton(
            footer,
            text="Cancel",
            width=90,
            height=40,
            corner_radius=10,
            fg_color="transparent",
            hover_color=theme.SURFACE_ALT,
            border_width=1,
            border_color=theme.BORDER,
            text_color=theme.TEXT,
            command=self.destroy,
        ).pack(
            side="right",
        )

        self.render_calendar()

    # -----------------------------------------------------

    def month_changed(
        self,
        value,
    ):
        self.month = list(
            calendar.month_name
        ).index(
            value
        )

        self.render_calendar()

    def year_changed(
        self,
        value,
    ):
        self.year = int(
            value
        )

        self.render_calendar()

    # -----------------------------------------------------

    def render_calendar(self):
        for widget in (
            self.calendar_frame
            .winfo_children()
        ):
            widget.destroy()

        headings = [
            "Mon",
            "Tue",
            "Wed",
            "Thu",
            "Fri",
            "Sat",
            "Sun",
        ]

        for column in range(7):
            self.calendar_frame.grid_columnconfigure(
                column,
                weight=1,
            )

        for column, heading in enumerate(
            headings
        ):
            ctk.CTkLabel(
                self.calendar_frame,
                text=heading,
                font=ctk.CTkFont(
                    family=theme.FONT_FAMILY,
                    size=9,
                    weight="bold",
                ),
                text_color=theme.TEXT_MUTED,
            ).grid(
                row=0,
                column=column,
                padx=2,
                pady=(0, 7),
            )

        weeks = calendar.monthcalendar(
            self.year,
            self.month,
        )

        today = date.today()

        for row, week in enumerate(
            weeks,
            start=1,
        ):
            for column, day in enumerate(
                week
            ):
                if day == 0:
                    continue

                is_today = (
                    self.year == today.year
                    and self.month == today.month
                    and day == today.day
                )

                is_selected = (
                    self.year
                    == self.selected_date.year
                    and self.month
                    == self.selected_date.month
                    and day
                    == self.selected_date.day
                )

                foreground = "transparent"
                text_color = theme.TEXT

                if is_selected:
                    foreground = theme.SECONDARY
                    text_color = "#FFFFFF"

                elif is_today:
                    foreground = theme.SURFACE_ALT

                ctk.CTkButton(
                    self.calendar_frame,
                    text=str(day),
                    width=42,
                    height=39,
                    corner_radius=10,
                    fg_color=foreground,
                    hover_color=theme.BORDER,
                    text_color=text_color,
                    font=ctk.CTkFont(
                        family=theme.FONT_FAMILY,
                        size=10,
                        weight=(
                            "bold"
                            if is_selected
                            or is_today
                            else "normal"
                        ),
                    ),
                    command=lambda d=day:
                    self.choose_day(d),
                ).grid(
                    row=row,
                    column=column,
                    padx=2,
                    pady=2,
                )

    # -----------------------------------------------------

    def choose_day(
        self,
        day,
    ):
        value = date(
            self.year,
            self.month,
            day,
        )

        if self.on_select:
            self.on_select(
                value
            )

        self.destroy()

    def select_today(self):
        if self.on_select:
            self.on_select(
                date.today()
            )

        self.destroy()


# =========================================================
# MEMBER FORM
# =========================================================

class MemberFormDialog(ctk.CTkToplevel):
    def __init__(
        self,
        master,
        service,
        on_saved,
        member=None,
    ):
        super().__init__(master)

        self.service = service
        self.on_saved = on_saved
        self.member = member

        self.variables = {}

        self.photo_source = None
        self.photo_image = None

        # No CTkCheckBox is used.
        self.baptized = bool(
            member.get(
                "baptized",
                False,
            )
            if member
            else False
        )

        self.selected_ministries = set(
            member.get(
                "ministry_ids",
                [],
            )
            if member
            else []
        )

        self.ministry_buttons = {}

        initial_status = (
            member.get(
                "status",
                "ACTIVE",
            )
            if member
            else "ACTIVE"
        )

        self.membership_status = (
            initial_status
            .replace(
                "_",
                " ",
            )
            .title()
        )

        self.title(
            "Edit Member"
            if member
            else "Add New Member"
        )

        self.configure(
            fg_color=theme.BACKGROUND
        )

        self.transient(
            master.winfo_toplevel()
        )

        self.grab_set()

        self.configure_window()

        self.build_header()

        # Footer is built BEFORE workspace.
        # Therefore it never scrolls away.
        self.build_footer()

        self.build_workspace()

        self.bind(
            "<Control-s>",
            lambda event:
            self.save(),
        )

    # =====================================================
    # WINDOW
    # =====================================================

    def configure_window(self):
        self.update_idletasks()

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        width = min(
            1120,
            screen_w - 70,
        )

        height = min(
            790,
            screen_h - 110,
        )

        x = max(
            20,
            (screen_w - width) // 2,
        )

        y = max(
            20,
            (screen_h - height) // 2,
        )

        self.geometry(
            f"{width}x{height}+{x}+{y}"
        )

        self.minsize(
            min(
                900,
                width,
            ),
            min(
                620,
                height,
            ),
        )

    # =====================================================
    # DATE FORMAT
    # =====================================================

    @staticmethod
    def display_date(
        value,
    ):
        if not value:
            return ""

        if isinstance(
            value,
            date,
        ):
            return value.strftime(
                "%d/%m/%Y"
            )

        raw = str(
            value
        ).strip()

        for fmt in (
            "%Y-%m-%d",
            "%d/%m/%Y",
        ):
            try:
                parsed = datetime.strptime(
                    raw,
                    fmt,
                ).date()

                return parsed.strftime(
                    "%d/%m/%Y"
                )

            except ValueError:
                pass

        return raw

    @staticmethod
    def storage_date(
        value,
    ):
        raw = str(
            value or ""
        ).strip()

        if not raw:
            return ""

        try:
            parsed = datetime.strptime(
                raw,
                "%d/%m/%Y",
            ).date()

        except ValueError as exc:
            raise MemberServiceError(
                f"Invalid date: {raw}. "
                "Use DD/MM/YYYY."
            ) from exc

        return parsed.isoformat()

    # =====================================================
    # HEADER
    # =====================================================

    def build_header(self):
        header = ctk.CTkFrame(
            self,
            height=84,
            corner_radius=0,
            fg_color=theme.SURFACE,
        )

        header.pack(
            side="top",
            fill="x",
        )

        header.pack_propagate(
            False
        )

        left = ctk.CTkFrame(
            header,
            fg_color="transparent",
        )

        left.pack(
            side="left",
            padx=28,
            pady=15,
        )

        ctk.CTkLabel(
            left,
            text=(
                "Edit member profile"
                if self.member
                else "Create member profile"
            ),
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
            left,
            text=(
                "Personal information, contact details, "
                "church records and ministries"
            ),
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            anchor="w",
            pady=(3, 0),
        )

        number_card = ctk.CTkFrame(
            header,
            corner_radius=13,
            fg_color=theme.SURFACE_ALT,
        )

        number_card.pack(
            side="right",
            padx=28,
            pady=15,
        )

        ctk.CTkLabel(
            number_card,
            text="MEMBER NUMBER",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=8,
                weight="bold",
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            anchor="w",
            padx=15,
            pady=(8, 1),
        )

        number = (
            self.member.get(
                "member_no",
                "",
            )
            if self.member
            else ""
        )

        ctk.CTkLabel(
            number_card,
            text=(
                number
                or "Generated automatically"
            ),
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
            padx=15,
            pady=(0, 8),
        )

    # =====================================================
    # FIXED SAVE FOOTER
    # =====================================================

    def build_footer(self):
        footer = ctk.CTkFrame(
            self,
            height=78,
            corner_radius=0,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )

        footer.pack(
            side="bottom",
            fill="x",
        )

        footer.pack_propagate(
            False
        )

        info = ctk.CTkFrame(
            footer,
            fg_color="transparent",
        )

        info.pack(
            side="left",
            padx=28,
        )

        ctk.CTkLabel(
            info,
            text="Required fields are marked *",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
        )

        ctk.CTkLabel(
            info,
            text="Ctrl + S to save",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=9,
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            anchor="w",
        )

        self.save_button = ctk.CTkButton(
            footer,
            text=(
                "Save Changes"
                if self.member
                else "Save Member"
            ),
            width=160,
            height=48,
            corner_radius=12,
            fg_color=theme.SECONDARY,
            hover_color=theme.SECONDARY_HOVER,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            command=self.save,
        )

        self.save_button.pack(
            side="right",
            padx=(10, 28),
        )

        ctk.CTkButton(
            footer,
            text="Cancel",
            width=110,
            height=48,
            corner_radius=12,
            fg_color=theme.SURFACE_ALT,
            hover_color=theme.BORDER,
            border_width=1,
            border_color=theme.BORDER,
            text_color=theme.TEXT,
            command=self.destroy,
        ).pack(
            side="right",
        )

    # =====================================================
    # WORKSPACE
    # =====================================================

    def build_workspace(self):
        workspace = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color=theme.BACKGROUND,
        )

        workspace.pack(
            fill="both",
            expand=True,
        )

        workspace.grid_rowconfigure(
            0,
            weight=1,
        )

        workspace.grid_columnconfigure(
            1,
            weight=1,
        )

        self.build_photo_panel(
            workspace
        )

        self.build_form(
            workspace
        )

    # =====================================================
    # PHOTO
    # =====================================================

    def build_photo_panel(
        self,
        parent,
    ):
        panel = ctk.CTkFrame(
            parent,
            width=260,
            corner_radius=20,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )

        panel.grid(
            row=0,
            column=0,
            sticky="ns",
            padx=(20, 10),
            pady=18,
        )

        panel.grid_propagate(
            False
        )

        ctk.CTkLabel(
            panel,
            text="Profile Photo",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=16,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
            padx=20,
            pady=(22, 4),
        )

        ctk.CTkLabel(
            panel,
            text=(
                "Used for identification and "
                "attendance records."
            ),
            wraplength=210,
            justify="left",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=9,
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            anchor="w",
            padx=20,
        )

        holder = ctk.CTkFrame(
            panel,
            width=174,
            height=174,
            corner_radius=87,
            fg_color=theme.SURFACE_ALT,
            border_width=2,
            border_color=theme.BORDER,
        )

        holder.pack(
            pady=(25, 18),
        )

        holder.pack_propagate(
            False
        )

        self.photo_preview = ctk.CTkLabel(
            holder,
            text="",
        )

        self.photo_preview.place(
            relx=0.5,
            rely=0.5,
            anchor="center",
        )

        self.initials_label = ctk.CTkLabel(
            holder,
            text=self.get_initials(),
            width=160,
            height=160,
            corner_radius=80,
            fg_color=theme.SECONDARY,
            text_color="#FFFFFF",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=34,
                weight="bold",
            ),
        )

        self.initials_label.place(
            relx=0.5,
            rely=0.5,
            anchor="center",
        )

        self.load_existing_photo()

        ctk.CTkButton(
            panel,
            text="Upload Photo",
            height=44,
            corner_radius=12,
            fg_color=theme.SECONDARY,
            hover_color=theme.SECONDARY_HOVER,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            command=self.choose_photo,
        ).pack(
            fill="x",
            padx=20,
        )

        self.photo_name = ctk.CTkLabel(
            panel,
            text="JPG, PNG or WEBP • Max 10 MB",
            wraplength=210,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=9,
            ),
            text_color=theme.TEXT_MUTED,
        )

        self.photo_name.pack(
            pady=(9, 20),
            padx=20,
        )

        ctk.CTkFrame(
            panel,
            height=1,
            fg_color=theme.BORDER,
        ).pack(
            fill="x",
            padx=20,
            pady=(0, 18),
        )

        ctk.CTkLabel(
            panel,
            text="Membership Status",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
            padx=20,
        )

        self.status_badge = ctk.CTkLabel(
            panel,
            text=self.membership_status,
            height=32,
            corner_radius=16,
            fg_color=(
                "#E4F5EB",
                "#153C28",
            ),
            text_color=theme.TEXT,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=9,
                weight="bold",
            ),
        )

        self.status_badge.pack(
            anchor="w",
            padx=20,
            pady=(7, 0),
            ipadx=10,
        )

    # =====================================================
    # FORM
    # =====================================================

    def build_form(
        self,
        parent,
    ):
        self.scroll = ctk.CTkScrollableFrame(
            parent,
            corner_radius=0,
            fg_color=theme.BACKGROUND,
        )

        self.scroll.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(0, 20),
            pady=18,
        )

        values = (
            self.member
            or {}
        )

        # -------------------------------------------------
        # PERSONAL
        # -------------------------------------------------

        personal = self.section(
            "Personal Information",
            "Basic member identity information.",
        )

        self.two_columns(
            personal
        )

        self.entry(
            personal,
            1,
            0,
            "first_name",
            "First name *",
            values.get(
                "first_name",
                "",
            ),
        )

        self.entry(
            personal,
            1,
            1,
            "middle_name",
            "Middle name",
            values.get(
                "middle_name",
                "",
            ),
        )

        self.entry(
            personal,
            2,
            0,
            "last_name",
            "Last name *",
            values.get(
                "last_name",
                "",
            ),
        )

        self.combo(
            personal,
            2,
            1,
            "gender",
            "Gender",
            [
                "Select gender",
                "Male",
                "Female",
            ],
            self.pretty(
                values.get(
                    "gender",
                    "",
                ),
                "Select gender",
            ),
        )

        self.date_input(
            personal,
            3,
            0,
            "date_of_birth",
            "Date of birth",
            self.display_date(
                values.get(
                    "date_of_birth",
                    "",
                )
            ),
        )

        self.combo(
            personal,
            3,
            1,
            "marital_status",
            "Marital status",
            [
                "Select status",
                "Single",
                "Married",
                "Divorced",
                "Widowed",
            ],
            self.pretty(
                values.get(
                    "marital_status",
                    "",
                ),
                "Select status",
            ),
        )

        self.entry(
            personal,
            4,
            0,
            "occupation",
            "Occupation",
            values.get(
                "occupation",
                "",
            ),
            columnspan=2,
            placeholder=(
                "e.g. Teacher, Engineer, Trader"
            ),
        )

        # -------------------------------------------------
        # CONTACT
        # -------------------------------------------------

        contact = self.section(
            "Contact Information",
            (
                "Phone, email and residential "
                "information."
            ),
        )

        self.two_columns(
            contact
        )

        self.entry(
            contact,
            1,
            0,
            "phone",
            "Primary phone",
            values.get(
                "phone",
                "",
            ),
            placeholder="e.g. 054 201 1738",
        )

        self.entry(
            contact,
            1,
            1,
            "alternate_phone",
            "Alternate phone",
            values.get(
                "alternate_phone",
                "",
            ),
            placeholder="Optional",
        )

        self.entry(
            contact,
            2,
            0,
            "email",
            "Email address",
            values.get(
                "email",
                "",
            ),
            columnspan=2,
            placeholder="name@example.com",
        )

        ctk.CTkLabel(
            contact,
            text="Residential address",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="w",
            padx=12,
            pady=(10, 6),
        )

        self.address_widget = ctk.CTkTextbox(
            contact,
            height=78,
            corner_radius=11,
            fg_color=theme.INPUT,
            border_width=1,
            border_color=theme.BORDER,
            text_color=theme.TEXT,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
            ),
        )

        self.address_widget.grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=12,
            pady=(0, 14),
        )

        self.address_widget.insert(
            "1.0",
            values.get(
                "address",
                "",
            ),
        )

        # -------------------------------------------------
        # CHURCH
        # -------------------------------------------------

        church = self.section(
            "Church Information",
            (
                "Membership status, baptism and "
                "church joining date."
            ),
        )

        self.two_columns(
            church
        )

        self.date_input(
            church,
            1,
            0,
            "date_joined",
            "Date joined",
            self.display_date(
                values.get(
                    "date_joined",
                    "",
                )
            ),
        )

        # Clear visible membership status.
        status_frame = ctk.CTkFrame(
            church,
            fg_color="transparent",
        )

        status_frame.grid(
            row=1,
            column=1,
            sticky="ew",
            padx=12,
            pady=8,
        )

        ctk.CTkLabel(
            status_frame,
            text="Membership status",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
            pady=(0, 6),
        )

        self.status_selector = (
            ctk.CTkSegmentedButton(
                status_frame,
                values=[
                    "Active",
                    "Inactive",
                    "Transferred",
                    "Deceased",
                ],
                height=43,
                corner_radius=10,
                fg_color=theme.SURFACE_ALT,
                selected_color=theme.SECONDARY,
                selected_hover_color=(
                    theme.SECONDARY_HOVER
                ),
                unselected_color=(
                    theme.SURFACE_ALT
                ),
                unselected_hover_color=(
                    theme.BORDER
                ),
                text_color=theme.TEXT,
                font=ctk.CTkFont(
                    family=theme.FONT_FAMILY,
                    size=9,
                    weight="bold",
                ),
                command=self.set_status,
            )
        )

        self.status_selector.pack(
            fill="x",
        )

        self.status_selector.set(
            self.membership_status
        )

        # Baptism - no checkbox.
        baptism_control = ctk.CTkFrame(
            church,
            fg_color="transparent",
        )

        baptism_control.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=12,
            pady=8,
        )

        ctk.CTkLabel(
            baptism_control,
            text="Baptism",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
            pady=(0, 6),
        )

        self.baptism_button = ctk.CTkButton(
            baptism_control,
            text="",
            height=44,
            corner_radius=11,
            command=self.toggle_baptism,
        )

        self.baptism_button.pack(
            fill="x",
        )

        self.refresh_baptism_button()

        self.date_input(
            church,
            2,
            1,
            "baptism_date",
            "Baptism date",
            self.display_date(
                values.get(
                    "baptism_date",
                    "",
                )
            ),
        )

        # -------------------------------------------------
        # MINISTRIES
        # -------------------------------------------------

        ministries = self.section(
            "Ministry Assignments",
            (
                "Click a ministry to select or "
                "remove it."
            ),
        )

        self.two_columns(
            ministries
        )

        available = (
            self.service
            .list_ministries()
        )

        for index, ministry in enumerate(
            available
        ):
            ministry_id = ministry["id"]

            button = ctk.CTkButton(
                ministries,
                text=ministry["name"],
                height=44,
                corner_radius=11,
                command=lambda mid=ministry_id:
                self.toggle_ministry(
                    mid
                ),
            )

            button.grid(
                row=1 + index // 2,
                column=index % 2,
                sticky="ew",
                padx=12,
                pady=6,
            )

            self.ministry_buttons[
                ministry_id
            ] = button

        self.refresh_ministry_buttons()

    # =====================================================
    # COMPONENTS
    # =====================================================

    def section(
        self,
        title,
        subtitle,
    ):
        card = ctk.CTkFrame(
            self.scroll,
            corner_radius=18,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )

        card.pack(
            fill="x",
            pady=(0, 15),
        )

        heading = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )

        heading.grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=12,
            pady=(16, 8),
        )

        ctk.CTkLabel(
            heading,
            text=title,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=15,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
        )

        ctk.CTkLabel(
            heading,
            text=subtitle,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=9,
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            anchor="w",
            pady=(2, 0),
        )

        return card

    @staticmethod
    def two_columns(
        frame,
    ):
        frame.grid_columnconfigure(
            0,
            weight=1,
            uniform="form",
        )

        frame.grid_columnconfigure(
            1,
            weight=1,
            uniform="form",
        )

    # -----------------------------------------------------

    def entry(
        self,
        parent,
        row,
        column,
        key,
        label,
        value="",
        placeholder="",
        columnspan=1,
    ):
        shell = ctk.CTkFrame(
            parent,
            fg_color="transparent",
        )

        shell.grid(
            row=row,
            column=column,
            columnspan=columnspan,
            sticky="ew",
            padx=12,
            pady=8,
        )

        ctk.CTkLabel(
            shell,
            text=label,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
            pady=(0, 6),
        )

        variable = ctk.StringVar(
            value=value
        )

        self.variables[
            key
        ] = variable

        ctk.CTkEntry(
            shell,
            textvariable=variable,
            placeholder_text=placeholder,
            height=44,
            corner_radius=11,
            fg_color=theme.INPUT,
            border_color=theme.BORDER,
            text_color=theme.TEXT,
            placeholder_text_color=(
                theme.TEXT_MUTED
            ),
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
            ),
        ).pack(
            fill="x",
        )

        if key in (
            "first_name",
            "last_name",
        ):
            variable.trace_add(
                "write",
                lambda *_:
                self.refresh_initials(),
            )

    # -----------------------------------------------------

    def combo(
        self,
        parent,
        row,
        column,
        key,
        label,
        values,
        value,
    ):
        shell = ctk.CTkFrame(
            parent,
            fg_color="transparent",
        )

        shell.grid(
            row=row,
            column=column,
            sticky="ew",
            padx=12,
            pady=8,
        )

        ctk.CTkLabel(
            shell,
            text=label,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
            pady=(0, 6),
        )

        variable = ctk.StringVar(
            value=value
        )

        self.variables[
            key
        ] = variable

        ctk.CTkComboBox(
            shell,
            variable=variable,
            values=values,
            state="readonly",
            height=44,
            corner_radius=11,
            fg_color=theme.INPUT,
            border_color=theme.BORDER,
            button_color=theme.SECONDARY,
            button_hover_color=(
                theme.SECONDARY_HOVER
            ),
            dropdown_fg_color=theme.SURFACE,
            dropdown_hover_color=(
                theme.SURFACE_ALT
            ),
            dropdown_text_color=theme.TEXT,
            text_color=theme.TEXT,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
            ),
        ).pack(
            fill="x",
        )

    # -----------------------------------------------------

    def date_input(
        self,
        parent,
        row,
        column,
        key,
        label,
        value,
    ):
        shell = ctk.CTkFrame(
            parent,
            fg_color="transparent",
        )

        shell.grid(
            row=row,
            column=column,
            sticky="ew",
            padx=12,
            pady=8,
        )

        ctk.CTkLabel(
            shell,
            text=label,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
            pady=(0, 6),
        )

        row_frame = ctk.CTkFrame(
            shell,
            fg_color="transparent",
        )

        row_frame.pack(
            fill="x",
        )

        row_frame.grid_columnconfigure(
            0,
            weight=1,
        )

        variable = ctk.StringVar(
            value=value
        )

        self.variables[
            key
        ] = variable

        ctk.CTkEntry(
            row_frame,
            textvariable=variable,
            placeholder_text="DD/MM/YYYY",
            height=44,
            corner_radius=11,
            fg_color=theme.INPUT,
            border_color=theme.BORDER,
            text_color=theme.TEXT,
            placeholder_text_color=(
                theme.TEXT_MUTED
            ),
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
            ),
        ).grid(
            row=0,
            column=0,
            sticky="ew",
        )

        ctk.CTkButton(
            row_frame,
            text="Choose",
            width=76,
            height=44,
            corner_radius=11,
            fg_color=theme.SURFACE_ALT,
            hover_color=theme.BORDER,
            text_color=theme.TEXT,
            command=lambda:
            self.open_date_picker(
                variable
            ),
        ).grid(
            row=0,
            column=1,
            padx=(7, 0),
        )

    # =====================================================
    # STATUS
    # =====================================================

    def set_status(
        self,
        value,
    ):
        self.membership_status = value

        self.status_badge.configure(
            text=value
        )

    # =====================================================
    # BAPTISM
    # =====================================================

    def toggle_baptism(self):
        self.baptized = (
            not self.baptized
        )

        self.refresh_baptism_button()

    def refresh_baptism_button(self):
        if self.baptized:
            self.baptism_button.configure(
                text="Baptized  ✓",
                fg_color=theme.GREEN,
                hover_color=theme.GREEN_HOVER,
                text_color="#FFFFFF",
            )

        else:
            self.baptism_button.configure(
                text="Not Baptized",
                fg_color=theme.SURFACE_ALT,
                hover_color=theme.BORDER,
                text_color=theme.TEXT,
            )

    # =====================================================
    # MINISTRY SELECTION
    # =====================================================

    def toggle_ministry(
        self,
        ministry_id,
    ):
        if ministry_id in (
            self.selected_ministries
        ):
            self.selected_ministries.remove(
                ministry_id
            )

        else:
            self.selected_ministries.add(
                ministry_id
            )

        self.refresh_ministry_buttons()

    def refresh_ministry_buttons(self):
        for ministry_id, button in (
            self.ministry_buttons.items()
        ):
            selected = (
                ministry_id
                in self.selected_ministries
            )

            button.configure(
                fg_color=(
                    theme.SECONDARY
                    if selected
                    else theme.SURFACE_ALT
                ),
                hover_color=(
                    theme.SECONDARY_HOVER
                    if selected
                    else theme.BORDER
                ),
                text_color=(
                    "#FFFFFF"
                    if selected
                    else theme.TEXT
                ),
                border_width=(
                    0
                    if selected
                    else 1
                ),
                border_color=theme.BORDER,
            )

    # =====================================================
    # CALENDAR
    # =====================================================

    def open_date_picker(
        self,
        variable,
    ):
        initial = date.today()

        value = variable.get().strip()

        if value:
            try:
                initial = datetime.strptime(
                    value,
                    "%d/%m/%Y",
                ).date()

            except ValueError:
                pass

        DatePickerDialog(
            self,
            initial_date=initial,
            on_select=lambda selected:
            variable.set(
                selected.strftime(
                    "%d/%m/%Y"
                )
            ),
        )

    # =====================================================
    # PHOTO
    # =====================================================

    @staticmethod
    def pretty(
        value,
        default,
    ):
        if not value:
            return default

        return (
            str(value)
            .replace(
                "_",
                " ",
            )
            .title()
        )

    def get_initials(self):
        if not self.member:
            return "HM"

        first = self.member.get(
            "first_name",
            "",
        )

        last = self.member.get(
            "last_name",
            "",
        )

        return (
            first[:1]
            + last[:1]
        ).upper() or "HM"

    def refresh_initials(self):
        if self.photo_source:
            return

        if (
            self.member
            and self.member.get(
                "photo_path"
            )
        ):
            return

        first_var = self.variables.get(
            "first_name"
        )

        last_var = self.variables.get(
            "last_name"
        )

        first = (
            first_var.get()
            if first_var
            else ""
        )

        last = (
            last_var.get()
            if last_var
            else ""
        )

        self.initials_label.configure(
            text=(
                first[:1]
                + last[:1]
            ).upper() or "HM"
        )

    # -----------------------------------------------------

    @staticmethod
    def circular_image(
        path,
        size=160,
    ):
        image = Image.open(
            path
        ).convert("RGBA")

        image = ImageOps.fit(
            image,
            (size, size),
            method=Image.Resampling.LANCZOS,
        )

        mask = Image.new(
            "L",
            (size, size),
            0,
        )

        drawer = ImageDraw.Draw(
            mask
        )

        drawer.ellipse(
            (
                0,
                0,
                size - 1,
                size - 1,
            ),
            fill=255,
        )

        image.putalpha(
            mask
        )

        return image

    def display_photo(
        self,
        path,
    ):
        try:
            image = self.circular_image(
                path
            )

        except Exception:
            return

        self.photo_image = ctk.CTkImage(
            light_image=image,
            dark_image=image,
            size=(160, 160),
        )

        self.initials_label.place_forget()

        self.photo_preview.configure(
            image=self.photo_image,
        )

    def load_existing_photo(self):
        if not self.member:
            return

        relative = self.member.get(
            "photo_path"
        )

        if not relative:
            return

        path = (
            PROJECT_ROOT
            / relative
        )

        if path.exists():
            self.display_photo(
                path
            )

    def choose_photo(self):
        selected = filedialog.askopenfilename(
            parent=self,
            title="Select Member Photo",
            filetypes=[
                (
                    "Images",
                    "*.jpg *.jpeg *.png *.webp",
                ),
            ],
        )

        if not selected:
            return

        path = Path(
            selected
        )

        if path.stat().st_size > (
            10 * 1024 * 1024
        ):
            messagebox.showerror(
                "Photo too large",
                "Choose an image under 10 MB.",
                parent=self,
            )
            return

        self.photo_source = selected

        self.display_photo(
            selected
        )

        self.photo_name.configure(
            text=path.name
        )

    # =====================================================
    # SAVE
    # =====================================================

    def save(self):
        self.save_button.configure(
            text="Saving...",
            state="disabled",
        )

        self.update_idletasks()

        try:
            data = {
                key: variable.get().strip()
                for key, variable
                in self.variables.items()
            }

            first_name = data.get(
                "first_name",
                ""
            )

            last_name = data.get(
                "last_name",
                ""
            )

            if not first_name:
                raise MemberServiceError(
                    "First name is required."
                )

            if not last_name:
                raise MemberServiceError(
                    "Last name is required."
                )

            for key in (
                "date_of_birth",
                "date_joined",
                "baptism_date",
            ):
                data[key] = self.storage_date(
                    data.get(
                        key,
                        "",
                    )
                )

            gender = data.get(
                "gender",
                ""
            )

            data["gender"] = (
                ""
                if gender == "Select gender"
                else gender.upper()
            )

            marital = data.get(
                "marital_status",
                ""
            )

            data["marital_status"] = (
                ""
                if marital == "Select status"
                else marital.upper()
            )

            data["status"] = (
                self.membership_status
                .upper()
                .replace(
                    " ",
                    "_",
                )
            )

            data["baptized"] = (
                self.baptized
            )

            if not self.baptized:
                data["baptism_date"] = ""

            email = data.get(
                "email",
                ""
            )

            if (
                email
                and (
                    "@" not in email
                    or "." not in email.split(
                        "@"
                    )[-1]
                )
            ):
                raise MemberServiceError(
                    "Enter a valid email address."
                )

            data["address"] = (
                self.address_widget
                .get(
                    "1.0",
                    "end",
                )
                .strip()
            )

            ministry_ids = list(
                self.selected_ministries
            )

            if self.member:
                saved = (
                    self.service
                    .update_member(
                        self.member["id"],
                        data,
                        ministry_ids,
                    )
                )

            else:
                saved = (
                    self.service
                    .create_member(
                        data,
                        ministry_ids,
                    )
                )

            if self.photo_source:
                saved = (
                    self.service
                    .set_photo(
                        saved["id"],
                        self.photo_source,
                    )
                )

        except MemberServiceError as exc:
            self.restore_save_button()

            messagebox.showerror(
                "Unable to save member",
                str(exc),
                parent=self,
            )

            return

        except Exception as exc:
            self.restore_save_button()

            messagebox.showerror(
                "Unexpected Error",
                str(exc),
                parent=self,
            )

            return

        messagebox.showinfo(
            "Member Saved",
            (
                f"{saved['full_name']} "
                f"was saved successfully.\n\n"
                f"Member number: "
                f"{saved['member_no']}"
            ),
            parent=self,
        )

        self.on_saved()
        self.destroy()

    def restore_save_button(self):
        self.save_button.configure(
            text=(
                "Save Changes"
                if self.member
                else "Save Member"
            ),
            state="normal",
        )
