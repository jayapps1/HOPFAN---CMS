from pathlib import Path

import customtkinter as ctk
from PIL import Image

from src.services.auth_service import (
    AuthenticationError,
    AuthService,
)
from src.ui import theme
from src.ui.components.totp_input import TotpInput
from src.ui.icons import icon
from src.ui.login.forgot_password_dialog import (
    ForgotPasswordDialog,
)


class LoginView(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_login_success,
        on_toggle_theme,
    ):
        super().__init__(
            master,
            fg_color=theme.BACKGROUND,
            corner_radius=0,
        )

        self.master = master
        self.on_login_success = on_login_success
        self.on_toggle_theme = on_toggle_theme

        self.auth_service = AuthService()

        self.email_var = ctk.StringVar()
        self.password_var = ctk.StringVar()
        self.status_var = ctk.StringVar()

        self.login_method = "password"
        self.password_visible = False

        self.logo_image = None

        self.icons = {
            "mail": icon("mail", 20),
            "lock": icon("lock", 20),
            "eye": icon("eye", 20),
            "eye_off": icon("eye_off", 20),
            "shield": icon("shield", 20),
            "moon": icon("moon", 18),
            "sun": icon("sun", 18),
            "arrow": icon("arrow", 18),
        }

        self.pack(
            fill="both",
            expand=True,
        )

        self.build_shell()
        self.show_password_form()

        self.master.bind(
            "<Return>",
            self.handle_enter,
        )

    # =====================================================
    # MAIN SHELL
    # =====================================================

    def build_shell(self):
        self.grid_rowconfigure(
            0,
            weight=1,
        )

        self.grid_columnconfigure(
            0,
            weight=5,
        )

        self.grid_columnconfigure(
            1,
            weight=6,
        )

        # -------------------------------------------------
        # LEFT BRAND AREA
        # -------------------------------------------------

        self.brand_panel = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color=theme.SIDEBAR,
        )

        self.brand_panel.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        # -------------------------------------------------
        # RIGHT LOGIN AREA
        # -------------------------------------------------

        self.login_panel = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color=theme.BACKGROUND,
        )

        self.login_panel.grid(
            row=0,
            column=1,
            sticky="nsew",
        )

        self.build_brand_panel()
        self.build_theme_control()
        self.build_login_card()

    # =====================================================
    # LEFT BRAND PANEL
    # =====================================================

    def build_brand_panel(self):
        wrapper = ctk.CTkFrame(
            self.brand_panel,
            fg_color="transparent",
        )

        wrapper.place(
            relx=0.5,
            rely=0.5,
            anchor="center",
        )

        project_root = (
            Path(__file__)
            .resolve()
            .parents[3]
        )

        clean_logo = (
            project_root
            / "assets"
            / "logo"
            / "hopfan_logo_clean.png"
        )

        original_logo = (
            project_root
            / "assets"
            / "logo"
            / "hopfan_logo.jpg"
        )

        logo_path = (
            clean_logo
            if clean_logo.exists()
            else original_logo
        )

        if logo_path.exists():
            image = Image.open(
                logo_path
            ).convert("RGBA")

            image.thumbnail(
                (190, 190)
            )

            self.logo_image = ctk.CTkImage(
                light_image=image,
                dark_image=image,
                size=(180, 180),
            )

            logo_shell = ctk.CTkFrame(
                wrapper,
                width=210,
                height=210,
                corner_radius=36,
                fg_color="#FFFFFF",
            )

            logo_shell.pack(
                anchor="w",
                pady=(0, 34),
            )

            logo_shell.pack_propagate(
                False
            )

            ctk.CTkLabel(
                logo_shell,
                text="",
                image=self.logo_image,
            ).place(
                relx=0.5,
                rely=0.5,
                anchor="center",
            )

        # -------------------------------------------------
        # BRAND NAME
        # -------------------------------------------------

        ctk.CTkLabel(
            wrapper,
            text="HOUSE OF PRAYER",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=31,
                weight="bold",
            ),
            text_color="#FFFFFF",
        ).pack(
            anchor="w",
        )

        ctk.CTkLabel(
            wrapper,
            text="FOR ALL NATIONS",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=31,
                weight="bold",
            ),
            text_color="#FFFFFF",
        ).pack(
            anchor="w",
            pady=(0, 8),
        )

        ctk.CTkLabel(
            wrapper,
            text="Church Management System",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=14,
            ),
            text_color=theme.SIDEBAR_MUTED,
        ).pack(
            anchor="w",
        )

        ctk.CTkFrame(
            wrapper,
            width=86,
            height=4,
            corner_radius=2,
            fg_color=theme.GREEN,
        ).pack(
            anchor="w",
            pady=(28, 20),
        )

        ctk.CTkLabel(
            wrapper,
            text="NO JESUS CHRIST - NO LIFE",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=12,
                weight="bold",
            ),
            text_color="#FFFFFF",
        ).pack(
            anchor="w",
        )

        # -------------------------------------------------
        # SECURITY CHIPS
        # -------------------------------------------------

        chips = ctk.CTkFrame(
            wrapper,
            fg_color="transparent",
        )

        chips.pack(
            anchor="w",
            pady=(34, 0),
        )

        for text in (
            "Secure access",
            "Private data",
            "Role based",
        ):
            ctk.CTkLabel(
                chips,
                text=text,
                height=32,
                corner_radius=16,
                fg_color=theme.SIDEBAR_SOFT,
                text_color="#D9E7F0",
                font=ctk.CTkFont(
                    family=theme.FONT_FAMILY,
                    size=10,
                    weight="bold",
                ),
            ).pack(
                side="left",
                padx=(0, 8),
                ipadx=10,
            )

        # -------------------------------------------------
        # LEFT FOOTER
        # -------------------------------------------------

        ctk.CTkLabel(
            self.brand_panel,
            text="HOPFAN • Church Management System",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=9,
            ),
            text_color=theme.SIDEBAR_MUTED,
        ).place(
            relx=0.07,
            rely=0.955,
            anchor="w",
        )

    # =====================================================
    # DARK / LIGHT CONTROL
    # =====================================================

    def build_theme_control(self):
        self.theme_box = ctk.CTkFrame(
            self.login_panel,
            height=42,
            corner_radius=21,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )

        self.theme_box.place(
            relx=0.94,
            rely=0.045,
            anchor="ne",
        )

        self.theme_icon = ctk.CTkLabel(
            self.theme_box,
            text="",
            image=(
                self.icons["moon"]
                if ctk.get_appearance_mode()
                == "Light"
                else self.icons["sun"]
            ),
        )

        self.theme_icon.pack(
            side="left",
            padx=(12, 4),
        )

        self.theme_label = ctk.CTkLabel(
            self.theme_box,
            text=(
                "Dark"
                if ctk.get_appearance_mode()
                == "Light"
                else "Light"
            ),
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            text_color=theme.TEXT,
        )

        self.theme_label.pack(
            side="left",
            padx=(2, 4),
        )

        self.theme_switch = ctk.CTkSwitch(
            self.theme_box,
            text="",
            width=42,
            command=self.change_theme,
            progress_color=theme.GREEN,
        )

        self.theme_switch.pack(
            side="left",
            padx=(2, 9),
        )

        if (
            ctk.get_appearance_mode()
            == "Dark"
        ):
            self.theme_switch.select()

    def change_theme(self):
        self.on_toggle_theme()

        self.after(
            20,
            self.refresh_theme_control,
        )

    def refresh_theme_control(self):
        dark = (
            ctk.get_appearance_mode()
            == "Dark"
        )

        self.theme_icon.configure(
            image=(
                self.icons["sun"]
                if dark
                else self.icons["moon"]
            )
        )

        self.theme_label.configure(
            text=(
                "Light"
                if dark
                else "Dark"
            )
        )

    # =====================================================
    # LOGIN CARD
    # =====================================================

    def build_login_card(self):
        # -------------------------------------------------
        # OUTER SOFT BORDER / GLASS LAYER
        # -------------------------------------------------

        glass_border = ctk.CTkFrame(
            self.login_panel,
            width=548,
            height=662,
            corner_radius=34,
            fg_color=theme.BORDER,
        )

        glass_border.place(
            relx=0.5,
            rely=0.52,
            anchor="center",
        )

        glass_border.pack_propagate(
            False
        )

        self.glass_card = ctk.CTkFrame(
            glass_border,
            corner_radius=33,
            fg_color=(
                "#FFFFFF",
                "#111B25",
            ),
        )

        self.glass_card.pack(
            fill="both",
            expand=True,
            padx=1,
            pady=1,
        )

        self.content = ctk.CTkFrame(
            self.glass_card,
            fg_color="transparent",
        )

        self.content.pack(
            fill="both",
            expand=True,
            padx=50,
            pady=46,
        )

    # =====================================================
    # COMMON CONTENT
    # =====================================================

    def clear_content(self):
        for widget in (
            self.content.winfo_children()
        ):
            widget.destroy()

        self.status_var.set("")

    def build_header(self):
        # -------------------------------------------------
        # SECURITY EYEBROW
        # -------------------------------------------------

        eyebrow = ctk.CTkFrame(
            self.content,
            fg_color="transparent",
        )

        eyebrow.pack(
            fill="x",
        )

        ctk.CTkLabel(
            eyebrow,
            text="",
            image=self.icons["shield"],
        ).pack(
            side="left",
            padx=(0, 8),
        )

        ctk.CTkLabel(
            eyebrow,
            text="SECURE ACCESS",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            text_color=theme.GREEN,
        ).pack(
            side="left",
        )

        ctk.CTkLabel(
            self.content,
            text="Welcome back",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=36,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
            pady=(10, 7),
        )

        ctk.CTkLabel(
            self.content,
            text=(
                "Choose your preferred sign-in method "
                "to continue."
            ),
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=13,
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            anchor="w",
            pady=(0, 26),
        )

        self.build_auth_selector()

    # =====================================================
    # LOGIN METHOD SELECTOR
    # =====================================================

    def build_auth_selector(self):
        selector = ctk.CTkFrame(
            self.content,
            height=54,
            corner_radius=15,
            fg_color=theme.SURFACE_ALT,
        )

        selector.pack(
            fill="x",
            pady=(0, 28),
        )

        selector.pack_propagate(
            False
        )

        password_active = (
            self.login_method
            == "password"
        )

        self.password_tab = ctk.CTkButton(
            selector,
            text="Password",
            height=44,
            corner_radius=12,
            fg_color=(
                theme.SURFACE
                if password_active
                else "transparent"
            ),
            hover_color=theme.BORDER,
            text_color=theme.TEXT,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=12,
                weight="bold",
            ),
            command=self.show_password_form,
        )

        self.password_tab.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(5, 3),
            pady=5,
        )

        self.totp_tab = ctk.CTkButton(
            selector,
            text="Authenticator",
            height=44,
            corner_radius=12,
            fg_color=(
                theme.SURFACE
                if not password_active
                else "transparent"
            ),
            hover_color=theme.BORDER,
            text_color=theme.TEXT,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=12,
                weight="bold",
            ),
            command=self.show_totp_form,
        )

        self.totp_tab.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(3, 5),
            pady=5,
        )

    # =====================================================
    # EMAIL FIELD
    # =====================================================

    def build_email_field(self):
        ctk.CTkLabel(
            self.content,
            text="Email address",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=12,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
            pady=(0, 8),
        )

        shell = ctk.CTkFrame(
            self.content,
            height=60,
            corner_radius=15,
            fg_color=theme.INPUT,
            border_width=1,
            border_color=theme.BORDER,
        )

        shell.pack(
            fill="x",
        )

        shell.pack_propagate(
            False
        )

        ctk.CTkLabel(
            shell,
            text="",
            image=self.icons["mail"],
            width=44,
        ).pack(
            side="left",
            padx=(10, 0),
        )

        self.email_entry = ctk.CTkEntry(
            shell,
            textvariable=self.email_var,
            placeholder_text="you@example.com",
            height=52,
            corner_radius=0,
            fg_color="transparent",
            border_width=0,
            text_color=theme.TEXT,
            placeholder_text_color=theme.TEXT_MUTED,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=13,
            ),
        )

        self.email_entry.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(5, 12),
        )

    # =====================================================
    # PASSWORD LOGIN FORM
    # =====================================================

    def show_password_form(self):
        self.login_method = "password"

        self.clear_content()
        self.build_header()
        self.build_email_field()

        title_row = ctk.CTkFrame(
            self.content,
            fg_color="transparent",
        )

        title_row.pack(
            fill="x",
            pady=(22, 8),
        )

        ctk.CTkLabel(
            title_row,
            text="Password",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=12,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            side="left",
        )

        ctk.CTkButton(
            title_row,
            text="Forgot password?",
            width=126,
            height=30,
            corner_radius=8,
            fg_color="transparent",
            hover_color=theme.SURFACE_ALT,
            text_color=theme.SECONDARY,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            command=self.open_forgot_password,
        ).pack(
            side="right",
        )

        # -------------------------------------------------
        # PASSWORD SHELL
        # -------------------------------------------------

        shell = ctk.CTkFrame(
            self.content,
            height=60,
            corner_radius=15,
            fg_color=theme.INPUT,
            border_width=1,
            border_color=theme.BORDER,
        )

        shell.pack(
            fill="x",
        )

        shell.pack_propagate(
            False
        )

        ctk.CTkLabel(
            shell,
            text="",
            image=self.icons["lock"],
            width=44,
        ).pack(
            side="left",
            padx=(10, 0),
        )

        self.password_entry = ctk.CTkEntry(
            shell,
            textvariable=self.password_var,
            placeholder_text="Enter your password",
            show="•",
            height=52,
            corner_radius=0,
            fg_color="transparent",
            border_width=0,
            text_color=theme.TEXT,
            placeholder_text_color=theme.TEXT_MUTED,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=13,
            ),
        )

        self.password_entry.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(5, 0),
        )

        self.password_button = ctk.CTkButton(
            shell,
            text="",
            image=self.icons["eye"],
            width=46,
            height=46,
            corner_radius=11,
            fg_color="transparent",
            hover_color=theme.SURFACE_ALT,
            command=self.toggle_password,
        )

        self.password_button.pack(
            side="right",
            padx=(0, 7),
        )

        self.build_status()

        # -------------------------------------------------
        # SIGN IN BUTTON
        # -------------------------------------------------

        self.signin_button = ctk.CTkButton(
            self.content,
            text="Sign in",
            image=self.icons["arrow"],
            compound="right",
            height=56,
            corner_radius=15,
            fg_color=theme.SECONDARY,
            hover_color=theme.SECONDARY_HOVER,
            text_color="#FFFFFF",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=13,
                weight="bold",
            ),
            command=self.login_with_password,
        )

        self.signin_button.pack(
            fill="x",
            pady=(23, 0),
        )

        ctk.CTkLabel(
            self.content,
            text="Press Enter to sign in quickly",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
            ),
            text_color=theme.TEXT_FAINT,
        ).pack(
            pady=(16, 0),
        )

        self.build_footer()

        if self.email_var.get():
            self.password_entry.focus_set()
        else:
            self.email_entry.focus_set()

    # =====================================================
    # AUTHENTICATOR LOGIN FORM
    # =====================================================

    def show_totp_form(self):
        self.login_method = "totp"

        self.clear_content()
        self.build_header()
        self.build_email_field()

        ctk.CTkLabel(
            self.content,
            text="Authenticator code",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=12,
                weight="bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w",
            pady=(24, 8),
        )

        ctk.CTkLabel(
            self.content,
            text=(
                "Enter the current 6-digit code from "
                "your authenticator app."
            ),
            justify="left",
            wraplength=410,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            anchor="w",
            pady=(0, 17),
        )

        self.totp_input = TotpInput(
            self.content,
            on_complete=self.login_with_totp,
        )

        self.totp_input.pack(
            pady=(0, 4),
        )

        self.build_status()

        ctk.CTkLabel(
            self.content,
            text=(
                "You will be signed in automatically "
                "when the sixth digit is valid."
            ),
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=10,
            ),
            text_color=theme.TEXT_FAINT,
        ).pack(
            pady=(17, 0),
        )

        self.build_footer()

        if self.email_var.get():
            self.totp_input.focus_first()
        else:
            self.email_entry.focus_set()

    # =====================================================
    # FOOTER
    # =====================================================

    def build_footer(self):
        separator = ctk.CTkFrame(
            self.content,
            height=1,
            fg_color=theme.BORDER,
        )

        separator.pack(
            fill="x",
            pady=(30, 18),
        )

        footer = ctk.CTkFrame(
            self.content,
            fg_color="transparent",
        )

        footer.pack(
            fill="x",
        )

        ctk.CTkLabel(
            footer,
            text="Protected HOPFAN access",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=9,
                weight="bold",
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            side="left",
        )

        ctk.CTkLabel(
            footer,
            text="Contact ICT for account assistance",
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=9,
            ),
            text_color=theme.TEXT_FAINT,
        ).pack(
            side="right",
        )

    # =====================================================
    # STATUS
    # =====================================================

    def build_status(self):
        ctk.CTkLabel(
            self.content,
            textvariable=self.status_var,
            justify="left",
            wraplength=410,
            font=ctk.CTkFont(
                family=theme.FONT_FAMILY,
                size=11,
                weight="bold",
            ),
            text_color=theme.DANGER,
        ).pack(
            anchor="w",
            pady=(13, 0),
        )

    # =====================================================
    # PASSWORD
    # =====================================================

    def toggle_password(self):
        self.password_visible = (
            not self.password_visible
        )

        self.password_entry.configure(
            show=(
                ""
                if self.password_visible
                else "•"
            )
        )

        self.password_button.configure(
            image=(
                self.icons["eye_off"]
                if self.password_visible
                else self.icons["eye"]
            )
        )

    def handle_enter(
        self,
        event=None,
    ):
        if self.login_method == "password":
            self.login_with_password()

    def login_with_password(self):
        email = (
            self.email_var.get().strip()
        )

        password = (
            self.password_var.get()
        )

        self.status_var.set("")

        if not email:
            self.status_var.set(
                "Enter your email address."
            )

            self.email_entry.focus_set()
            return

        if not password:
            self.status_var.set(
                "Enter your password."
            )

            self.password_entry.focus_set()
            return

        self.signin_button.configure(
            text="Signing in...",
            state="disabled",
        )

        self.update_idletasks()

        try:
            user = (
                self.auth_service
                .authenticate_password(
                    email,
                    password,
                )
            )

        except AuthenticationError as exc:
            self.status_var.set(
                str(exc)
            )

            self.signin_button.configure(
                text="Sign in",
                state="normal",
            )

            self.password_var.set("")
            self.password_entry.focus_set()

            return

        self.on_login_success(
            user
        )

    # =====================================================
    # AUTHENTICATOR
    # =====================================================

    def login_with_totp(
        self,
        code,
    ):
        email = (
            self.email_var.get().strip()
        )

        self.status_var.set("")

        if not email:
            self.status_var.set(
                "Enter your email address first."
            )

            self.totp_input.clear(
                focus=False
            )

            self.email_entry.focus_set()
            return

        self.status_var.set(
            "Verifying authenticator..."
        )

        self.update_idletasks()

        try:
            user = (
                self.auth_service
                .authenticate_totp_only(
                    email=email,
                    code=code,
                )
            )

        except AuthenticationError as exc:
            self.status_var.set(
                str(exc)
            )

            self.totp_input.clear()

            return

        self.on_login_success(
            user
        )

    # =====================================================
    # PASSWORD RECOVERY
    # =====================================================

    def open_forgot_password(self):
        ForgotPasswordDialog(
            self.master,
            self.auth_service,
        )
