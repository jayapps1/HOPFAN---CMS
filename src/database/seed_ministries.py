from sqlalchemy import select

from src.config.database import SessionLocal
from src.models.ministry import Ministry


MINISTRIES = [
    (
        "YOUTH",
        "Youth Ministry",
    ),
    (
        "WOMEN",
        "Women's Fellowship",
    ),
    (
        "MEN",
        "Men's Fellowship",
    ),
    (
        "CHOIR",
        "Choir / Music Ministry",
    ),
    (
        "PROTOCOL",
        "Protocol Ministry",
    ),
    (
        "USHERS",
        "Ushers Ministry",
    ),
    (
        "MEDIA",
        "Media Ministry",
    ),
    (
        "ICT",
        "ICT Ministry",
    ),
    (
        "PRAYER",
        "Prayer Ministry",
    ),
    (
        "EVANGELISM",
        "Evangelism Ministry",
    ),
    (
        "WELFARE",
        "Welfare Ministry",
    ),
    (
        "SECURITY",
        "Security Ministry",
    ),
    (
        "COUNSELLING",
        "Counselling Ministry",
    ),
    (
        "SUNDAY_SCHOOL",
        "Sunday School",
    ),
]


def seed():
    created = 0

    with SessionLocal() as db:
        for code, name in MINISTRIES:
            ministry = db.scalar(
                select(Ministry)
                .where(
                    Ministry.code
                    == code
                )
            )

            if ministry is None:
                ministry = Ministry(
                    code=code,
                    name=name,
                    is_active=True,
                )

                db.add(ministry)
                created += 1

            # Existing administrator changes and lifecycle states are authoritative.

        db.commit()

    print(
        f"Ministries ready. "
        f"Created: {created}"
    )


if __name__ == "__main__":
    seed()
