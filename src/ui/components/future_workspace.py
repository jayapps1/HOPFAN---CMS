"""Consistent shells for modules awaiting their underlying services."""
import customtkinter as ctk
from src.ui.components.modern import AppCard, StatusBadge, label
from src.ui.icons import icon


class FutureWorkspace(ctk.CTkFrame):
    def __init__(self, master, title, image, context, features):
        super().__init__(master, fg_color='transparent')
        card = AppCard(self)
        card.pack(fill='x', padx=24, pady=8)
        ctk.CTkLabel(card, text='', image=icon(image, 40)).pack(pady=(28, 12))
        label(card, title+' workspace', 22, True).pack()
        label(card, context, muted=True, wraplength=600).pack(pady=(4, 12))
        StatusBadge(card, 'PLANNED').pack(pady=(0, 16))
        label(card, 'This module is awaiting implementation. No records or totals are available yet.',
              muted=True, wraplength=600).pack(pady=(0, 28))
        panel = AppCard(self)
        panel.pack(fill='x', padx=24, pady=16)
        label(panel, 'Planned capabilities', 16, True).pack(anchor='w', padx=20, pady=(16, 8))
        for feature in features:
            label(panel, feature, anchor='w').pack(fill='x', padx=20, pady=4)
        label(panel, 'Access follows your assigned role and ministry scope.', 12, muted=True).pack(anchor='w', padx=20, pady=16)
