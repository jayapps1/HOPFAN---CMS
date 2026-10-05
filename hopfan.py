import os
import time
import logging
from src.ui.components.async_loader import AsyncLoader
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
from src.ui import theme


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
        theme.configure_typography(self.root)

        self.root.title(
            "HOPFAN Church Management System"
        )

        self.root.geometry(
            "1360x820"
        )

        self.root.minsize(
            min(1100, self.root.winfo_screenwidth()-60),
            min(640, self.root.winfo_screenheight()-100),
        )

        # -------------------------------------------------
        # SESSION
        # -------------------------------------------------

        self.current_user = None
        self.current_view = None
        self.session_loader = AsyncLoader(self.root)

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
        scale = self.root._get_window_scaling()
        area_x, area_y, area_width, area_height = theme.desktop_work_area(self.root)
        caption = max(28, self.root.winfo_rooty()-self.root.winfo_y())

        width = min(
            1360,
            int((area_width-30) / scale),
        )

        height = min(
            820,
            int((area_height-caption-30) / scale),
        )

        x = area_x + max(0, (area_width-width*scale)//2)
        y = area_y + max(0, (area_height-height*scale-caption)//2)

        self.root.minsize(min(1100, width), min(640, height))
        self.root.geometry(f"{width}x{height}+{int(x)}+{int(y)}")

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
                elif hasattr(self, 'session_loader') and hasattr(self.current_user, 'auth_revision'):
                    user=self.current_user
                    service=getattr(user, '_auth_service', None)
                    if service:
                        def checked(valid):
                            if self.current_user is user and not valid:
                                self.end_session_audit('SESSION_REVOKED')
                                self.close_open_dialogs()
                                self.show_login()
                        self.session_loader.submit('session-valid',
                            lambda:service.session_valid(user.id,user.auth_revision),checked,
                            lambda _error:checked(False))

        finally:
            self.root.after(
                self.session_check_interval,
                self.check_session_timeout,
            )

    def expire_session(self):
        if self.current_user is None:
            return

        self.end_session_audit('IDLE_EXPIRED')
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

    def end_session_audit(self,action):
        user=self.current_user
        service=getattr(user,'_auth_service',None)
        if service and hasattr(self,'session_loader'):
            self.session_loader.submit('session-end',lambda:service.record_session_end(user.id,action),
                lambda _:None,lambda error:logging.getLogger(__name__).error('Session audit failed: %s',type(error).__name__))

    def logout(self):
        self.end_session_audit('LOGOUT')
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
