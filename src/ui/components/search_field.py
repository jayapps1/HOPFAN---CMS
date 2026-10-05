"""Consistent debounced directory search with cancellation on destruction."""
from src.ui.components.modern import ModernEntry


class SearchField(ModernEntry):
    def __init__(self,master,on_search,placeholder='Search name or code',**kwargs):
        super().__init__(master,placeholder_text=placeholder,height=46,corner_radius=11,**kwargs)
        self.on_search,self.search_timer=on_search,None
        self.bind('<KeyRelease>',self.schedule)
        self.bind('<Return>',lambda _event:self.submit())

    def schedule(self,_event=None):
        if self.search_timer is not None:
            self.after_cancel(self.search_timer)
        self.search_timer=self.after(300,self.submit)

    def submit(self):
        if self.search_timer is not None:
            self.after_cancel(self.search_timer)
        self.search_timer=None
        self.on_search()

    def destroy(self):
        if self.search_timer is not None:
            self.after_cancel(self.search_timer)
        super().destroy()
