"""An input with an icon, optional action and a placeholder for bound variables."""
import customtkinter as ctk
from src.ui import theme
from src.ui.components.modern import font
from src.ui.icons import icon


class IconEntry(ctk.CTkFrame):
    def __init__(self, master, variable, icon_name, placeholder='', show='', action=None, action_icon='eye'):
        super().__init__(master, height=48, corner_radius=12, border_width=1,
            border_color=theme.BORDER, fg_color=theme.INPUT)
        self.variable = variable
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_propagate(False)
        ctk.CTkLabel(self, text='', image=icon(icon_name, 20), width=24).grid(row=0, column=0, padx=(12,6))
        self.entry = ctk.CTkEntry(self, textvariable=variable, show=show, height=42,
            corner_radius=0, border_width=0, fg_color=theme.INPUT, text_color=theme.TEXT,
            font=font(13))
        self.entry.grid(row=0, column=1, sticky='ew', padx=(0,8))
        # CTkEntry suppresses native placeholder_text when a StringVar is attached.
        self.placeholder = ctk.CTkLabel(self.entry, text=placeholder, text_color=theme.TEXT_MUTED,
            font=font(13), anchor='w', fg_color=theme.INPUT, height=22)
        self.placeholder.bind('<Button-1>', lambda _event:self.entry.focus_set())
        self.entry.bind('<FocusIn>', lambda _event:self.configure(border_color=theme.FOCUS_BORDER), add='+')
        self.entry.bind('<FocusOut>', lambda _event:self.configure(border_color=theme.BORDER), add='+')
        self.action_button = None
        if action:
            self.action_button = ctk.CTkButton(self, text='', image=icon(action_icon,20), command=action,
                width=34, height=34, corner_radius=8, fg_color='transparent', hover_color=theme.SURFACE_ALT)
            self.action_button.grid(row=0, column=2, padx=(0,8))
        self.variable_trace = variable.trace_add('write', self.render_placeholder)
        self.render_placeholder()

    def render_placeholder(self, *_args):
        if self.variable.get():
            self.placeholder.place_forget()
        else:
            self.placeholder.place(x=2, rely=.5, anchor='w')

    def destroy(self):
        self.variable.trace_remove('write', self.variable_trace)
        super().destroy()
