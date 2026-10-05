"""Verified first-login password change and user-owned authenticator enrollment."""
import customtkinter as ctk
from src.ui.administration.dialogs import AdminDialog, details, heading
from src.ui.components.modern import ActionButton, label
from src.ui.components.totp_input import TotpInput
from src.services.auth_service import AuthenticationError


class InitialPasswordDialog(AdminDialog):
    def __init__(self,master,auth_service,user,on_signed_in):
        super().__init__(master,'Change temporary password','Create your own password before opening HOPFAN.',width=600,height=510)
        self.auth_service,self.user,self.on_signed_in=auth_service,user,on_signed_in
        self.password=self.entry('New password *',secret=True)
        self.confirm=self.entry('Confirm new password *',secret=True)
        details(self.content,'Use 10+ characters with uppercase, lowercase, a number and a special character. Choose a password different from the temporary password.')
        self.save_button=ActionButton(self.footer,'Save and sign in',self.save,'primary',width=165)
        self.save_button.pack(side='right',padx=18,pady=14)

    def save(self):
        password,confirm=self.password.get(),self.confirm.get()
        ticket=self.user._authentication_ticket
        def saved(user):
            self.password.delete(0,'end'); self.confirm.delete(0,'end')
            self.destroy(); self.on_signed_in(user)
        self.request(lambda:self.auth_service.change_initial_password(self.user.id,password,confirm,ticket),saved,self.save_button)


class AuthenticatorSetupDialog(AdminDialog):
    def __init__(self,master,auth_service,user,on_enrolled=None):
        super().__init__(master,'My authenticator','Enroll an authenticator for your own account.',width=650,height=690)
        self.auth_service,self.user,self.on_enrolled=auth_service,user,on_enrolled
        self.secret,self.ticket=None,None
        details(self.content,'Verify your own account with your password before setting up authenticator sign-in. Your password and authenticator remain separate sign-in choices.')
        self.password=self.entry('Current password *',secret=True)
        self.save_button=ActionButton(self.footer,'Continue',self.verify,'primary',width=120)
        self.save_button.pack(side='right',padx=18,pady=14)

    def verify(self):
        password=self.password.get()
        def verified(user):
            self.password.delete(0,'end')
            if user.id!=self.user.id:
                self.error_var.set('Verify your own account.'); return
            self.ticket=user._authentication_ticket
            self.request(lambda:self.auth_service.create_totp_enrollment(user.id,self.ticket),self.enrollment_ready,self.save_button)
        self.request(lambda:self.auth_service.authenticate_password(self.user.email or self.user.username,password),verified,self.save_button)

    def enrollment_ready(self,result):
        self.secret,uri=result
        for w in self.content.winfo_children(): w.destroy()
        heading(self.content,'Scan this QR code in your authenticator app')
        source=self.auth_service.totp.qr_image(uri)
        self.qr=ctk.CTkImage(light_image=source,dark_image=source,size=(230,230))
        label(self.content,'',image=self.qr).pack(pady=12)
        details(self.content,'Setup key: '+self.secret)
        details(self.content,'Keep this setup key private. Enter a code from the newly configured authenticator to finish.')
        self.code=TotpInput(self.content,on_complete=self.confirm_enrollment)
        self.code.pack(pady=10)
        self.save_button.pack_forget()

    def confirm_enrollment(self,code):
        def saved(user):
            self.secret=None
            if self.on_enrolled: self.on_enrolled(user)
            self.destroy()
        self.request(lambda:self.auth_service.confirm_totp_enrollment(self.user.id,self.secret,code,self.ticket),saved)

    def destroy(self):
        if self.ticket:
            self.auth_service.cancel_totp_enrollment(self.user.id,self.ticket)
        self.secret=None
        super().destroy()
