import os
import time
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from dotenv import load_dotenv

from src.config.ui_settings import (
    load_appearance_mode,
    save_appearance_mode,
)
from src.ui.dashboard.dashboard_view import (
    DashboardView,
)
from src.ui.login.login_view import (
    LoginView,
)


PROJECT_ROOT = Path(__file__).resolve().parent

load_dotenv(
    PROJECT_ROOT / ".env",
    override=True,
)


class HopfanApplication:
    def __init__(self):
        ctk.set_appearance_mode(
            load_appearance_mode()
        )

        self.root = ctk.CTk()

        self.root.title(
            "HOPFAN Church Management System"
        )

        self.root.geometry(
            "1360x820"
        )

        self.root.minsize(
            1100,
            700,
        )

        # -------------------------------------------------
        # SESSION
        # -------------------------------------------------

        self.current_user = None
        self.current_view = None

        self.last_activity = (
            time.monotonic()
        )

        try:
            minutes = int(
                os.getenv(
                    "SESSION_IDLE_MINUTES",
                    "30",
                )
            )

        except ValueError:
            minutes = 30

        self.session_idle_seconds = (
            max(
                1,
                minutes,
            )
            * 60
        )

        # Check every 15 seconds.
        self.session_check_interval = (
            15_000
        )

        self.center_window()

        self.bind_activity_monitor()

        self.show_login()

        self.root.after(
            self.session_check_interval,
            self.check_session_timeout,
        )

    # =====================================================
    # WINDOW
    # =====================================================

    def center_window(self):
        self.root.update_idletasks()

        width = min(
            1360,
            self.root.winfo_screenwidth()
            - 30,
        )

        height = min(
            820,
            self.root.winfo_screenheight()
            - 70,
        )

        x = max(
            0,
            (
                self.root.winfo_screenwidth()
                - width
            )
            // 2,
        )

        y = max(
            0,
            (
                self.root.winfo_screenheight()
                - height
            )
            // 2,
        )

        self.root.geometry(
            f"{width}x{height}+{x}+{y}"
        )

    # =====================================================
    # ACTIVITY / SESSION
    # =====================================================

    def bind_activity_monitor(self):
        # Activity anywhere in HOPFAN resets
        # the inactivity timer.

        self.root.bind_all(
            "<KeyPress>",
            self.record_activity,
            add="+",
        )

        self.root.bind_all(
            "<ButtonPress>",
            self.record_activity,
            add="+",
        )

        self.root.bind_all(
            "<MouseWheel>",
            self.record_activity,
            add="+",
        )

        self.root.bind_all(
            "<Motion>",
            self.record_activity,
            add="+",
        )

    def record_activity(
        self,
        event=None,
    ):
        if self.current_user is not None:
            self.last_activity = (
                time.monotonic()
            )

    def start_session(
        self,
    ):
        self.last_activity = (
            time.monotonic()
        )

    def check_session_timeout(
        self,
    ):
        try:
            if self.current_user is not None:
                idle_seconds = (
                    time.monotonic()
                    - self.last_activity
                )

                if (
                    idle_seconds
                    >= self.session_idle_seconds
                ):
                    self.expire_session()

        finally:
            self.root.after(
                self.session_check_interval,
                self.check_session_timeout,
            )

    def expire_session(self):
        if self.current_user is None:
            return

        self.close_open_dialogs()

        self.show_login()

        self.root.after(
            150,
            lambda:
            messagebox.showinfo(
                "Session Expired",
                (
                    "You were signed out because "
                    "HOPFAN was inactive for too long.\n\n"
                    "Please sign in again."
                ),
                parent=self.root,
            ),
        )

    def close_open_dialogs(self):
        # Close member forms and other modal
        # windows when the security session expires.

        for widget in list(
            self.root.winfo_children()
        ):
            if isinstance(
                widget,
                ctk.CTkToplevel,
            ):
                try:
                    widget.destroy()
                except Exception:
                    pass

    # =====================================================
    # THEME
    # =====================================================

    def toggle_theme(self):
        current = (
            ctk.get_appearance_mode()
            .lower()
        )

        new_mode = (
            "light"
            if current == "dark"
            else "dark"
        )

        ctk.set_appearance_mode(
            new_mode
        )

        save_appearance_mode(
            new_mode
        )

        return new_mode

    # =====================================================
    # VIEW MANAGEMENT
    # =====================================================

    def clear_view(self):
        if self.current_view:
            try:
                self.current_view.destroy()
            except Exception:
                pass

        self.current_view = None

    def show_login(self):
        self.clear_view()

        self.current_user = None

        self.current_view = LoginView(
            master=self.root,
            on_login_success=self.show_dashboard,
            on_toggle_theme=self.toggle_theme,
        )

    def show_dashboard(
        self,
        user,
    ):
        self.clear_view()

        self.current_user = user

        self.start_session()

        self.current_view = DashboardView(
            master=self.root,
            user=user,
            on_logout=self.logout,
            on_toggle_theme=self.toggle_theme,
        )

    def logout(self):
        self.close_open_dialogs()
        self.show_login()

    # =====================================================
    # RUN
    # =====================================================

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    application = HopfanApplication()
    application.run()
