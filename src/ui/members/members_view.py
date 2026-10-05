from pathlib import Path

import customtkinter as ctk
from PIL import Image
from tkinter import filedialog, messagebox

from src.services.member_service import (
    MemberService,
    MemberServiceError,
)
from src.ui import theme
from src.ui.icons import icon
from src.ui.members.member_form_dialog import MemberFormDialog


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class MembersView(ctk.CTkFrame):
    def __init__(
        self,
        master,
    ):
        super().__init__(
            master,
            fg_color=theme.BACKGROUND,
            corner_radius=0,
        )

        self.service = MemberService()

        self.search_var = ctk.StringVar()
        self.status_var = ctk.StringVar(
            value="ALL"
        )

        self.icons = {
            "users": icon(
                "users",
                20,
            ),
            "search": icon(
                "eye",
                18,
            ),
        }

        self.grid_rowconfigure(
            0,
            weight=1,
        )

        self.grid_columnconfigure(
            0,
            weight=1,
        )

        self.build_ui()

    # ==================================================
    # UI
    # ==================================================

    def build_ui(self):
        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=theme.BACKGROUND,
            corner_radius=0,
        )

        self.scroll.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self.content = ctk.CTkFrame(
            self.scroll,
            fg_color="transparent",
        )

        self.content.pack(
            fill="both",
            expand=True,
            padx=28,
            pady=24,
        )

        self.build_header()
        self.build_stats()
        self.build_filters()
        self.build_member_section()

        self.refresh()

    # ==================================================
    # HEADER
    # ==================================================

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
            text="Members",
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
                "Manage church membership, "
                "profiles and ministry assignments."
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
            text="+  Add Member",
            height=44,
            width=145,
            corner_radius=12,
            fg_color=theme.SECONDARY,
            hover_color=theme.SECONDARY_HOVER,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            command=self.add_member,
        ).pack(
            side="right",
        )

    # ==================================================
    # STATS
    # ==================================================

    def build_stats(self):
        self.stats_frame = ctk.CTkFrame(
            self.content,
            fg_color="transparent",
        )

        self.stats_frame.pack(
            fill="x",
            pady=(0, 20),
        )

        for i in range(4):
            self.stats_frame.grid_columnconfigure(
                i,
                weight=1,
            )

    def refresh_stats(self):
        for child in (
            self.stats_frame
            .winfo_children()
        ):
            child.destroy()

        stats = self.service.stats()

        cards = [
            (
                "Total members",
                stats["total"],
            ),
            (
                "Active",
                stats["active"],
            ),
            (
                "Inactive",
                stats["inactive"],
            ),
            (
                "Baptized",
                stats["baptized"],
            ),
        ]

        for i, (
            title,
            value,
        ) in enumerate(cards):

            card = ctk.CTkFrame(
                self.stats_frame,
                fg_color=theme.SURFACE,
                corner_radius=17,
                border_width=1,
                border_color=theme.BORDER,
            )

            card.grid(
                row=0,
                column=i,
                sticky="nsew",
                padx=(
                    0 if i == 0 else 6,
                    0 if i == 3 else 6,
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
                padx=18,
                pady=(17, 5),
            )

            ctk.CTkLabel(
                card,
                text=str(value),
                font=ctk.CTkFont(
                    family=theme.FONT_FAMILY,
                    size=27,
                    weight="bold",
                ),
                text_color=theme.TEXT,
            ).pack(
                anchor="w",
                padx=18,
                pady=(0, 17),
            )

    # ==================================================
    # FILTERS
    # ==================================================

    def build_filters(self):
        filters = ctk.CTkFrame(
            self.content,
            fg_color=theme.SURFACE,
            corner_radius=17,
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
            padx=16,
            pady=14,
        )

        self.search_entry = ctk.CTkEntry(
            inner,
            textvariable=self.search_var,
            placeholder_text=(
                "Search name, member number, "
                "phone or email..."
            ),
            height=44,
            corner_radius=11,
            fg_color=theme.INPUT,
            border_color=theme.BORDER,
            text_color=theme.TEXT,
            placeholder_text_color=theme.TEXT_MUTED,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
            ),
        )

        self.search_entry.pack(
            side="left",
            fill="x",
            expand=True,
        )

        self.search_entry.bind(
            "<Return>",
            lambda event:
            self.refresh(),
        )

        status = ctk.CTkOptionMenu(
            inner,
            variable=self.status_var,
            values=[
                "ALL",
                "ACTIVE",
                "INACTIVE",
                "TRANSFERRED",
                "DECEASED",
            ],
            width=150,
            height=44,
            corner_radius=11,
            fg_color=theme.SURFACE_ALT,
            button_color=theme.SECONDARY,
            button_hover_color=(
                theme.SECONDARY_HOVER
            ),
            text_color=theme.TEXT,
            command=lambda value:
            self.refresh(),
        )

        status.pack(
            side="left",
            padx=(10, 0),
        )

        ctk.CTkButton(
            inner,
            text="Search",
            width=95,
            height=44,
            corner_radius=11,
            fg_color=theme.SECONDARY,
            hover_color=theme.SECONDARY_HOVER,
            command=self.refresh,
        ).pack(
            side="left",
            padx=(10, 0),
        )

    # ==================================================
    # MEMBER LIST
    # ==================================================

    def build_member_section(self):
        self.list_card = ctk.CTkFrame(
            self.content,
            fg_color=theme.SURFACE,
            corner_radius=18,
            border_width=1,
            border_color=theme.BORDER,
        )

        self.list_card.pack(
            fill="both",
            expand=True,
        )

        heading = ctk.CTkFrame(
            self.list_card,
            fg_color="transparent",
        )

        heading.pack(
            fill="x",
            padx=18,
            pady=(17, 12),
        )

        self.result_label = ctk.CTkLabel(
            heading,
            text="Member directory",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=14,
                weight="bold",
            ),
            text_color=theme.TEXT,
        )

        self.result_label.pack(
            side="left",
        )

        self.rows = ctk.CTkFrame(
            self.list_card,
            fg_color="transparent",
        )

        self.rows.pack(
            fill="both",
            expand=True,
            padx=14,
            pady=(0, 15),
        )

    def refresh(self):
        self.refresh_stats()

        members = self.service.list_members(
            search=self.search_var.get(),
            status=self.status_var.get(),
        )

        self.result_label.configure(
            text=(
                f"Member directory  •  "
                f"{len(members)} result"
                f"{'' if len(members) == 1 else 's'}"
            )
        )

        for child in (
            self.rows.winfo_children()
        ):
            child.destroy()

        if not members:
            ctk.CTkLabel(
                self.rows,
                text="No members found.",
                font=ctk.CTkFont(
                    family=theme.FONT_FAMILY,
                    size=12,
                    weight="bold",
                ),
                text_color=theme.TEXT,
            ).pack(
                pady=(45, 5),
            )

            ctk.CTkLabel(
                self.rows,
                text=(
                    "Add your first member or "
                    "change the search filters."
                ),
                font=ctk.CTkFont(
                    family=theme.FONT_FAMILY,
                    size=10,
                ),
                text_color=theme.TEXT_MUTED,
            ).pack(
                pady=(0, 45),
            )

            return

        for member in members:
            self.member_row(
                member
            )

    def member_row(
        self,
        member,
    ):
        row = ctk.CTkFrame(
            self.rows,
            fg_color=theme.SURFACE_SOFT,
            corner_radius=13,
            border_width=1,
            border_color=theme.BORDER,
        )

        row.pack(
            fill="x",
            pady=5,
        )

        # ----------------------------------------------
        # Avatar / Photo
        # ----------------------------------------------

        photo_path = member.get(
            "photo_path"
        )

        photo_label = None

        if photo_path:
            full_path = (
                PROJECT_ROOT
                / photo_path
            )

            if full_path.exists():
                try:
                    image = Image.open(
                        full_path
                    ).convert("RGB")

                    avatar = ctk.CTkImage(
                        light_image=image,
                        dark_image=image,
                        size=(48, 48),
                    )

                    photo_label = ctk.CTkLabel(
                        row,
                        text="",
                        image=avatar,
                        width=48,
                        height=48,
                    )

                    photo_label.image = avatar

                except Exception:
                    photo_label = None

        if photo_label is None:
            initials = (
                member["first_name"][:1]
                + member["last_name"][:1]
            ).upper()

            photo_label = ctk.CTkLabel(
                row,
                text=initials,
                width=48,
                height=48,
                corner_radius=24,
                fg_color=theme.SECONDARY,
                text_color="#FFFFFF",
                font=ctk.CTkFont(
                    family=theme.FONT_FAMILY,
                    size=13,
                    weight="bold",
                ),
            )

        photo_label.pack(
            side="left",
            padx=(14, 12),
            pady=12,
        )

        # ----------------------------------------------
        # Identity
        # ----------------------------------------------

        identity = ctk.CTkFrame(
            row,
            fg_color="transparent",
            width=220,
        )

        identity.pack(
            side="left",
            fill="y",
            pady=11,
        )

        ctk.CTkLabel(
            identity,
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
            identity,
            text=member["member_no"],
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=9,
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            anchor="w",
            pady=(3, 0),
        )

        # ----------------------------------------------
        # Contact
        # ----------------------------------------------

        contact = ctk.CTkFrame(
            row,
            fg_color="transparent",
        )

        contact.pack(
            side="left",
            fill="both",
            expand=True,
            pady=11,
            padx=(20, 5),
        )

        ctk.CTkLabel(
            contact,
            text=(
                member["phone"]
                or "No phone"
            ),
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
        )

        ministries = (
            ", ".join(
                member["ministries"]
            )
            if member["ministries"]
            else "No ministry assigned"
        )

        ctk.CTkLabel(
            contact,
            text=ministries,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=9,
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            anchor="w",
            pady=(3, 0),
        )

        # ----------------------------------------------
        # Status
        # ----------------------------------------------

        status = member["status"]

        status_colors = {
            "ACTIVE": (
                "#E4F5EB",
                "#153C28",
            ),
            "INACTIVE": (
                "#F0F2F4",
                "#293440",
            ),
            "TRANSFERRED": (
                "#FFF3D7",
                "#433516",
            ),
            "DECEASED": (
                "#F5E8E8",
                "#432222",
            ),
        }

        ctk.CTkLabel(
            row,
            text=status.title(),
            height=30,
            corner_radius=15,
            fg_color=status_colors.get(
                status,
                theme.SURFACE_ALT,
            ),
            text_color=theme.TEXT,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=9,
                weight="bold",
            ),
        ).pack(
            side="left",
            padx=10,
            ipadx=9,
        )

        ctk.CTkButton(
            row,
            text="View",
            width=72,
            height=36,
            corner_radius=10,
            fg_color=theme.SURFACE_ALT,
            hover_color=theme.BORDER,
            text_color=theme.TEXT,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
                weight="bold",
            ),
            command=lambda m=member:
            self.view_member(m),
        ).pack(
            side="right",
            padx=(5, 14),
        )

    # ==================================================
    # ACTIONS
    # ==================================================

    def add_member(self):
        MemberFormDialog(
            self,
            service=self.service,
            on_saved=self.refresh,
        )

    def view_member(
        self,
        member,
    ):
        MemberProfileDialog(
            self,
            member_id=member["id"],
            service=self.service,
            on_changed=self.refresh,
        )


