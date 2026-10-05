"""Keyboard-accessible contextual actions using the shared bounded popover."""
from src.ui.components.modern_select import ModernSelect


class ActionMenu(ModernSelect):
    def __init__(self,master,actions):
        self.actions=dict(actions)
        self.popup_width=220
        super().__init__(master,values=list(self.actions),placeholder='More',height=36,width=86,command=self.selected)
        self.set('')

    def selected(self,action):
        self.set('')
        self.actions[action]()
