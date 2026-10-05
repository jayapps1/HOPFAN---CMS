import customtkinter as ctk

from src.ui import theme


class TotpInput(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_complete=None,
    ):
        super().__init__(
            master,
            fg_color="transparent",
        )

        self.on_complete = on_complete
        self.entries = []
        self.last_completed_code = ""

        for index in range(6):
            entry = ctk.CTkEntry(
                self,
                width=58,
                height=64,
                corner_radius=14,
                justify="center",
                font=ctk.CTkFont(
                    family=theme.FONT_FAMILY,
                    size=25,
                    weight="bold",
                ),
                fg_color=theme.INPUT,
                border_color=theme.BORDER,
                border_width=1,
                text_color=theme.TEXT,
            )

            entry.grid(
                row=0,
                column=index,
                padx=5,
            )

            entry.bind(
                "<KeyRelease>",
                lambda event, i=index:
                self._key_released(
                    event,
                    i,
                ),
            )

            entry.bind(
                "<Control-v>",
                self._paste,
            )

            self.entries.append(entry)

    def _key_released(
        self,
        event,
        index,
    ):
        entry = self.entries[index]
        value = entry.get()

        digits = "".join(
            c for c in value
            if c.isdigit()
        )

        if len(digits) > 1:
            self.set_code(
                digits[:6]
            )
            return

        if value and not value.isdigit():
            entry.delete(
                0,
                "end",
            )
            return

        if value and index < 5:
            self.entries[
                index + 1
            ].focus_set()

        elif (
            event.keysym == "BackSpace"
            and not value
            and index > 0
        ):
            previous = self.entries[
                index - 1
            ]

            previous.focus_set()

        self._check_complete()

    def _paste(
        self,
        event=None,
    ):
        try:
            value = self.clipboard_get()
        except Exception:
            return "break"

        digits = "".join(
            c for c in value
            if c.isdigit()
        )

        self.set_code(
            digits[:6]
        )

        return "break"

    def set_code(
        self,
        code,
    ):
        self.clear(
            focus=False
        )

        for index, digit in enumerate(
            code[:6]
        ):
            self.entries[index].insert(
                0,
                digit,
            )

        if len(code) < 6:
            self.entries[
                len(code)
            ].focus_set()

        self._check_complete()

    def get_code(self):
        return "".join(
            entry.get()
            for entry in self.entries
        )

    def _check_complete(self):
        code = self.get_code()

        if (
            len(code) == 6
            and code.isdigit()
            and code != self.last_completed_code
        ):
            self.last_completed_code = code

            if self.on_complete:
                self.after(
                    90,
                    lambda:
                    self.on_complete(code),
                )

    def clear(
        self,
        focus=True,
    ):
        for entry in self.entries:
            entry.delete(
                0,
                "end",
            )

        self.last_completed_code = ""

        if focus:
            self.entries[0].focus_set()

    def focus_first(self):
        self.entries[0].focus_set()
