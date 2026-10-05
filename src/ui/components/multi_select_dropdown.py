"""Searchable multi-select with stable IDs and clickable checked rows."""
from src.ui.components.modern_select import ModernSelect


class MultiSelectDropdown(ModernSelect):
    multiple = True

    def __init__(self, master, options=(), selected_ids=(), command=None,
                 placeholder='Select ministries', search_label='ministries', **kwargs):
        self.options = []
        self.selected_ids = set(str(value) for value in selected_ids)
        super().__init__(master, values=[], command=command, placeholder=placeholder,
                         search_label=search_label, **kwargs)
        self.set_options(options)

    def set_options(self, options):
        self.options = list({str(item['id']): dict(item, id=str(item['id'])) for item in options}.values())
        self.values = [item['name'] for item in self.options]
        self.update_summary()

    def get_selected_ids(self):
        ordered = [item['id'] for item in self.options if item['id'] in self.selected_ids]
        return ordered+sorted(self.selected_ids-set(ordered))

    def get_selected_names(self):
        return [item['name'] for item in self.options if item['id'] in self.selected_ids]

    def set_selected_ids(self, ids, notify=False):
        self.selected_ids = set(str(value) for value in ids)
        self.update_summary()
        if notify:
            self.notify(self.get_selected_ids())

    def get(self):
        return self.get_selected_ids()

    def update_summary(self):
        names = self.get_selected_names()
        text = ', '.join(names) if len(names) <= 2 and len(', '.join(names)) < 48 else f'{len(self.selected_ids)} {self.search_label} selected'
        self.variable.set(text if names else f'{len(self.selected_ids)} {self.search_label} selected' if self.selected_ids else '')

    def popup_options(self, search=''):
        return [(item['id'], item['name']) for item in self.options if search.casefold() in item['name'].casefold()]

    def is_selected(self, key):
        return key in self.selected_ids

    def pick(self, key):
        self.selected_ids.symmetric_difference_update({str(key)})
        self.update_summary()
        self.notify(self.get_selected_ids())
