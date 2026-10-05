import os

from argon2 import PasswordHasher
from dotenv import load_dotenv
from sqlalchemy import select

from src.config.database import SessionLocal
from src.models.role import Role
from src.models.user import User, UserStatus


load_dotenv(override=True)

password_hasher = PasswordHasher()

ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL")
ADMIN_USERNAME = os.getenv("SEED_ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD")


def seed_initial_admin():
    if not ADMIN_EMAIL or not ADMIN_USERNAME or not ADMIN_PASSWORD:
        raise RuntimeError(
            "Missing SEED_ADMIN_EMAIL, SEED_ADMIN_USERNAME "
            "or SEED_ADMIN_PASSWORD in .env"
        )

    with SessionLocal() as db:
        admin_role = db.scalar(
            select(Role).where(Role.code == "ADMINISTRATOR")
        )

        if admin_role is None:
            admin_role = Role(
                code="ADMINISTRATOR",
                name="Church Administrator",
                description=(
                    "Primary HOPFAN administrator with church-wide "
                    "operational management access."
                ),
                is_system=True,
                is_active=True,
            )

            db.add(admin_role)
            db.flush()

            print("Created ADMINISTRATOR role.")

        user = db.scalar(
            select(User).where(User.email == ADMIN_EMAIL)
        )

        if user is None:
            user = User(
                username=ADMIN_USERNAME,
                email=ADMIN_EMAIL,
                password_hash=password_hasher.hash(ADMIN_PASSWORD),
                status=UserStatus.ACTIVE,
                failed_login_attempts=0,
            )

            user.roles.append(admin_role)

            db.add(user)
            db.commit()

            print("Initial HOPFAN administrator created successfully.")
            print(f"Email: {ADMIN_EMAIL}")
            print("Role: ADMINISTRATOR")

        else:
            changed = False

            if admin_role not in user.roles:
                user.roles.append(admin_role)
                changed = True

            if user.status != UserStatus.ACTIVE:
                user.status = UserStatus.ACTIVE
                changed = True

            if changed:
                db.commit()

            print("Initial administrator already exists.")
            print(f"Email: {user.email}")
            print("Role: ADMINISTRATOR")


if __name__ == "__main__":
    seed_initial_admin()