# ==========================================================
# MEMBER FORM
# ==========================================================

class LegacyMemberFormDialog(
    ctk.CTkToplevel
):
    def __init__(
        self,
        master,
        service,
        on_saved,
        member=None,
    ):
        super().__init__(
            master
        )

        self.service = service
        self.on_saved = on_saved
        self.member = member

        self.photo_source = None

        self.title(
            "Edit Member"
            if member
            else "Add Member"
        )

        self.geometry(
            "820x790"
        )

        self.minsize(
            760,
            700,
        )

        self.transient(
            master.winfo_toplevel()
        )

        self.grab_set()

        self.configure(
            fg_color=theme.BACKGROUND
        )

        self.variables = {}
        self.ministry_vars = {}

        self.build_ui()

    def build_ui(self):
        outer = ctk.CTkFrame(
            self,
            fg_color=theme.BACKGROUND,
            corner_radius=0,
        )

        outer.pack(
            fill="both",
            expand=True,
        )

        header = ctk.CTkFrame(
            outer,
            fg_color=theme.SURFACE,
            corner_radius=0,
            height=76,
        )

        header.pack(
            fill="x",
        )

        header.pack_propagate(
            False
        )

        ctk.CTkLabel(
            header,
            text=(
                "Edit member"
                if self.member
                else "Add new member"
            ),
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=22,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            side="left",
            padx=24,
        )

        body = ctk.CTkScrollableFrame(
            outer,
            fg_color=theme.BACKGROUND,
            corner_radius=0,
        )

        body.pack(
            fill="both",
            expand=True,
        )

        form = ctk.CTkFrame(
            body,
            fg_color=theme.SURFACE,
            corner_radius=18,
            border_width=1,
            border_color=theme.BORDER,
        )

        form.pack(
            fill="x",
            padx=24,
            pady=22,
        )

        content = ctk.CTkFrame(
            form,
            fg_color="transparent",
        )

        content.pack(
            fill="x",
            padx=24,
            pady=22,
        )

        content.grid_columnconfigure(
            0,
            weight=1,
        )

        content.grid_columnconfigure(
            1,
            weight=1,
        )

        values = (
            self.member
            or {}
        )

        fields = [
            (
                "first_name",
                "First name *",
            ),
            (
                "middle_name",
                "Middle name",
            ),
            (
                "last_name",
                "Last name *",
            ),
            (
                "phone",
                "Phone",
            ),
            (
                "alternate_phone",
                "Alternate phone",
            ),
            (
                "email",
                "Email",
            ),
            (
                "date_of_birth",
                "Date of birth (YYYY-MM-DD)",
            ),
            (
                "occupation",
                "Occupation",
            ),
            (
                "date_joined",
                "Date joined (YYYY-MM-DD)",
            ),
            (
                "baptism_date",
                "Baptism date (YYYY-MM-DD)",
            ),
        ]

        row_index = 0

        for index, (
            key,
            label,
        ) in enumerate(fields):

            column = (
                index % 2
            )

            if column == 0:
                row_index = (
                    index // 2
                )

            self._entry_field(
                content,
                row_index,
                column,
                key,
                label,
                values.get(
                    key,
                    "",
                ),
            )

        option_row = (
            len(fields) + 1
        ) // 2

        self._option_field(
            content,
            option_row,
            0,
            "gender",
            "Gender",
            [
                "",
                "MALE",
                "FEMALE",
            ],
            values.get(
                "gender",
                "",
            ),
        )

        self._option_field(
            content,
            option_row,
            1,
            "marital_status",
            "Marital status",
            [
                "",
                "SINGLE",
                "MARRIED",
                "DIVORCED",
                "WIDOWED",
            ],
            values.get(
                "marital_status",
                "",
            ),
        )

        self._option_field(
            content,
            option_row + 1,
            0,
            "status",
            "Member status",
            [
                "ACTIVE",
                "INACTIVE",
                "TRANSFERRED",
                "DECEASED",
            ],
            values.get(
                "status",
                "ACTIVE",
            ),
        )

        baptized_var = ctk.BooleanVar(
            value=bool(
                values.get(
                    "baptized",
                    False,
                )
            )
        )

        self.variables[
            "baptized"
        ] = baptized_var

        ctk.CTkCheckBox(
            content,
            text="Baptized member",
            variable=baptized_var,
            progress_color=theme.GREEN,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).grid(
            row=option_row + 1,
            column=1,
            sticky="w",
            padx=8,
            pady=(31, 8),
        )

        # Address
        address_row = option_row + 2

        ctk.CTkLabel(
            content,
            text="Residential address",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).grid(
            row=address_row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=8,
            pady=(14, 6),
        )

        address = ctk.CTkTextbox(
            content,
            height=80,
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

        address.grid(
            row=address_row + 1,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=8,
        )

        address.insert(
            "1.0",
            values.get(
                "address",
                "",
            ),
        )

        self.address_widget = address

        # Photo
        photo_row = (
            address_row + 2
        )

        ctk.CTkLabel(
            content,
            text="Profile photo",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).grid(
            row=photo_row,
            column=0,
            sticky="w",
            padx=8,
            pady=(18, 6),
        )

        self.photo_label = ctk.CTkLabel(
            content,
            text=(
                "Current photo retained"
                if values.get(
                    "photo_path"
                )
                else "No photo selected"
            ),
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
            ),
            text_color=theme.TEXT_MUTED,
        )

        self.photo_label.grid(
            row=photo_row + 1,
            column=0,
            sticky="w",
            padx=8,
        )

        ctk.CTkButton(
            content,
            text="Choose Photo",
            width=130,
            height=38,
            corner_radius=10,
            fg_color=theme.SURFACE_ALT,
            hover_color=theme.BORDER,
            text_color=theme.TEXT,
            command=self.choose_photo,
        ).grid(
            row=photo_row + 1,
            column=1,
            sticky="e",
            padx=8,
        )

        # Ministries
        ministry_row = (
            photo_row + 2
        )

        ctk.CTkLabel(
            content,
            text="Ministry assignments",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=13,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).grid(
            row=ministry_row,
            column=0,
            columnspan=2,
            sticky="w",
            padx=8,
            pady=(24, 10),
        )

        ministry_frame = ctk.CTkFrame(
            content,
            fg_color=theme.SURFACE_ALT,
            corner_radius=12,
        )

        ministry_frame.grid(
            row=ministry_row + 1,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=8,
            pady=(0, 10),
        )

        selected = set(
            values.get(
                "ministry_ids",
                [],
            )
        )

        ministries = (
            self.service
            .list_ministries()
        )

        for i, ministry in enumerate(
            ministries
        ):
            var = ctk.BooleanVar(
                value=(
                    ministry["id"]
                    in selected
                )
            )

            self.ministry_vars[
                ministry["id"]
            ] = var

            ctk.CTkCheckBox(
                ministry_frame,
                text=ministry["name"],
                variable=var,
                progress_color=theme.GREEN,
                text_color=theme.TEXT,
                font=ctk.CTkFont(
                    family=theme.FONT_FAMILY,
                    size=10,
                ),
            ).grid(
                row=i // 2,
                column=i % 2,
                sticky="w",
                padx=15,
                pady=8,
            )

        # Buttons
        buttons = ctk.CTkFrame(
            body,
            fg_color="transparent",
        )

        buttons.pack(
            fill="x",
            padx=24,
            pady=(0, 25),
        )

        ctk.CTkButton(
            buttons,
            text="Cancel",
            width=110,
            height=44,
            corner_radius=11,
            fg_color=theme.SURFACE_ALT,
            hover_color=theme.BORDER,
            text_color=theme.TEXT,
            command=self.destroy,
        ).pack(
            side="right",
        )

        ctk.CTkButton(
            buttons,
            text=(
                "Save Changes"
                if self.member
                else "Create Member"
            ),
            width=150,
            height=44,
            corner_radius=11,
            fg_color=theme.SECONDARY,
            hover_color=theme.SECONDARY_HOVER,
            command=self.save,
        ).pack(
            side="right",
            padx=(0, 10),
        )

    def _entry_field(
        self,
        parent,
        row,
        column,
        key,
        label,
        value,
    ):
        frame = ctk.CTkFrame(
            parent,
            fg_color="transparent",
        )

        frame.grid(
            row=row,
            column=column,
            sticky="ew",
            padx=8,
            pady=8,
        )

        ctk.CTkLabel(
            frame,
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

        var = ctk.StringVar(
            value=value
        )

        self.variables[
            key
        ] = var

        ctk.CTkEntry(
            frame,
            textvariable=var,
            height=43,
            corner_radius=10,
            fg_color=theme.INPUT,
            border_color=theme.BORDER,
            text_color=theme.TEXT,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
            ),
        ).pack(
            fill="x",
        )

    def _option_field(
        self,
        parent,
        row,
        column,
        key,
        label,
        choices,
        value,
    ):
        frame = ctk.CTkFrame(
            parent,
            fg_color="transparent",
        )

        frame.grid(
            row=row,
            column=column,
            sticky="ew",
            padx=8,
            pady=8,
        )

        ctk.CTkLabel(
            frame,
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

        var = ctk.StringVar(
            value=value
        )

        self.variables[
            key
        ] = var

        ctk.CTkOptionMenu(
            frame,
            variable=var,
            values=choices,
            height=43,
            corner_radius=10,
            fg_color=theme.SURFACE_ALT,
            button_color=theme.SECONDARY,
            button_hover_color=(
                theme.SECONDARY_HOVER
            ),
            text_color=theme.TEXT,
        ).pack(
            fill="x",
        )

    def choose_photo(self):
        path = filedialog.askopenfilename(
            title="Select member photo",
            filetypes=[
                (
                    "Image files",
                    "*.jpg *.jpeg *.png *.webp",
                ),
            ],
        )

        if not path:
            return

        self.photo_source = path

        self.photo_label.configure(
            text=Path(path).name
        )

    def save(self):
        data = {}

        for key, variable in (
            self.variables.items()
        ):
            data[key] = variable.get()

        data["address"] = (
            self.address_widget
            .get(
                "1.0",
                "end",
            )
            .strip()
        )

        selected_ministries = [
            ministry_id
            for ministry_id, variable
            in self.ministry_vars.items()
            if variable.get()
        ]

        try:
            if self.member:
                saved = (
                    self.service
                    .update_member(
                        self.member["id"],
                        data,
                        selected_ministries,
                    )
                )

            else:
                saved = (
                    self.service
                    .create_member(
                        data,
                        selected_ministries,
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
            messagebox.showerror(
                "Unable to save member",
                str(exc),
                parent=self,
            )
            return

        messagebox.showinfo(
            "Member saved",
            (
                f"{saved['full_name']}\n"
                f"{saved['member_no']}"
            ),
            parent=self,
        )

        self.on_saved()
        self.destroy()


# ==========================================================
# MEMBER PROFILE
# ==========================================================

class MemberProfileDialog(
    ctk.CTkToplevel
):
    def __init__(
        self,
        master,
        member_id,
        service,
        on_changed,
    ):
        super().__init__(
            master
        )

        self.member_id = member_id
        self.service = service
        self.on_changed = on_changed

        self.title(
            "Member Profile"
        )

        self.geometry(
            "680x700"
        )

        self.transient(
            master.winfo_toplevel()
        )

        self.grab_set()

        self.configure(
            fg_color=theme.BACKGROUND
        )

        self.load()

    def load(self):
        member = (
            self.service
            .get_member(
                self.member_id
            )
        )

        for child in self.winfo_children():
            child.destroy()

        body = ctk.CTkScrollableFrame(
            self,
            fg_color=theme.BACKGROUND,
            corner_radius=0,
        )

        body.pack(
            fill="both",
            expand=True,
        )

        card = ctk.CTkFrame(
            body,
            fg_color=theme.SURFACE,
            corner_radius=20,
            border_width=1,
            border_color=theme.BORDER,
        )

        card.pack(
            fill="x",
            padx=24,
            pady=24,
        )

        hero = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )

        hero.pack(
            fill="x",
            padx=24,
            pady=24,
        )

        initials = (
            member["first_name"][:1]
            + member["last_name"][:1]
        ).upper()

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
                        size=(92, 92),
                    )

                    photo_widget = ctk.CTkLabel(
                        hero,
                        text="",
                        image=photo,
                    )

                    photo_widget.image = photo

                except Exception:
                    photo_widget = None

        if photo_widget is None:
            photo_widget = ctk.CTkLabel(
                hero,
                text=initials,
                width=92,
                height=92,
                corner_radius=46,
                fg_color=theme.SECONDARY,
                text_color="#FFFFFF",
                font=ctk.CTkFont(
                    family=theme.FONT_FAMILY,
                    size=24,
                    weight="bold",
                ),
            )

        photo_widget.pack(
            side="left",
            padx=(0, 18),
        )

        title = ctk.CTkFrame(
            hero,
            fg_color="transparent",
        )

        title.pack(
            side="left",
            fill="both",
            expand=True,
        )

        ctk.CTkLabel(
            title,
            text=member["full_name"],
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=23,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
        )

        ctk.CTkLabel(
            title,
            text=member["member_no"],
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            text_color=theme.SECONDARY,
        ).pack(
            anchor="w",
            pady=(4, 0),
        )

        ctk.CTkLabel(
            title,
            text=member["status"].title(),
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
                weight="bold",
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            anchor="w",
            pady=(4, 0),
        )

        details = [
            (
                "Phone",
                member["phone"]
                or "—",
            ),
            (
                "Email",
                member["email"]
                or "—",
            ),
            (
                "Gender",
                member["gender"]
                or "—",
            ),
            (
                "Date of birth",
                member["date_of_birth"]
                or "—",
            ),
            (
                "Marital status",
                member["marital_status"]
                or "—",
            ),
            (
                "Occupation",
                member["occupation"]
                or "—",
            ),
            (
                "Date joined",
                member["date_joined"]
                or "—",
            ),
            (
                "Baptized",
                (
                    "Yes"
                    if member["baptized"]
                    else "No"
                ),
            ),
            (
                "Ministries",
                (
                    ", ".join(
                        member["ministries"]
                    )
                    if member["ministries"]
                    else "None assigned"
                ),
            ),
            (
                "Address",
                member["address"]
                or "—",
            ),
        ]

        detail_card = ctk.CTkFrame(
            card,
            fg_color=theme.SURFACE_ALT,
            corner_radius=14,
        )

        detail_card.pack(
            fill="x",
            padx=24,
            pady=(0, 20),
        )

        for label, value in details:
            row = ctk.CTkFrame(
                detail_card,
                fg_color="transparent",
            )

            row.pack(
                fill="x",
                padx=16,
                pady=8,
            )

            ctk.CTkLabel(
                row,
                text=label,
                width=130,
                anchor="w",
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
                row,
                text=value,
                anchor="w",
                wraplength=360,
                justify="left",
                font=ctk.CTkFont(
                    family=theme.FONT_FAMILY,
                    size=10,
                ),
                text_color=theme.TEXT,
            ).pack(
                side="left",
                fill="x",
                expand=True,
            )

        buttons = ctk.CTkFrame(
            card,
            fg_color="transparent",
        )

        buttons.pack(
            fill="x",
            padx=24,
            pady=(0, 24),
        )

        ctk.CTkButton(
            buttons,
            text="Close",
            width=100,
            height=42,
            corner_radius=11,
            fg_color=theme.SURFACE_ALT,
            hover_color=theme.BORDER,
            text_color=theme.TEXT,
            command=self.destroy,
        ).pack(
            side="right",
        )

        ctk.CTkButton(
            buttons,
            text="Edit Member",
            width=125,
            height=42,
            corner_radius=11,
            fg_color=theme.SECONDARY,
            hover_color=theme.SECONDARY_HOVER,
            command=lambda:
            self.edit_member(
                member
            ),
        ).pack(
            side="right",
            padx=(0, 10),
        )

    def edit_member(
        self,
        member,
    ):
        MemberFormDialog(
            self,
            service=self.service,
            member=member,
            on_saved=self.after_edit,
        )

    def after_edit(self):
        self.on_changed()
        self.load()
