"""Responsive sign-in using the shared HOPFAN visual system."""
from pathlib import Path
import customtkinter as ctk
from PIL import Image
from src.services.auth_service import AuthService, AuthenticationError
from src.ui import theme
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.modern import ActionButton, AppCard, ModernEntry, font, label
from src.ui.components.totp_input import TotpInput
from src.ui.icons import icon
from src.ui.login.forgot_password_dialog import ForgotPasswordDialog


class LoginView(ctk.CTkFrame):
    def __init__(self, master, on_login_success, on_toggle_theme):
        super().__init__(master, fg_color=theme.BACKGROUND, corner_radius=0)
        self.on_login_success, self.on_toggle_theme = on_login_success, on_toggle_theme
        self.auth_service = AuthService()
        self.loader = AsyncLoader(self)
        self.email_var = ctk.StringVar(master=self)
        self.password_var = ctk.StringVar(master=self)
        self.status_var = ctk.StringVar(master=self)
        self.login_method, self.password_visible, self.busy = 'password', False, False
        self.pack(fill='both', expand=True)
        self.grid_columnconfigure(0, weight=4, uniform='panels')
        self.grid_columnconfigure(1, weight=6, uniform='panels')
        self.grid_rowconfigure(0, weight=1)
        brand = ctk.CTkFrame(self, fg_color=theme.SIDEBAR, corner_radius=0)
        brand.grid(row=0, column=0, sticky='nsew')
        brand.grid_columnconfigure(0, weight=1)
        brand.grid_rowconfigure(1, weight=1)
        identity = ctk.CTkFrame(brand, fg_color='transparent')
        identity.grid(row=0, column=0, sticky='ew', padx=32, pady=24)
        logo_path = Path(__file__).resolve().parents[3] / 'assets' / 'logo' / 'hopfan_logo_clean.png'
        try:
            with Image.open(logo_path) as source:
                self.logo_image = ctk.CTkImage(light_image=source.copy(), dark_image=source.copy(), size=(64, 64))
            ctk.CTkLabel(identity, text='', image=self.logo_image).pack(side='left', padx=(0, 16))
        except OSError:
            self.logo_image = None
        ctk.CTkLabel(identity, text='HOPFAN', text_color='#FFFFFF', font=font(27, True), anchor='w').pack(side='left')
        message = ctk.CTkFrame(brand, fg_color='transparent')
        message.grid(row=1, column=0, sticky='ew', padx=32)
        ctk.CTkLabel(message, text='A connected church.\nA cared-for community.', font=font(30, True),
            text_color='#FFFFFF', anchor='w', justify='left', wraplength=330).pack(fill='x')
        ctk.CTkLabel(message, text='Members, ministry and attendance\nin one trusted workspace.', font=font(14),
            text_color=theme.SIDEBAR_MUTED, anchor='w', justify='left').pack(fill='x', pady=(16, 0))
        ctk.CTkLabel(brand, text='HOUSE OF PRAYER FOR ALL NATIONS', font=font(10, True),
            text_color=theme.SIDEBAR_MUTED, anchor='w').grid(row=2, column=0, sticky='ew', padx=32, pady=24)
        self.login_panel = ctk.CTkFrame(self, fg_color=theme.BACKGROUND, corner_radius=0)
        self.login_panel.grid(row=0, column=1, sticky='nsew')
        self.theme_button = ActionButton(self.login_panel, 'Dark mode' if ctk.get_appearance_mode() == 'Light' else 'Light mode', self.change_theme, width=105)
        self.theme_button.place(relx=1, x=-24, y=16, anchor='ne')
        self.card = AppCard(self.login_panel, width=470, height=510)
        self.card.place(relx=.5, rely=.54, anchor='center')
        self.card.grid_columnconfigure(0, weight=1)
        self.card.grid_rowconfigure(2, weight=1)
        self.card.grid_propagate(False)
        header = ctk.CTkFrame(self.card, fg_color='transparent')
        header.grid(row=0, column=0, sticky='ew', padx=24, pady=(20, 12))
        label(header, 'Welcome back', 26, True).pack(anchor='w')
        label(header, 'Sign in to your HOPFAN workspace.', 12, muted=True).pack(anchor='w', pady=(4,0))
        self.selector = ctk.CTkSegmentedButton(self.card, values=['Password', 'Authenticator'], font=font(13, True),
            command=lambda value: self.show_password_form() if value == 'Password' else self.show_totp_form(),
            fg_color=theme.SURFACE_ALT, corner_radius=8,
            selected_color=("#DDECF7", "#245477"), selected_hover_color=("#C8E0F2", "#2C638E"),
            unselected_color=theme.SURFACE_ALT, unselected_hover_color=theme.BORDER, text_color=theme.TEXT)
        self.selector.grid(row=1, column=0, sticky='ew', padx=24, pady=(0, 10))
        self.selector.set('Password')
        self.content = ctk.CTkScrollableFrame(self.card, fg_color='transparent', corner_radius=0)
        self.content.grid(row=2, column=0, sticky='nsew', padx=18)
        self.footer = ctk.CTkFrame(self.card, fg_color='transparent')
        self.footer.grid(row=3, column=0, sticky='ew', padx=24, pady=(8, 20))
        self.status_label = ctk.CTkLabel(self.footer, textvariable=self.status_var, font=font(12),
                                       text_color=theme.DANGER, wraplength=390)
        self.status_label.pack(fill='x', pady=(0, 4))
        self.signin_button = ActionButton(self.footer, 'Sign in', self.login_with_password, 'primary')
        self.signin_button.pack(fill='x')
        self.login_panel.bind('<Configure>', self.resize_card)
        self.show_password_form()
        self.enter_binding = master.bind('<Return>', self.handle_enter, add='+')

    def resize_card(self, event):
        scale = self._get_widget_scaling()
        width, height = event.width/scale, event.height/scale
        self.card.configure(width=min(470, max(360, width-48)), height=min(510, max(340, height-88)))

    def change_theme(self):
        self.on_toggle_theme()
        self.theme_button.configure(text='Dark mode' if ctk.get_appearance_mode() == 'Light' else 'Light mode')

    def clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.status_var.set('')
        label(self.content, 'Email address', 12, True).pack(anchor='w', padx=6, pady=(8,4))
        self.email_entry = ModernEntry(self.content, textvariable=self.email_var, placeholder_text='you@example.com')
        self.email_entry.pack(fill='x', padx=6)

    def show_password_form(self):
        if self.busy:
            return
        self.login_method = 'password'
        self.selector.set('Password')
        self.clear_content()
        label(self.content, 'Password', 12, True).pack(anchor='w', padx=6, pady=(16,4))
        row = ctk.CTkFrame(self.content, fg_color='transparent')
        row.pack(fill='x', padx=6)
        self.password_entry = ModernEntry(row, textvariable=self.password_var, show='•')
        self.password_entry.pack(side='left', fill='x', expand=True)
        self.password_visible = False
        self.password_button = ActionButton(row, '', self.toggle_password, width=36, image=icon('eye', 18))
        self.password_button.pack(side='right', padx=(6,0))
        ActionButton(self.content, 'Forgot password?', self.open_forgot_password, width=150).pack(anchor='e', padx=6, pady=12)
        self.signin_button.configure(text='Sign in', state='normal')
        self.signin_button.pack(fill='x')

    def show_totp_form(self):
        if self.busy:
            return
        self.login_method = 'totp'
        self.selector.set('Authenticator')
        self.clear_content()
        label(self.content, 'Authenticator code', 12, True).pack(anchor='w', padx=6, pady=(16,8))
        self.totp_input = TotpInput(self.content, on_complete=self.login_with_totp)
        self.totp_input.pack(anchor='center', pady=(0, 12))
        label(self.content, 'Enter the six-digit code from your authenticator app.\nVerification starts automatically.',
              12, muted=True, wraplength=370, justify='left').pack(anchor='w', padx=6)
        self.signin_button.pack_forget()

    def toggle_password(self):
        self.password_visible = not self.password_visible
        self.password_entry.configure(show='' if self.password_visible else '•')
        self.password_button.configure(image=icon('eye_off' if self.password_visible else 'eye', 18))

    def handle_enter(self, _event=None):
        if self.login_method == 'password':
            self.login_with_password()

    def authenticate(self, operation):
        if self.busy:
            return
        self.busy = True
        self.selector.configure(state='disabled')
        self.status_var.set('Signing in…')
        self.signin_button.configure(state='disabled', text='Signing in…')
        self.loader.submit('authentication', operation, self.signed_in, self.failed)

    def login_with_password(self):
        email, password = self.email_var.get().strip(), self.password_var.get()
        if not email or not password:
            self.status_var.set('Enter your email address and password.')
            return
        self.authenticate(lambda: self.auth_service.authenticate_password(email, password))

    def login_with_totp(self, code):
        email = self.email_var.get().strip()
        if not email:
            self.status_var.set('Enter your email address first.')
            self.totp_input.clear(focus=False)
            self.email_entry.focus_set()
            return
        self.authenticate(lambda: self.auth_service.authenticate_totp_only(email=email, code=code))

    def signed_in(self, user):
        self.busy = False
        self.selector.configure(state='normal')
        self.status_var.set('')
        self.on_login_success(user)

    def failed(self, error):
        self.busy = False
        self.selector.configure(state='normal')
        self.status_var.set(str(error) if isinstance(error, AuthenticationError) else 'Unable to sign in. Please retry.')
        self.signin_button.configure(state='normal', text='Sign in')
        if self.login_method == 'totp':
            self.totp_input.clear()
        else:
            self.password_var.set('')

    def open_forgot_password(self):
        ForgotPasswordDialog(self.winfo_toplevel(), self.auth_service)

    def destroy(self):
        self.loader.close()
        if self.enter_binding:
            self.master.unbind('<Return>', self.enter_binding)
        super().destroy()
