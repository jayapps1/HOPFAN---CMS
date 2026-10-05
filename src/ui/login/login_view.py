"""Responsive sign-in using the shared HOPFAN visual system."""
import customtkinter as ctk
from src.services.auth_service import AuthService, AuthenticationError
from src.ui import theme
from src.ui.components.async_loader import AsyncLoader
from src.ui.components.modern import ActionButton, font, label
from src.ui.components.icon_entry import IconEntry
from src.ui.components.totp_input import TotpInput
from src.ui.icons import icon
from src.ui.login.forgot_password_dialog import ForgotPasswordDialog
from src.ui.login.brand_panel import BrandPanel


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
        brand = BrandPanel(self)
        brand.grid(row=0, column=0, sticky='nsew')
        self.login_panel = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=0)
        self.login_panel.grid(row=0, column=1, sticky='nsew')
        self.login_panel.grid_columnconfigure(0, weight=1)
        self.login_panel.grid_rowconfigure(1, weight=1)
        toolbar = ctk.CTkFrame(self.login_panel, fg_color='transparent', height=52)
        toolbar.grid(row=0, column=0, sticky='ew')
        self.theme_button = ActionButton(self.login_panel, 'Dark mode' if ctk.get_appearance_mode() == 'Light' else 'Light mode', self.change_theme, width=105)
        self.theme_button.place(relx=1, x=-24, y=16, anchor='ne')
        stage = ctk.CTkFrame(self.login_panel, fg_color='transparent')
        stage.grid(row=1, column=0, sticky='nsew', padx=24, pady=(4,28))
        self.card = ctk.CTkFrame(stage, fg_color='transparent', width=420)
        self.card.place(relx=.5, rely=.5, anchor='center')
        self.card.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(self.card, fg_color='transparent')
        header.grid(row=0, column=0, sticky='ew', pady=(0,20))
        label(header, 'Welcome back', 30, True).pack(anchor='w')
        label(header, 'Sign in to your HOPFAN workspace.', 12, muted=True).pack(anchor='w', pady=(4,0))
        self.selector = ctk.CTkSegmentedButton(self.card, values=['Password', 'Authenticator'], font=font(12, True), height=38,
            command=lambda value: self.show_password_form() if value == 'Password' else self.show_totp_form(),
            fg_color=theme.SURFACE_ALT, corner_radius=10,
            selected_color=("#DDECF7", "#245477"), selected_hover_color=("#C8E0F2", "#2C638E"),
            unselected_color=theme.SURFACE_ALT, unselected_hover_color=theme.BORDER, text_color=theme.TEXT)
        self.selector.grid(row=1, column=0, sticky='ew', pady=(0,20))
        self.selector.set('Password')
        self.content = ctk.CTkFrame(self.card, fg_color='transparent', corner_radius=0)
        self.content.grid(row=2, column=0, sticky='ew')
        self.footer = ctk.CTkFrame(self.card, fg_color='transparent')
        self.footer.grid(row=3, column=0, sticky='ew', pady=(8,0))
        self.status_label = ctk.CTkLabel(self.footer, textvariable=self.status_var, font=font(12),
                                       text_color=theme.ERROR_TEXT, wraplength=390)
        self.status_label.pack(fill='x', pady=(0,6))
        self.signin_button = ActionButton(self.footer, 'Sign in', self.login_with_password, 'primary', height=48, corner_radius=12)
        self.signin_button.pack(fill='x')
        label(self.card, 'Secure church administration', 11, muted=True, image=icon('shield',16), compound='left').grid(row=4,column=0,pady=(18,0))
        stage.bind('<Configure>', self.resize_card)
        self.show_password_form()
        self.enter_binding = master.bind('<Return>', self.handle_enter, add='+')

    def resize_card(self, event):
        scale = self._get_widget_scaling()
        width = min(420, max(280,event.width/scale))
        # Tk's place_configure takes physical pixels; CTk inputs use logical ones.
        self.card.place_configure(width=round(width*scale))
        self.status_label.configure(wraplength=width)

    def change_theme(self):
        self.on_toggle_theme()
        self.theme_button.configure(text='Dark mode' if ctk.get_appearance_mode() == 'Light' else 'Light mode')

    def clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.status_var.set('')
        label(self.content, 'Email address', 11, True).pack(anchor='w', pady=(0,6))
        self.email_field = IconEntry(self.content, self.email_var, 'mail', placeholder='name@example.com')
        self.email_field.pack(fill='x')
        self.email_entry = self.email_field.entry

    def show_password_form(self):
        if self.busy:
            return
        self.login_method = 'password'
        self.selector.set('Password')
        self.clear_content()
        label(self.content, 'Password', 11, True).pack(anchor='w', pady=(18,6))
        self.password_field = IconEntry(self.content, self.password_var, 'lock', placeholder='Enter your password',
            show='•', action=self.toggle_password)
        self.password_field.pack(fill='x')
        self.password_entry = self.password_field.entry
        self.password_visible = False
        self.password_button = self.password_field.action_button
        ctk.CTkButton(self.content, text='Forgot password?', command=self.open_forgot_password, width=126,
            height=26, font=font(11,True), fg_color='transparent', hover_color=theme.SURFACE_ALT,
            text_color=theme.LINK_TEXT).pack(anchor='e', pady=(8,0))
        self.signin_button.configure(text='Sign in', state='normal')
        self.signin_button.pack(fill='x')

    def show_totp_form(self):
        if self.busy:
            return
        self.login_method = 'totp'
        self.selector.set('Authenticator')
        self.clear_content()
        label(self.content, 'Authenticator code', 11, True).pack(anchor='w', pady=(18,8))
        self.totp_input = TotpInput(self.content, on_complete=self.login_with_totp)
        self.totp_input.pack(anchor='center', pady=(0, 12))
        label(self.content, 'Enter the six-digit code from your authenticator app.\nVerification starts automatically.',
              12, muted=True, wraplength=370, justify='left').pack(anchor='w')
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
