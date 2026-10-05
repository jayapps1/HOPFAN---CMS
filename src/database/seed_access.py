"""Optional, idempotent baseline catalogue seeding after the schema upgrade."""
from importlib import import_module
from src.config.database import engine


def seed():
    catalogue=import_module('migrations.versions.a91c73d5f204_user_administration')
    with engine.begin() as connection:
        catalogue.seed_missing(connection)
    print('Access catalogue ready. Existing roles, grants and users preserved.')


if __name__=='__main__':
    seed()
