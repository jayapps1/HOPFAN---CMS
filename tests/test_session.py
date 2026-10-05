"""Security session behavior without a GUI or persisted authentication."""
import unittest
from types import SimpleNamespace
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


    def test_revoked_credentials_close_current_session(self):
        app=self.app()
        service=Mock()
        user=SimpleNamespace(id='synthetic-user',auth_revision=7,_auth_service=service)
        app.current_user=user
        app.session_loader=Mock()
        app.end_session_audit=Mock()
        app.close_open_dialogs=Mock()
        app.show_login=Mock()
        with patch('hopfan.time.monotonic',return_value=101): app.check_session_timeout()
        args=app.session_loader.submit.call_args.args
        self.assertEqual(args[0],'session-valid')
        args[1]()
        service.session_valid.assert_called_once_with('synthetic-user',7)
        args[2](False)
        app.end_session_audit.assert_called_once_with('SESSION_REVOKED')
        app.close_open_dialogs.assert_called_once()
        app.show_login.assert_called_once()

    def test_stale_session_check_does_not_close_a_new_login(self):
        app=self.app()
        app.current_user=SimpleNamespace(id='old-user',auth_revision=1,_auth_service=Mock())
        app.session_loader=Mock()
        app.show_login=Mock()
        with patch('hopfan.time.monotonic',return_value=101): app.check_session_timeout()
        callback=app.session_loader.submit.call_args.args[2]
        app.current_user=object()
        callback(False)
        app.show_login.assert_not_called()

if __name__ == "__main__":
    unittest.main()
