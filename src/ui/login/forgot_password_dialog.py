"""Fixed-footer password recovery, retaining the existing email/TOTP/reset flow."""
import customtkinter as ctk
from src.services.auth_service import PasswordRecoveryError
from src.ui.components.modern import ActionButton, FixedFooterDialog, ModernEntry, label
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.totp_input import TotpInput


class ForgotPasswordDialog(FixedFooterDialog):
    def __init__(self, master, auth_service):
        super().__init__(master, 'Recover account', 'Verify your account to create a new password.', width=580, height=560)
        self.auth_service, self.user_id = auth_service, None
        self.loader = AsyncLoader(self)
        self.email_var, self.password_var, self.confirm_var = [ctk.StringVar(master=self) for _ in range(3)]
        self.next_button = ActionButton(self.footer, 'Continue', self.start_recovery, 'primary')
        self.next_button.pack(side='right', padx=18, pady=14)
        self.show_email_step()

    def clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.error_var.set('')

    def entry(self, title, variable, secret=False):
        label(self.content, title, 12, True).pack(anchor='w', padx=16, pady=(16,4))
        entry = ModernEntry(self.content, textvariable=variable, show='•' if secret else '')
        entry.pack(fill='x', padx=16)
        return entry

    def show_email_step(self):
        self.clear_content()
        self.entry('Email address', self.email_var).focus_set()
        label(self.content, 'Use the email address registered to your account.', muted=True, wraplength=450).pack(anchor='w', padx=16, pady=16)

    def request(self, operation, success):
        self.next_button.configure(state='disabled')
        def done(result):
            self.next_button.configure(state='normal')
            success(result)
        def failed(error):
            self.next_button.configure(state='normal')
            self.error_var.set(str(error) if isinstance(error, PasswordRecoveryError) else 'Unable to recover this account. Please retry.')
            if hasattr(self, 'totp_input') and self.totp_input.winfo_exists():
                self.totp_input.clear()
        self.loader.submit('recovery', operation, done, failed)

    def start_recovery(self):
        email = self.email_var.get().strip()
        if not email:
            self.error_var.set('Enter your email address.'); return
        def ready(user_id):
            self.user_id = user_id
            self.show_totp_step()
        self.request(lambda: self.auth_service.prepare_password_recovery(email), ready)

    def show_totp_step(self):
        self.clear_content()
        label(self.content, 'Authenticator code', 17, True).pack(anchor='w', padx=16, pady=16)
        self.totp_input = TotpInput(self.content, on_complete=self.verify_totp)
        self.totp_input.pack(pady=8)
        label(self.content, 'Enter your six-digit authenticator code to verify your identity.', muted=True, wraplength=450).pack(padx=16,pady=16)
        self.next_button.pack_forget()
        self.totp_input.focus_first()

    def verify_totp(self, code):
        self.request(lambda: self.auth_service.verify_recovery_totp(self.user_id, code), lambda _: self.show_new_password_step())

    def show_new_password_step(self):
        self.clear_content()
        self.entry('New password', self.password_var, True).focus_set()
        self.entry('Confirm new password', self.confirm_var, True)
        self.next_button.configure(text='Save password', command=self.save_password)
        self.next_button.pack(side='right', padx=18, pady=14)

    def save_password(self):
        password = self.password_var.get()
        if password != self.confirm_var.get():
            self.error_var.set('The passwords do not match.'); return
        def saved(_result):
            self.clear_content()
            label(self.content, 'Password updated', 22, True).pack(pady=(32,12))
            label(self.content, 'You can now sign in with your new password.', muted=True).pack()
            self.next_button.configure(text='Return to sign in', command=self.destroy)
        self.request(lambda: self.auth_service.reset_password(self.user_id, password), saved)
