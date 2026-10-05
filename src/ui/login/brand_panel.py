"""Official HOPFAN identity for the desktop sign-in page."""
from pathlib import Path
import customtkinter as ctk
from PIL import Image
from src.ui import theme
from src.ui.components.modern import font


class BrandPanel(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=theme.SIDEBAR, corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        content = ctk.CTkFrame(self, fg_color='transparent')
        content.grid(row=0, column=0, sticky='ew', padx=32, pady=32)
        identity = ctk.CTkFrame(content, fg_color='transparent')
        identity.pack(fill='x', pady=(0,32))
        logo_path = Path(__file__).resolve().parents[3]/'assets/logo/hopfan_logo_clean.png'
        try:
            with Image.open(logo_path) as source:
                self.logo_image = ctk.CTkImage(light_image=source.copy(), dark_image=source.copy(), size=(72,72))
            ctk.CTkLabel(identity, text='', image=self.logo_image).pack(side='left', padx=(0,14))
        except OSError:
            self.logo_image = None
        ctk.CTkLabel(identity, text='HOPFAN', text_color='#FFFFFF', font=font(26,True)).pack(side='left')
        self.church_name = ctk.CTkLabel(content, text='HOUSE OF PRAYER\nFOR ALL NATIONS', font=font(15,True),
            text_color=theme.SIDEBAR_MUTED, anchor='w', justify='left')
        self.church_name.pack(fill='x')
        self.title_label = ctk.CTkLabel(content, text='Church Management\nSystem', font=font(30,True),
            text_color='#FFFFFF', anchor='w', justify='left')
        self.title_label.pack(fill='x', pady=(12,18))
        ctk.CTkFrame(content, width=44, height=3, fg_color=theme.GREEN, corner_radius=1).pack(anchor='w')
        self.support_label = ctk.CTkLabel(content, text='Care for your members. Connect your ministries.\nKeep every church record in one trusted place.',
            font=font(13), text_color=theme.SIDEBAR_MUTED, anchor='w', justify='left', wraplength=320)
        self.support_label.pack(fill='x', pady=(18,0))
        content.bind('<Configure>', lambda event:self.support_label.configure(wraplength=max(160,event.width/self._get_widget_scaling())))
        ctk.CTkLabel(self, text='Secure  ·  Centralized  ·  Accountable', font=font(11),
            text_color=theme.SIDEBAR_MUTED, anchor='w').grid(row=1, column=0, sticky='ew', padx=32, pady=24)
