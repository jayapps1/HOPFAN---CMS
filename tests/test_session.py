"""Security session behavior without a GUI or persisted authentication."""
import unittest
from unittest.mock import Mock, patch

from hopfan import HopfanApplication


class SessionTests(unittest.TestCase):
    def app(self):
        app = HopfanApplication.__new__(HopfanApplication)
        app.current_user = object()
        app.last_activity = 100
        app.session_idle_seconds = 1800
        app.session_check_interval = 15000
        app.root = Mock()
        app.expire_session = Mock()
        return app

    def test_active_actions_extend_session(self):
        app = self.app()
        with patch("hopfan.time.monotonic", return_value=1900):
            app.record_activity()
        with patch("hopfan.time.monotonic", return_value=1901):
            app.check_session_timeout()
        app.expire_session.assert_not_called()
        self.assertEqual(app.last_activity, 1900)
        app.root.after.assert_called_once_with(15000, app.check_session_timeout)

    def test_idle_expiry_remains_enforced(self):
        app = self.app()
        with patch("hopfan.time.monotonic", return_value=1900):
            app.check_session_timeout()
        app.expire_session.assert_called_once()

    def test_login_screen_does_not_create_an_authenticated_session(self):
        app = self.app()
        app.clear_view = Mock()
        with patch("hopfan.LoginView") as login:
            app.show_login()
        self.assertIsNone(app.current_user)
        login.assert_called_once()


if __name__ == "__main__":
    unittest.main()
