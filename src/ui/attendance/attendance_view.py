from datetime import date, datetime
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from src.services.attendance_service import (
    AttendanceService,
    AttendanceServiceError,
)
from src.ui import theme


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class AttendanceView(ctk.CTkFrame):
    def __init__(
        self,
        master,
        user,
    ):
        super().__init__(
            master,
            fg_color=theme.BACKGROUND,
            corner_radius=0,
        )

        self.user = user

        self.service = (
            AttendanceService()
        )

        self.current_session = None

        self.search_var = ctk.StringVar()

        self.ministry_var = ctk.StringVar(
            value="All Ministries"
        )

        self.session_var = ctk.StringVar()

        self.session_lookup = {}
        self.ministry_lookup = {
            "All Ministries": None
        }

        self.pack_propagate(False)

        self.build_ui()
        self.load_ministries()
        self.load_sessions()

    # =====================================================
    # UI
    # =====================================================

    def build_ui(self):
        self.grid_rowconfigure(
            0,
            weight=1,
        )

        self.grid_columnconfigure(
            0,
            weight=1,
        )

        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=theme.BACKGROUND,
            corner_radius=0,
        )

        scroll.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.content = ctk.CTkFrame(
            scroll,
            fg_color="transparent",
        )

        self.content.pack(
            fill="both",
            expand=True,
            padx=28,
            pady=24,
        )

        self.build_header()
        self.build_session_bar()
        self.build_stats()
        self.build_filters()
        self.build_roster_card()

    # =====================================================
    # HEADER
    # =====================================================

    def build_header(self):
        row = ctk.CTkFrame(
            self.content,
            fg_color="transparent",
        )

        row.pack(
            fill="x",
            pady=(0, 20),
        )

        left = ctk.CTkFrame(
            row,
            fg_color="transparent",
        )

        left.pack(
            side="left",
        )

        ctk.CTkLabel(
            left,
            text="Attendance",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=27,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
        )

        ctk.CTkLabel(
            left,
            text=(
                "Manual controlled attendance with "
                "one church-wide Sunday record per member."
            ),
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            anchor="w",
            pady=(4, 0),
        )

        ctk.CTkButton(
            row,
            text="+  Open Today's Sunday Service",
            height=44,
            corner_radius=12,
            fg_color=theme.SECONDARY,
            hover_color=theme.SECONDARY_HOVER,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            command=self.open_today,
        ).pack(
            side="right",
        )

    # =====================================================
    # SESSION BAR
    # =====================================================

    def build_session_bar(self):
        card = ctk.CTkFrame(
            self.content,
            fg_color=theme.SURFACE,
            corner_radius=17,
            border_width=1,
            border_color=theme.BORDER,
        )

        card.pack(
            fill="x",
            pady=(0, 18),
        )

        inner = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )

        inner.pack(
            fill="x",
            padx=16,
            pady=14,
        )

        ctk.CTkLabel(
            inner,
            text="Attendance session",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            side="left",
            padx=(0, 10),
        )

        self.session_combo = ctk.CTkComboBox(
            inner,
            variable=self.session_var,
            values=[
                "No sessions"
            ],
            state="readonly",
            width=300,
            height=42,
            corner_radius=10,
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
            command=self.session_changed,
        )

        self.session_combo.pack(
            side="left",
        )

        self.state_label = ctk.CTkLabel(
            inner,
            text="No session selected",
            height=32,
            corner_radius=16,
            fg_color=theme.SURFACE_ALT,
            text_color=theme.TEXT_MUTED,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=9,
                weight="bold",
            ),
        )

        self.state_label.pack(
            side="left",
            padx=12,
            ipadx=10,
        )

        self.close_button = ctk.CTkButton(
            inner,
            text="Close Session",
            width=115,
            height=40,
            corner_radius=10,
            fg_color=theme.SURFACE_ALT,
            hover_color=theme.BORDER,
            text_color=theme.TEXT,
            state="disabled",
            command=self.close_current_session,
        )

        self.close_button.pack(
            side="right",
        )

    # =====================================================
    # STATS
    # =====================================================

    def build_stats(self):
        self.stats_frame = ctk.CTkFrame(
            self.content,
            fg_color="transparent",
        )

        self.stats_frame.pack(
            fill="x",
            pady=(0, 18),
        )

        for column in range(4):
            self.stats_frame.grid_columnconfigure(
                column,
                weight=1,
            )

        self.refresh_stats()

    def refresh_stats(self):
        for child in (
            self.stats_frame
            .winfo_children()
        ):
            child.destroy()

        counts = {
            "PRESENT": 0,
            "LATE": 0,
            "EXCUSED": 0,
            "ABSENT": 0,
        }

        if self.current_session:
            counts = (
                self.service
                .session_counts(
                    self.current_session[
                        "id"
                    ]
                )
            )

        cards = [
            (
                "Present",
                counts["PRESENT"],
            ),
            (
                "Late",
                counts["LATE"],
            ),
            (
                "Excused",
                counts["EXCUSED"],
            ),
            (
                "Absent",
                counts["ABSENT"],
            ),
        ]

        for index, (
            title,
            value,
        ) in enumerate(cards):

            card = ctk.CTkFrame(
                self.stats_frame,
                corner_radius=16,
                fg_color=theme.SURFACE,
                border_width=1,
                border_color=theme.BORDER,
            )

            card.grid(
                row=0,
                column=index,
                sticky="nsew",
                padx=(
                    0
                    if index == 0
                    else 6,
                    0
                    if index == 3
                    else 6,
                ),
            )

            ctk.CTkLabel(
                card,
                text=title,
                font=ctk.CTkFont(
                    family=theme.FONT_FAMILY,
                    size=10,
                    weight="bold",
                ),
                text_color=theme.TEXT_MUTED,
            ).pack(
                anchor="w",
                padx=17,
                pady=(15, 4),
            )

            ctk.CTkLabel(
                card,
                text=str(value),
                font=ctk.CTkFont(
                    family=theme.FONT_FAMILY,
                    size=26,
                    weight="bold",
                ),
                text_color=theme.TEXT,
            ).pack(
                anchor="w",
                padx=17,
                pady=(0, 15),
            )

    # =====================================================
    # FILTERS
    # =====================================================

    def build_filters(self):
        filters = ctk.CTkFrame(
            self.content,
            fg_color=theme.SURFACE,
            corner_radius=16,
            border_width=1,
            border_color=theme.BORDER,
        )

        filters.pack(
            fill="x",
            pady=(0, 18),
        )

        inner = ctk.CTkFrame(
            filters,
            fg_color="transparent",
        )

        inner.pack(
            fill="x",
            padx=15,
            pady=13,
        )

        self.search_entry = ctk.CTkEntry(
            inner,
            textvariable=self.search_var,
            placeholder_text=(
                "Search name, member number, phone or email..."
            ),
            height=43,
            corner_radius=10,
            fg_color=theme.INPUT,
            border_color=theme.BORDER,
            text_color=theme.TEXT,
            placeholder_text_color=theme.TEXT_MUTED,
        )

        self.search_entry.pack(
            side="left",
            fill="x",
            expand=True,
        )

        self.search_entry.bind(
            "<Return>",
            lambda event:
            self.refresh_roster(),
        )

        self.ministry_combo = ctk.CTkComboBox(
            inner,
            variable=self.ministry_var,
            values=[
                "All Ministries"
            ],
            state="readonly",
            width=220,
            height=43,
            corner_radius=10,
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
            command=lambda value:
            self.refresh_roster(),
        )

        self.ministry_combo.pack(
            side="left",
            padx=(10, 0),
        )

        ctk.CTkButton(
            inner,
            text="Search",
            width=90,
            height=43,
            corner_radius=10,
            fg_color=theme.SECONDARY,
            hover_color=theme.SECONDARY_HOVER,
            command=self.refresh_roster,
        ).pack(
            side="left",
            padx=(10, 0),
        )

    # =====================================================
    # ROSTER
    # =====================================================

    def build_roster_card(self):
        card = ctk.CTkFrame(
            self.content,
            fg_color=theme.SURFACE,
            corner_radius=18,
            border_width=1,
            border_color=theme.BORDER,
        )

        card.pack(
            fill="both",
            expand=True,
        )

        header = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )

        header.pack(
            fill="x",
            padx=18,
            pady=(17, 10),
        )

        self.roster_title = ctk.CTkLabel(
            header,
            text="Member roster",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=14,
                weight="bold",
            ),
            text_color=theme.TEXT,
        )

        self.roster_title.pack(
            side="left",
        )

        self.roster_frame = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )

        self.roster_frame.pack(
            fill="both",
            expand=True,
            padx=14,
            pady=(0, 15),
        )

        self.refresh_roster()

    # =====================================================
    # LOAD DATA
    # =====================================================

    def load_ministries(self):
        ministries = (
            self.service
            .list_ministries()
        )

        names = [
            "All Ministries"
        ]

        for ministry in ministries:
            names.append(
                ministry["name"]
            )

            self.ministry_lookup[
                ministry["name"]
            ] = ministry["id"]

        self.ministry_combo.configure(
            values=names
        )

    def load_sessions(self):
        sessions = (
            self.service
            .list_sessions()
        )

        self.session_lookup = {}

        labels = []

        for session in sessions:
            display_date = (
                datetime.strptime(
                    session[
                        "session_date"
                    ],
                    "%Y-%m-%d",
                )
                .strftime(
                    "%d/%m/%Y"
                )
            )

            label = (
                f"{display_date}  •  "
                f"{session['name']}"
            )

            if (
                session["state"]
                == "CLOSED"
            ):
                label += "  •  Closed"

            labels.append(
                label
            )

            self.session_lookup[
                label
            ] = session

        if labels:
            self.session_combo.configure(
                values=labels
            )

            self.session_var.set(
                labels[0]
            )

            self.current_session = (
                self.session_lookup[
                    labels[0]
                ]
            )

            self.apply_session_state()

        else:
            self.session_combo.configure(
                values=[
                    "No sessions"
                ]
            )

            self.session_var.set(
                "No sessions"
            )

            self.current_session = None

            self.apply_session_state()

        self.refresh_stats()
        self.refresh_roster()

    # =====================================================
    # SESSION ACTIONS
    # =====================================================

    def open_today(self):
        self.service.open_sunday_session(
            session_date=date.today(),
            name="Sunday Service",
            user_id=self.user.id,
        )

        self.load_sessions()

    def session_changed(
        self,
        value,
    ):
        session = (
            self.session_lookup.get(
                value
            )
        )

        if not session:
            return

        self.current_session = session

        self.apply_session_state()
        self.refresh_stats()
        self.refresh_roster()

    def apply_session_state(self):
        if not self.current_session:
            self.state_label.configure(
                text="No session selected",
                fg_color=theme.SURFACE_ALT,
            )

            self.close_button.configure(
                state="disabled"
            )

            return

        state = (
            self.current_session[
                "state"
            ]
        )

        self.state_label.configure(
            text=state.title(),
            fg_color=(
                (
                    "#E4F5EB",
                    "#153C28",
                )
                if state == "OPEN"
                else theme.SURFACE_ALT
            ),
        )

        self.close_button.configure(
            state=(
                "normal"
                if state == "OPEN"
                else "disabled"
            )
        )

    def close_current_session(self):
        if not self.current_session:
            return

        self.service.close_session(
            self.current_session["id"]
        )

        self.load_sessions()

    # =====================================================
    # ROSTER RENDERING
    # =====================================================

    def refresh_roster(self):
        for child in (
            self.roster_frame
            .winfo_children()
        ):
            child.destroy()

        if not self.current_session:
            self.roster_title.configure(
                text="Member roster"
            )

            ctk.CTkLabel(
                self.roster_frame,
                text=(
                    "Open or select an attendance "
                    "session to begin."
                ),
                text_color=theme.TEXT_MUTED,
            ).pack(
                pady=45,
            )

            return

        ministry_id = (
            self.ministry_lookup.get(
                self.ministry_var.get()
            )
        )

        members = self.service.roster(
            self.current_session["id"],
            search=self.search_var.get(),
            ministry_id=ministry_id,
        )

        self.roster_title.configure(
            text=(
                f"Member roster  •  "
                f"{len(members)} members"
            )
        )

        if not members:
            ctk.CTkLabel(
                self.roster_frame,
                text="No matching members found.",
                text_color=theme.TEXT_MUTED,
            ).pack(
                pady=45,
            )

            return

        for member in members:
            self.render_member(
                member
            )

    def render_member(
        self,
        member,
    ):
        row = ctk.CTkFrame(
            self.roster_frame,
            fg_color=theme.SURFACE_SOFT,
            corner_radius=13,
            border_width=1,
            border_color=theme.BORDER,
        )

        row.pack(
            fill="x",
            pady=5,
        )

        # ---------------------------------------------
        # PHOTO
        # ---------------------------------------------

        photo_widget = None

        if member["photo_path"]:
            path = (
                PROJECT_ROOT
                / member["photo_path"]
            )

            if path.exists():
                try:
                    image = Image.open(
                        path
                    ).convert("RGB")

                    photo = ctk.CTkImage(
                        light_image=image,
                        dark_image=image,
                        size=(48, 48),
                    )

                    photo_widget = (
                        ctk.CTkLabel(
                            row,
                            text="",
                            image=photo,
                            width=48,
                            height=48,
                        )
                    )

                    photo_widget.image = (
                        photo
                    )

                except Exception:
                    pass

        if photo_widget is None:
            parts = (
                member["full_name"]
                .split()
            )

            initials = "".join(
                part[:1]
                for part in parts[:2]
            ).upper()

            photo_widget = ctk.CTkLabel(
                row,
                text=initials or "HM",
                width=48,
                height=48,
                corner_radius=24,
                fg_color=theme.SECONDARY,
                text_color="#FFFFFF",
                font=ctk.CTkFont(
                    family=theme.FONT_FAMILY,
                    size=12,
                    weight="bold",
                ),
            )

        photo_widget.pack(
            side="left",
            padx=(13, 11),
            pady=11,
        )

        # ---------------------------------------------
        # MEMBER DETAILS
        # ---------------------------------------------

        details = ctk.CTkFrame(
            row,
            fg_color="transparent",
            width=260,
        )

        details.pack(
            side="left",
            fill="y",
            pady=10,
        )

        ctk.CTkLabel(
            details,
            text=member["full_name"],
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
        )

        ctk.CTkLabel(
            details,
            text=(
                f"{member['member_no']}  •  "
                f"{member['phone'] or 'No phone'}"
            ),
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=9,
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            anchor="w",
            pady=(3, 0),
        )

        ministries = (
            ", ".join(
                member["ministries"]
            )
            if member["ministries"]
            else "No ministry assigned"
        )

        ctk.CTkLabel(
            row,
            text=ministries,
            width=200,
            anchor="w",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=9,
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            side="left",
            padx=(20, 5),
        )

        # ---------------------------------------------
        # ATTENDANCE BUTTONS
        # ---------------------------------------------

        actions = ctk.CTkFrame(
            row,
            fg_color="transparent",
        )

        actions.pack(
            side="right",
            padx=12,
        )

        current = (
            member[
                "attendance_status"
            ]
        )

        closed = (
            self.current_session[
                "state"
            ]
            == "CLOSED"
        )

        statuses = [
            ("Present", "PRESENT"),
            ("Late", "LATE"),
            ("Excused", "EXCUSED"),
            ("Absent", "ABSENT"),
        ]

        for label, value in statuses:
            selected = (
                current == value
            )

            button = ctk.CTkButton(
                actions,
                text=label,
                width=72,
                height=34,
                corner_radius=9,
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
                state=(
                    "disabled"
                    if closed
                    else "normal"
                ),
                font=ctk.CTkFont(
                    family=theme.FONT_FAMILY,
                    size=9,
                    weight=(
                        "bold"
                        if selected
                        else "normal"
                    ),
                ),
                command=lambda mid=member["id"], s=value:
                self.mark_member(
                    mid,
                    s,
                ),
            )

            button.pack(
                side="left",
                padx=2,
            )

    # =====================================================
    # MARK MEMBER
    # =====================================================

    def mark_member(
        self,
        member_id,
        status,
    ):
        if not self.current_session:
            return

        try:
            self.service.mark(
                session_id=(
                    self.current_session[
                        "id"
                    ]
                ),
                member_id=member_id,
                status=status,
                user_id=self.user.id,
            )

        except AttendanceServiceError:
            return

        self.refresh_stats()
        self.refresh_roster()
