from PIL import Image, ImageDraw
import customtkinter as ctk


LIGHT = "#55687A"
DARK = "#D7E1EA"
WHITE = "#FFFFFF"


def _canvas(size):
    return Image.new(
        "RGBA",
        (size, size),
        (0, 0, 0, 0),
    )


def _draw(name, color, size):
    image = _canvas(size)
    d = ImageDraw.Draw(image)

    w = max(2, size // 12)
    p = max(4, size // 5)
    c = size // 2

    # -------------------------------------------------
    # LOGIN ICONS
    # -------------------------------------------------

    if name == "mail":
        d.rounded_rectangle(
            (p, p + 2, size - p, size - p - 1),
            radius=3,
            outline=color,
            width=w,
        )

        d.line(
            (
                p + 1,
                p + 4,
                c,
                c + 2,
                size - p - 1,
                p + 4,
            ),
            fill=color,
            width=w,
        )

    elif name == "lock":
        d.rounded_rectangle(
            (
                p,
                c - 1,
                size - p,
                size - p,
            ),
            radius=4,
            outline=color,
            width=w,
        )

        d.arc(
            (
                size // 3,
                p,
                size - size // 3,
                c + 5,
            ),
            180,
            360,
            fill=color,
            width=w,
        )

    elif name in ("eye", "eye_off"):
        d.ellipse(
            (
                p,
                size // 3,
                size - p,
                size - size // 3,
            ),
            outline=color,
            width=w,
        )

        r = max(2, size // 10)

        d.ellipse(
            (
                c - r,
                c - r,
                c + r,
                c + r,
            ),
            fill=color,
        )

        if name == "eye_off":
            d.line(
                (
                    p,
                    size - p,
                    size - p,
                    p,
                ),
                fill=color,
                width=w,
            )

    elif name == "shield":
        pts = [
            (c, p),
            (size - p, p + 3),
            (size - p - 1, c + 3),
            (c, size - p),
            (p + 1, c + 3),
            (p, p + 3),
            (c, p),
        ]

        d.line(
            pts,
            fill=color,
            width=w,
            joint="curve",
        )

    elif name == "arrow":
        d.line(
            (
                p,
                c,
                size - p - 2,
                c,
            ),
            fill=color,
            width=w,
        )

        d.line(
            (
                size - p - 7,
                c - 5,
                size - p - 2,
                c,
                size - p - 7,
                c + 5,
            ),
            fill=color,
            width=w,
        )

    # -------------------------------------------------
    # THEME
    # -------------------------------------------------

    elif name == "sun":
        r = size // 6

        d.ellipse(
            (
                c - r,
                c - r,
                c + r,
                c + r,
            ),
            outline=color,
            width=w,
        )

        d.line((c, p, c, p + 4), fill=color, width=w)
        d.line((c, size - p, c, size - p - 4), fill=color, width=w)
        d.line((p, c, p + 4, c), fill=color, width=w)
        d.line((size - p, c, size - p - 4, c), fill=color, width=w)

    elif name == "moon":
        d.arc(
            (
                p,
                p,
                size - p,
                size - p,
            ),
            70,
            290,
            fill=color,
            width=w,
        )

        d.arc(
            (
                c - 2,
                p + 1,
                size - 2,
                size - p - 1,
            ),
            100,
            260,
            fill=color,
            width=w,
        )

    # -------------------------------------------------
    # DASHBOARD
    # -------------------------------------------------

    elif name == "home":
        d.line(
            (
                p,
                c,
                c,
                p,
                size - p,
                c,
            ),
            fill=color,
            width=w,
        )

        d.rounded_rectangle(
            (
                p + 3,
                c,
                size - p - 3,
                size - p,
            ),
            radius=2,
            outline=color,
            width=w,
        )

    elif name == "users":
        d.ellipse(
            (
                p + 2,
                p,
                c + 3,
                c + 1,
            ),
            outline=color,
            width=w,
        )

        d.arc(
            (
                p,
                c - 1,
                c + 6,
                size - p,
            ),
            180,
            360,
            fill=color,
            width=w,
        )

        d.ellipse(
            (
                c + 1,
                p + 3,
                size - p,
                c + 3,
            ),
            outline=color,
            width=w,
        )

    elif name == "calendar":
        stroke = max(1, size//16)
        margin = max(2, size//8)
        d.rounded_rectangle((margin, 2*margin, size-margin, size-margin), radius=stroke, outline=color, width=stroke)
        d.line((margin, size*2//5, size-margin, size*2//5), fill=color, width=stroke)
        for x in (size//3, size*2//3):
            d.line((x, margin, x, 2*margin+stroke), fill=color, width=stroke)
        for x in (size*2//5, size*3//5):
            for y in (size*3//5, size*4//5):
                d.rectangle((x, y, x+stroke-1, y+stroke-1), fill=color)

    elif name == "attendance":
        d.rounded_rectangle(
            (
                p,
                p,
                size - p,
                size - p,
            ),
            radius=3,
            outline=color,
            width=w,
        )

        d.line(
            (
                p + 4,
                c,
                c - 1,
                size - p - 5,
                size - p - 4,
                p + 6,
            ),
            fill=color,
            width=w,
        )

    elif name == "ministries":
        r = 3

        positions = [
            (p + 2, p + 2),
            (size - p - 2, p + 2),
            (p + 2, size - p - 2),
            (size - p - 2, size - p - 2),
        ]

        for x, y in positions:
            d.ellipse(
                (
                    x - r,
                    y - r,
                    x + r,
                    y + r,
                ),
                fill=color,
            )

        d.line((p + 5, p + 5, c, c), fill=color, width=w)
        d.line((size - p - 5, p + 5, c, c), fill=color, width=w)
        d.line((p + 5, size - p - 5, c, c), fill=color, width=w)
        d.line((size - p - 5, size - p - 5, c, c), fill=color, width=w)

    elif name == "book":
        d.line(
            (
                c,
                p,
                c,
                size - p,
            ),
            fill=color,
            width=w,
        )

        d.rounded_rectangle(
            (
                p,
                p,
                c,
                size - p,
            ),
            radius=2,
            outline=color,
            width=w,
        )

        d.rounded_rectangle(
            (
                c,
                p,
                size - p,
                size - p,
            ),
            radius=2,
            outline=color,
            width=w,
        )

    elif name == "finance":
        d.rounded_rectangle(
            (
                p,
                p + 3,
                size - p,
                size - p,
            ),
            radius=3,
            outline=color,
            width=w,
        )

        d.line(
            (
                p,
                c - 3,
                size - p,
                c - 3,
            ),
            fill=color,
            width=w,
        )

        d.ellipse(
            (
                c - 2,
                c + 1,
                c + 2,
                c + 5,
            ),
            fill=color,
        )

    elif name == "heart":
        d.arc(
            (
                p,
                p + 2,
                c + 2,
                c + 4,
            ),
            180,
            360,
            fill=color,
            width=w,
        )

        d.arc(
            (
                c - 2,
                p + 2,
                size - p,
                c + 4,
            ),
            180,
            360,
            fill=color,
            width=w,
        )

        d.line(
            (
                p + 1,
                c,
                c,
                size - p,
                size - p - 1,
                c,
            ),
            fill=color,
            width=w,
        )

    elif name == "message":
        d.rounded_rectangle(
            (
                p,
                p,
                size - p,
                size - p - 3,
            ),
            radius=4,
            outline=color,
            width=w,
        )

        d.line(
            (
                c - 2,
                size - p - 3,
                c - 5,
                size - p + 2,
                c + 2,
                size - p - 3,
            ),
            fill=color,
            width=w,
        )

    elif name == "chart":
        d.line(
            (
                p,
                size - p,
                p,
                p,
            ),
            fill=color,
            width=w,
        )

        d.line(
            (
                p,
                size - p,
                size - p,
                size - p,
            ),
            fill=color,
            width=w,
        )

        d.line(
            (
                p + 3,
                size - p - 4,
                c - 2,
                c,
                c + 3,
                c + 3,
                size - p,
                p + 3,
            ),
            fill=color,
            width=w,
        )

    elif name == "settings":
        d.ellipse(
            (
                c - 4,
                c - 4,
                c + 4,
                c + 4,
            ),
            outline=color,
            width=w,
        )

        d.ellipse(
            (
                p,
                p,
                size - p,
                size - p,
            ),
            outline=color,
            width=w,
        )

    elif name == "logout":
        d.rounded_rectangle(
            (
                p,
                p,
                c + 2,
                size - p,
            ),
            radius=2,
            outline=color,
            width=w,
        )

        d.line(
            (
                c,
                c,
                size - p,
                c,
            ),
            fill=color,
            width=w,
        )

        d.line(
            (
                size - p - 4,
                c - 4,
                size - p,
                c,
                size - p - 4,
                c + 4,
            ),
            fill=color,
            width=w,
        )

    elif name == "bell":
        d.arc(
            (
                p,
                p,
                size - p,
                size - p,
            ),
            180,
            360,
            fill=color,
            width=w,
        )

        d.line(
            (
                p,
                c,
                p,
                size - p - 3,
                size - p,
                size - p - 3,
                size - p,
                c,
            ),
            fill=color,
            width=w,
        )

    return image


def icon(
    name,
    size=22,
    white=False,
):
    if white:
        image = _draw(
            name,
            WHITE,
            size,
        )

        return ctk.CTkImage(
            light_image=image,
            dark_image=image,
            size=(size, size),
        )

    return ctk.CTkImage(
        light_image=_draw(
            name,
            LIGHT,
            size,
        ),
        dark_image=_draw(
            name,
            DARK,
            size,
        ),
        size=(size, size),
    )
