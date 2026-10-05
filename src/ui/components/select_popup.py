"""Bounded, keyboard-accessible select popover with modal-grab restoration."""
import customtkinter as ctk
from src.ui import theme
from src.ui.icons import icon


class SelectPopup(ctk.CTkToplevel):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.previous_grab = owner.grab_current()
        self.closed = False
        self.activation_timer = None
        self.focus_timer = None
        self.rows, self.keys = {}, []
        self.active_index = 0
        self.withdraw()
        self.overrideredirect(True)
        self.transient(owner.winfo_toplevel())
        self.configure(fg_color=theme.SURFACE)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        surface = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=10,
                               border_width=1, border_color=theme.BORDER)
        surface.grid(row=0, column=0, sticky='nsew')
        surface.grid_columnconfigure(0, weight=1)
        surface.grid_rowconfigure(1, weight=1)
        self.search_variable = ctk.StringVar(master=self)
        self.search = ctk.CTkEntry(surface, textvariable=self.search_variable,
            height=36, corner_radius=8, fg_color=theme.INPUT, border_color=theme.BORDER,
            text_color=theme.TEXT, placeholder_text_color=theme.TEXT_MUTED,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=12))
        self.search_hint = ctk.CTkLabel(self.search, text='Search '+owner.search_label+'…',
            text_color=theme.TEXT_MUTED, fg_color=theme.INPUT, anchor='w', height=20,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=12))
        self.search_hint.bind('<Button-1>', lambda _event:self.search.focus_set())
        self.search_trace = self.search_variable.trace_add('write', self.update_search_hint)
        self.update_search_hint()
        self.searchable = owner.multiple or len(owner.values) > 7
        if self.searchable:
            self.search.grid(row=0, column=0, sticky='ew', padx=8, pady=(8, 4))
            self.search.bind('<KeyRelease>', self.filter_changed)
        self.list_frame = ctk.CTkScrollableFrame(surface, fg_color='transparent', corner_radius=0,
            scrollbar_button_color=theme.BORDER, scrollbar_button_hover_color=theme.TEXT_FAINT)
        self.list_frame.grid(row=1, column=0, sticky='nsew', padx=6, pady=6)
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.hint = ctk.CTkLabel(surface, text='Escape to close',
            text_color=theme.TEXT_MUTED, font=ctk.CTkFont(family=theme.FONT_FAMILY, size=11), height=20)
        self.hint.grid(row=2, column=0, sticky='ew', padx=8, pady=(0, 6))
        self.render()
        self.position()
        self.bind('<Escape>', lambda _event: self.close())
        self.bind('<Down>', lambda event: self.move(1))
        self.bind('<Up>', lambda event: self.move(-1))
        self.bind('<Return>', lambda event: self.pick_active())
        self.bind('<space>', self.space_pressed)
        self.bind('<ButtonPress-1>', self.outside_click, add='+')
        self.bind('<FocusOut>', self.focus_left, add='+')
        self.deiconify()
        self.lift()
        self.activation_timer = self.after(20, self.activate)

    def position(self):
        self.owner.update_idletasks()
        scale = self._get_window_scaling()
        left, top, work_width, work_height = theme.desktop_work_area(self.owner)
        margin = 8
        width = min(self.owner.winfo_width(), work_width-2*margin)
        desired_height = min(330, 36*max(1, min(len(self.keys), 8))+42+(44 if self.searchable else 0))*scale
        below = top+work_height-(self.owner.winfo_rooty()+self.owner.winfo_height())-margin
        above = self.owner.winfo_rooty()-top-margin
        open_below = below >= desired_height or below >= above
        height = min(desired_height, below if open_below else above)
        height = max(80, int(height))
        x = max(left+margin, min(self.owner.winfo_rootx(), left+work_width-width-margin))
        y = self.owner.winfo_rooty()+self.owner.winfo_height()+4 if open_below else self.owner.winfo_rooty()-height-4
        y = max(top+margin, min(y, top+work_height-height-margin))
        self.geometry(f'{int(width/scale)}x{int(height/scale)}+{int(x)}+{int(y)}')

    def update_search_hint(self, *_args):
        if self.search_variable.get():
            self.search_hint.place_forget()
        else:
            self.search_hint.place(x=8,rely=.5,anchor='w')

    def activate(self):
        self.activation_timer = None
        if not self.closed:
            self.grab_set()
            if self.searchable:
                self.search.focus_set()
            elif self.keys:
                self.rows[self.keys[self.active_index]].focus_set()

    def render(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        self.rows = {}
        options = self.owner.popup_options(self.search.get() if self.searchable else '')
        self.keys = [key for key, _ in options]
        self.active_index = min(self.active_index, max(0, len(self.keys)-1))
        for index, (key, text) in enumerate(options):
            button = ctk.CTkButton(self.list_frame, text=text, anchor='w', height=34,
                corner_radius=7, border_width=0, font=ctk.CTkFont(family=theme.FONT_FAMILY, size=12),
                fg_color='transparent', hover_color=theme.SURFACE_ALT, text_color=theme.TEXT,
                image=icon('check' if self.owner.is_selected(key) else 'blank', 16),
                command=lambda value=key: self.choose(value))
            button.grid(row=index, column=0, sticky='ew', pady=2)
            self.rows[key] = button
        if not options:
            ctk.CTkLabel(self.list_frame, text='No matching options', text_color=theme.TEXT_MUTED,
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=12)).grid(sticky='ew', pady=20)
        self.style_rows()

    def style_rows(self):
        for index, key in enumerate(self.keys):
            selected = self.owner.is_selected(key)
            self.rows[key].configure(image=icon('check' if selected else 'blank', 16),
                fg_color=theme.SELECTED_SURFACE if selected else theme.SURFACE_ALT if index == self.active_index else 'transparent')

    def filter_changed(self, event=None):
        if event and event.keysym in {'Up', 'Down', 'Return', 'Escape'}:
            return
        self.active_index = 0
        self.render()
        self.list_frame._parent_canvas.yview_moveto(0)

    def move(self, direction):
        if self.keys:
            self.active_index = (self.active_index+direction) % len(self.keys)
            self.style_rows()
            button = self.rows[self.keys[self.active_index]]
            self.update_idletasks()
            canvas = self.list_frame._parent_canvas
            bounds = canvas.bbox('all')
            if bounds:
                y = button.winfo_y()
                canvas.yview_moveto(max(0, (y-canvas.winfo_height()/2)/max(1, bounds[3])))
        return 'break'

    def pick_active(self):
        if self.keys:
            self.choose(self.keys[self.active_index])
        return 'break'

    def space_pressed(self, event):
        if event.widget == self.search._entry:
            return None
        return self.pick_active()

    def choose(self, key):
        if self.owner.multiple:
            self.owner.pick(key)
            if not self.closed:
                self.style_rows()
        else:
            owner = self.owner
            owner.set(key)
            self.close()
            owner.notify(key)

    def outside_click(self, event):
        if not (self.winfo_rootx() <= event.x_root < self.winfo_rootx()+self.winfo_width()
                and self.winfo_rooty() <= event.y_root < self.winfo_rooty()+self.winfo_height()):
            self.close()
            return 'break'

    def focus_left(self, _event):
        if not self.closed and self.focus_timer is None:
            self.focus_timer = self.after_idle(self.check_focus)

    def check_focus(self):
        self.focus_timer = None
        if self.closed:
            return
        focused = self.focus_displayof()
        if focused is None or focused.winfo_toplevel() != self:
            self.close(restore_focus=False)

    def close(self, restore_focus=True):
        if self.closed:
            return
        self.closed = True
        if self.activation_timer is not None:
            self.after_cancel(self.activation_timer)
        if self.focus_timer is not None:
            self.after_cancel(self.focus_timer)
        if self.grab_current() == self:
            self.grab_release()
        self.owner.popup = None
        self.search_variable.trace_remove('write', self.search_trace)
        super().destroy()
        if self.previous_grab is not None and self.previous_grab.winfo_exists():
            self.previous_grab.grab_set()
        if restore_focus and self.owner.winfo_exists():
            self.owner.focus_set()

    def destroy(self):
        self.close(restore_focus=False)
