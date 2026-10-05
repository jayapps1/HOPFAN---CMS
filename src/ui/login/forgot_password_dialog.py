import customtkinter as ctk

from src.services.auth_service import (
    PasswordRecoveryError,
)
from src.ui import theme
from src.ui.components.totp_input import TotpInput


class ForgotPasswordDialog(
    ctk.CTkToplevel
):
    def __init__(
        self,
        master,
        auth_service,
    ):
        super().__init__(
            master
        )

        self.auth_service = auth_service

        self.user_id = None

        self.email_var = ctk.StringVar()
        self.password_var = ctk.StringVar()
        self.confirm_var = ctk.StringVar()
        self.status_var = ctk.StringVar()

        self.title(
            "Recover HOPFAN Account"
        )

        self.geometry(
            "500x560"
        )

        self.resizable(
            False,
            False,
        )

        self.transient(
            master
        )

        self.grab_set()

        self.container = ctk.CTkFrame(
            self,
            fg_color=theme.BACKGROUND,
            corner_radius=0,
        )

        self.container.pack(
            fill="both",
            expand=True,
        )

        self.show_email_step()

    def clear_content(self):
        for widget in (
            self.container.winfo_children()
        ):
            widget.destroy()

        self.status_var.set("")

    def page(self):
        frame = ctk.CTkFrame(
            self.container,
            fg_color="transparent",
        )

        frame.pack(
            fill="both",
            expand=True,
            padx=48,
            pady=45,
        )

        return frame

    # -------------------------------------------------
    # EMAIL
    # -------------------------------------------------

    def show_email_step(self):
        self.clear_content()

        frame = self.page()

        ctk.CTkLabel(
            frame,
            text="Forgot your password?",
            font=(
                theme.FONT_FAMILY,
                24,
                "bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w"
        )

        ctk.CTkLabel(
            frame,
            text=(
                "Enter your account email. "
                "We will verify your identity using "
                "your authenticator app."
            ),
            font=(
                theme.FONT_FAMILY,
                11,
            ),
            text_color=theme.TEXT_MUTED,
            justify="left",
            wraplength=390,
        ).pack(
            anchor="w",
            pady=(8, 28),
        )

        entry = ctk.CTkEntry(
            frame,
            textvariable=self.email_var,
            placeholder_text="Email address",
            height=50,
            corner_radius=12,
            fg_color=theme.INPUT,
            border_color=theme.BORDER,
            text_color=theme.TEXT,
        )

        entry.pack(
            fill="x"
        )

        self._status(
            frame
        )

        ctk.CTkButton(
            frame,
            text="Continue",
            height=48,
            corner_radius=12,
            fg_color=theme.SECONDARY,
            hover_color=theme.SECONDARY_HOVER,
            command=self.start_recovery,
        ).pack(
            fill="x",
            pady=(18, 0),
        )

        entry.focus_set()

    def start_recovery(self):
        try:
            self.user_id = (
                self.auth_service
                .prepare_password_recovery(
                    self.email_var.get()
                )
            )

        except PasswordRecoveryError as exc:
            self.status_var.set(
                str(exc)
            )
            return

        self.show_totp_step()

    # -------------------------------------------------
    # TOTP
    # -------------------------------------------------

    def show_totp_step(self):
        self.clear_content()

        frame = self.page()

        ctk.CTkLabel(
            frame,
            text="Verify your identity",
            font=(
                theme.FONT_FAMILY,
                24,
                "bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w"
        )

        ctk.CTkLabel(
            frame,
            text=(
                "Enter the 6-digit code from your "
                "authenticator app."
            ),
            font=(
                theme.FONT_FAMILY,
                11,
            ),
            text_color=theme.TEXT_MUTED,
        ).pack(
            anchor="w",
            pady=(8, 30),
        )

        self.totp_input = TotpInput(
            frame,
            on_complete=self.verify_totp,
        )

        self.totp_input.pack(
            pady=(5, 10),
        )

        self._status(
            frame
        )

        ctk.CTkButton(
            frame,
            text="Back",
            fg_color="transparent",
            hover_color=theme.SURFACE_ALT,
            border_width=1,
            border_color=theme.BORDER,
            text_color=theme.TEXT,
            command=self.show_email_step,
        ).pack(
            pady=(28, 0),
        )

        self.totp_input.focus_first()

    def verify_totp(
        self,
        code,
    ):
        try:
            self.auth_service.verify_recovery_totp(
                self.user_id,
                code,
            )

        except PasswordRecoveryError as exc:
            self.status_var.set(
                str(exc)
            )

            self.totp_input.clear()
            return

        self.show_new_password_step()

    # -------------------------------------------------
    # NEW PASSWORD
    # -------------------------------------------------

    def show_new_password_step(self):
        self.clear_content()

        frame = self.page()

        ctk.CTkLabel(
            frame,
            text="Create a new password",
            font=(
                theme.FONT_FAMILY,
                24,
                "bold",
            ),
            text_color=theme.TEXT,
        ).pack(
            anchor="w"
        )

        ctk.CTkLabel(
            frame,
            text=(
                "Use at least 10 characters with "
                "uppercase, lowercase, number and "
                "special character."
            ),
            font=(
                theme.FONT_FAMILY,
                10,
            ),
            text_color=theme.TEXT_MUTED,
            justify="left",
            wraplength=390,
        ).pack(
            anchor="w",
            pady=(8, 25),
        )

        password = ctk.CTkEntry(
            frame,
            textvariable=self.password_var,
            placeholder_text="New password",
            show="•",
            height=50,
            corner_radius=12,
            fg_color=theme.INPUT,
            border_color=theme.BORDER,
        )

        password.pack(
            fill="x"
        )

        confirm = ctk.CTkEntry(
            frame,
            textvariable=self.confirm_var,
            placeholder_text="Confirm new password",
            show="•",
            height=50,
            corner_radius=12,
            fg_color=theme.INPUT,
            border_color=theme.BORDER,
        )

        confirm.pack(
            fill="x",
            pady=(14, 0),
        )

        self._status(
            frame
        )

        ctk.CTkButton(
            frame,
            text="Reset password",
            height=48,
            corner_radius=12,
            fg_color=theme.SECONDARY,
            hover_color=theme.SECONDARY_HOVER,
            command=self.save_password,
        ).pack(
            fill="x",
            pady=(18, 0),
        )

        password.focus_set()

    def save_password(self):
        password = (
            self.password_var.get()
        )

        confirmation = (
            self.confirm_var.get()
        )

        if password != confirmation:
            self.status_var.set(
                "The passwords do not match."
            )
            return

        try:
            self.auth_service.reset_password(
                self.user_id,
                password,
            )

        except PasswordRecoveryError as exc:
            self.status_var.set(
                str(exc)
            )
            return

        self.clear_content()

        frame = self.page()

        ctk.CTkLabel(
            frame,
            text="Password updated",
            font=(
                theme.FONT_FAMILY,
                24,
                "bold",
            ),
            text_color=theme.SUCCESS,
        ).pack(
            pady=(70, 10),
        )

        ctk.CTkLabel(
            frame,
            text=(
                "Your password has been changed "
                "successfully. You can now sign in."
            ),
            font=(
                theme.FONT_FAMILY,
                11,
            ),
            text_color=theme.TEXT,
            wraplength=350,
        ).pack()

        ctk.CTkButton(
            frame,
            text="Return to sign in",
            height=48,
            corner_radius=12,
            command=self.destroy,
        ).pack(
            fill="x",
            pady=(30, 0),
        )

    def _status(
        self,
        parent,
    ):
        ctk.CTkLabel(
            parent,
            textvariable=self.status_var,
            font=(
                theme.FONT_FAMILY,
                9,
            ),
            text_color=theme.DANGER,
            justify="left",
            wraplength=390,
        ).pack(
            anchor="w",
            pady=(15, 0),
        )
