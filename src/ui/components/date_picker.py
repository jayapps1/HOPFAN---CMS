"""One date control for attendance and membership, with direct month/year selection."""
import calendar
from datetime import date, datetime

import customtkinter as ctk

from src.ui import theme
from src.ui.components.modern import ActionButton, ModernComboBox, ModernEntry, font, label


def display_date(value):
    if not value:
        return ""
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(value), pattern).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return str(value)


def parse_date(value):
    try:
        return datetime.strptime(value.strip(), "%d/%m/%Y").date()
    except (ValueError, AttributeError) as exc:
        raise ValueError("Enter a valid date as DD/MM/YYYY.") from exc


class DatePicker(ctk.CTkFrame):
    def __init__(self, master, initial_date=None, variable=None, compact=False):
        super().__init__(master, fg_color="transparent")
        self.variable = variable if variable is not None else ctk.StringVar(master=self, value=display_date(initial_date))
        self.grid_columnconfigure(0, weight=1)
        self.entry = ModernEntry(self, textvariable=self.variable, placeholder_text="DD/MM/YYYY", width=110 if compact else 140)
        self.entry.grid(row=0, column=0, sticky="ew")
        from src.ui.icons import icon
        ActionButton(self, "" if compact else "Calendar", self.open_calendar, width=32 if compact else 88,
                     image=icon("calendar", 18) if compact else None).grid(row=0, column=1, padx=(6, 0))

    def get_date(self):
        return parse_date(self.variable.get())

    def open_calendar(self):
        try:
            initial = self.get_date()
        except ValueError:
            initial = date.today()
        DatePickerDialog(self, initial, lambda selected: self.variable.set(display_date(selected)))


class DatePickerDialog(ctk.CTkToplevel):
    def __init__(self, master, initial_date=None, on_select=None):
        super().__init__(master)
        self.title("Choose date")
        self.transient(master.winfo_toplevel())
        self.configure(fg_color=theme.SURFACE)
        self.resizable(False, False)
        self.geometry("430x405")
        self.year = (initial_date or date.today()).year
        self.month = (initial_date or date.today()).month
        self.on_select = on_select
        self.parent_dialog = master.winfo_toplevel()
        self.months = list(calendar.month_name)[1:]
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=16, pady=14)
        self.month_box = ModernComboBox(toolbar, self.months, command=self.month_changed, width=180)
        self.month_box.pack(side="left")
        self.month_box.set(self.months[self.month-1])
        self.year_box = ModernComboBox(toolbar, [str(y) for y in range(1900, date.today().year+31)],
                                      command=self.year_changed, width=115)
        self.year_box.configure(state="normal")
        self.year_box.set(str(self.year))
        self.year_box.pack(side="right")
        self.year_box.bind("<Return>", lambda _e: self.year_changed(self.year_box.get()))
        self.year_box.bind("<FocusOut>", lambda _e: self.year_changed(self.year_box.get()))
        self.days = ctk.CTkFrame(self, fg_color="transparent")
        self.days.pack(fill="both", expand=True, padx=16)
        self.render_calendar()
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=12)
        ActionButton(footer, "Today", lambda: self.select(date.today()), width=100).pack(side="left")
        ActionButton(footer, "Cancel", self.destroy, width=100).pack(side="right")
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.after(60, self.grab_set)

    def month_changed(self, value):
        self.month = self.months.index(value)+1
        self.render_calendar()

    def year_changed(self, value):
        try:
            year = int(value)
            if not 1 <= year <= 9999:
                raise ValueError
        except ValueError:
            self.year_box.set(str(self.year))
            return
        self.year = year
        self.render_calendar()

    def render_calendar(self):
        for widget in self.days.winfo_children():
            widget.destroy()
        for column, day in enumerate(calendar.day_abbr):
            self.days.grid_columnconfigure(column, weight=1)
            label(self.days, day, 11, muted=True).grid(row=0, column=column, pady=5)
        for row, week in enumerate(calendar.monthcalendar(self.year, self.month), 1):
            for column, day in enumerate(week):
                if day:
                    ActionButton(self.days, str(day), lambda d=day: self.select(date(self.year, self.month, d)),
                                 width=45).grid(row=row, column=column, padx=2, pady=2, sticky="ew")

    def select(self, selected):
        if self.on_select:
            self.on_select(selected)
        self.destroy()

    def destroy(self):
        super().destroy()
        if self.parent_dialog.winfo_exists() and isinstance(self.parent_dialog, ctk.CTkToplevel):
            self.parent_dialog.grab_set()
