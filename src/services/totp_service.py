import os
from pathlib import Path

import pyotp
import qrcode
from cryptography.fernet import Fernet
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(
    dotenv_path=ENV_FILE,
    override=True,
)


class TotpService:
    ISSUER = "HOPFAN Church Management System"

    def __init__(self):
        encryption_key = os.getenv(
            "APP_ENCRYPTION_KEY"
        )

        if not encryption_key:
            raise RuntimeError(
                "APP_ENCRYPTION_KEY is missing from .env"
            )

        self.fernet = Fernet(
            encryption_key.encode()
        )

    def generate_secret(self) -> str:
        return pyotp.random_base32()

    def encrypt_secret(
        self,
        secret: str,
    ) -> str:
        return self.fernet.encrypt(
            secret.encode()
        ).decode()

    def decrypt_secret(
        self,
        encrypted_secret: str,
    ) -> str:
        return self.fernet.decrypt(
            encrypted_secret.encode()
        ).decode()

    def provisioning_uri(
        self,
        secret: str,
        email: str,
    ) -> str:
        return pyotp.TOTP(
            secret
        ).provisioning_uri(
            name=email,
            issuer_name=self.ISSUER,
        )

    def verify_plain(
        self,
        secret: str,
        code: str,
    ) -> bool:
        if not code or len(code) != 6:
            return False

        return pyotp.TOTP(secret).verify(
            code,
            valid_window=1,
        )

    def verify_encrypted(
        self,
        encrypted_secret: str,
        code: str,
    ) -> bool:
        secret = self.decrypt_secret(
            encrypted_secret
        )

        return self.verify_plain(
            secret,
            code,
        )

    def qr_image(
        self,
        provisioning_uri: str,
    ):
        qr = qrcode.QRCode(
            version=1,
            box_size=8,
            border=2,
        )

        qr.add_data(
            provisioning_uri
        )

        qr.make(
            fit=True
        )

        return qr.make_image().convert(
            "RGB"
        )
