"""Modern single-select input. Programmatic set does not invoke the command."""
import customtkinter as ctk
from src.ui import theme
from src.ui.icons import icon
from src.ui.components.select_popup import SelectPopup


class ModernSelect(ctk.CTkFrame):
    multiple = False

    def __init__(self, master, values, variable=None, command=None, width=180, height=46,
                 placeholder='Select an option', state='readonly', search_label='options', **kwargs):
        super().__init__(master, width=width, height=height, corner_radius=11, border_width=1,
                         fg_color=theme.INPUT, border_color=theme.BORDER, **kwargs)
        self.values = list(dict.fromkeys(str(value) for value in values))
        self.variable = variable if variable is not None else ctk.StringVar(master=self, value=self.values[0] if self.values else '')
        self.command, self.placeholder, self.search_label = command, placeholder, search_label
        self.state, self.popup = state, None
        self.destroying = False
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_propagate(False)
        self.value_label = ctk.CTkLabel(self, text='', width=1, anchor='w',
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=13), text_color=theme.TEXT)
        self.value_label.grid(row=0, column=0, sticky='ew', padx=(12, 4))
        self.chevron = ctk.CTkLabel(self, text='', image=icon('chevron_down', 16), width=18)
        self.chevron.grid(row=0, column=1, padx=(4, 12))
        self._canvas.configure(takefocus=1)
        for widget in (self, self.value_label, self.chevron):
            widget.bind('<Button-1>', self.toggle_popup, add='+')
            widget.bind('<Enter>', self.hover, add='+')
            widget.bind('<Leave>', self.leave, add='+')
        self.bind('<FocusIn>', lambda _e: self.configure(border_color=theme.FOCUS_BORDER), add='+')
        self.bind('<FocusOut>', lambda _e: self.configure(border_color=theme.BORDER), add='+')
        for key in ('<space>', '<Return>', '<Down>', '<Alt-Down>'):
            self.bind(key, self.open_popup, add='+')
        self.bind('<Escape>', lambda _e: self.close_popup(), add='+')
        self.variable_trace = self.variable.trace_add('write', lambda *_: self.render_value())
        self.render_value()

    def get(self):
        return self.variable.get()

    def set(self, value):
        self.variable.set(str(value))

    def notify(self, value):
        if self.command:
            self.command(value)

    def render_value(self):
        if self.destroying:
            return
        disabled = self.state == 'disabled'
        self.value_label.configure(text=self.variable.get() or self.placeholder,
            text_color=theme.TEXT_MUTED if disabled or not self.variable.get() else theme.TEXT)
        super().configure(fg_color=theme.DISABLED_INPUT if disabled else theme.INPUT)
        if disabled:
            super().configure(border_color=theme.BORDER)
        self._canvas.configure(takefocus=0 if disabled else 1)

    def popup_options(self, search=''):
        return [(value, value) for value in self.values if search.casefold() in value.casefold()]

    def is_selected(self, key):
        return key == self.get()

    def open_popup(self, _event=None):
        if self.state != 'disabled' and self.popup is None and (self.values or self.multiple):
            self.focus_set()
            self.popup = SelectPopup(self)
        return 'break'

    def toggle_popup(self, _event=None):
        if self.popup:
            self.close_popup()
        else:
            self.open_popup()
        return 'break'

    def close_popup(self):
        if self.popup:
            self.popup.close()
        return 'break'

    def focus_set(self):
        if self.state != 'disabled':
            self._canvas.focus_set()

    def hover(self, _event):
        if self.state != 'disabled':
            super().configure(border_color=theme.FOCUS_BORDER)

    def leave(self, _event):
        super().configure(border_color=theme.FOCUS_BORDER if self.focus_get()==self._canvas else theme.BORDER)

    def configure(self, require_redraw=False, **kwargs):
        if not hasattr(self, 'state'):
            return super().configure(require_redraw=require_redraw, **kwargs)
        if 'values' in kwargs:
            self.values = list(dict.fromkeys(str(value) for value in kwargs.pop('values')))
        if 'command' in kwargs:
            self.command = kwargs.pop('command')
        if 'state' in kwargs:
            self.state = kwargs.pop('state')
            if self.state == 'disabled':
                self.close_popup()
        result = super().configure(require_redraw=require_redraw, **kwargs)
        self.render_value()
        return result

    def cget(self, name):
        if name == 'state':
            return self.state
        if name == 'values':
            return self.values
        return super().cget(name)

    def destroy(self):
        self.destroying = True
        if self.popup:
            self.popup.close(restore_focus=False)
        self.variable.trace_remove('write', self.variable_trace)
        super().destroy()
