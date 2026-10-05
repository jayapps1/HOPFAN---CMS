"""Compact session rows shared by dashboards and attendance."""
import customtkinter as ctk
from src.ui.components.date_picker import display_date
from src.ui.components.modern import ActionButton, AppCard, StatusBadge, label


class SessionRow(AppCard):
    def __init__(self, master, session, on_open):
        super().__init__(master)
        self.grid_columnconfigure(1, weight=1)
        label(self, display_date(session['session_date']), 11, True).grid(row=0, column=0, rowspan=3, padx=12)
        label(self, session['title'], 14, True, anchor='w', wraplength=240).grid(row=0, column=1, sticky='ew', pady=(10, 0))
        created = session.get('created_at')
        timestamp = created.astimezone().strftime('%d/%m/%Y %H:%M') if created else ''
        detail = f"{session['session_type'].replace('_', ' ').title()} · {session['ministry_name']}"
        label(self, detail, 11, muted=True, anchor='w', wraplength=240).grid(row=1, column=1, sticky='ew')
        label(self, f"Created by {session['created_by']}  {timestamp}", 11, muted=True, anchor='w', wraplength=240
        ).grid(row=2, column=1, sticky='ew', pady=(0, 10))
        stats = session['stats']
        totals = ctk.CTkFrame(self, fg_color='transparent')
        totals.grid(row=0, column=2, rowspan=3, padx=12)
        label(totals, f"{stats['PRESENT']} present · {stats['LATE']} late", 11).pack()
        label(totals, f"{stats['ABSENT']} absent · {stats['rate']:g}%", 11, muted=True).pack()
        StatusBadge(self, session['state']).grid(row=0, column=3, rowspan=3, padx=8)
        self.open_button = ActionButton(self, 'View', lambda: on_open(session['id']), width=65)
        self.open_button.grid(row=0, column=4, rowspan=3, padx=(0, 12))
