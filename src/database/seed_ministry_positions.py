"""Seed five configurable offices per ministry without restoring admin changes.

Run after migrations: python -m src.database.seed_ministry_positions
Use --actor-id UUID to select an authorized administrator explicitly.
"""
import argparse
import os
import re
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.postgresql import insert

from src.config.database import SessionLocal
from src.models import Ministry, MinistryPosition, MinistryLeadershipAuditLog, User
from src.services.authorization_service import AuthorizationService


DEFAULT_POSITIONS = (
    ('LEADER', 'Leader'),
    ('SECRETARY', 'Secretary'),
    ('ASSISTANT_LEADER', 'Assistant Leader'),
    ('ORGANIZER', 'Organizer'),
    ('TREASURER', 'Treasurer'),
)


def position_name(ministry_name, title):
    prefix = ' '.join(ministry_name.split())
    prefix = re.sub(r'\s+(MINISTRY|FELLOWSHIP|DEPARTMENT|UNIT)$', '', prefix, flags=re.IGNORECASE) or prefix
    return prefix[:149-len(title)].rstrip() + ' ' + title


def seed(session_factory=SessionLocal, actor_user_id=None):
    result = dict(ministries=0, created=0, existing=0, managed=0)
    with session_factory() as db:
        # Serialize repeat invocations. Unique indexes also protect against a
        # position being created through the ordinary manager during this run.
        db.execute(text('SELECT pg_advisory_xact_lock(847211)'))
        if actor_user_id is None:
            email = (os.getenv('SEED_ADMIN_EMAIL') or '').strip().lower()
            username = (os.getenv('SEED_ADMIN_USERNAME') or '').strip().lower()
            matches = []
            if email:
                matches.append(func.lower(User.email) == email)
            if username:
                matches.append(func.lower(User.username) == username)
            actors = set(db.scalars(select(User.id).where(or_(*matches)))) if matches else set()
            if len(actors) != 1:
                raise RuntimeError('Choose an authorized administrator with --actor-id UUID.')
            actor_user_id = actors.pop()
        access = AuthorizationService.load(db, UUID(str(actor_user_id)))
        access.require_permission('MINISTRIES_VIEW_ALL')
        access.require_permission('MINISTRY_POSITION_CREATE')

        ministries = db.scalars(select(Ministry).order_by(Ministry.code).with_for_update()).all()
        positions = db.execute(select(MinistryPosition.ministry_id, MinistryPosition.code, MinistryPosition.name)).all()
        current = {ministry.id: (set(), set()) for ministry in ministries}
        managed = {ministry.id: (set(), set()) for ministry in ministries}
        for ministry_id, code, name in positions:
            current[ministry_id][0].add(code.upper())
            current[ministry_id][1].add(name.casefold())
        history = db.execute(select(MinistryLeadershipAuditLog.ministry_id,
            MinistryLeadershipAuditLog.old_values, MinistryLeadershipAuditLog.new_values)
            .where(MinistryLeadershipAuditLog.action.in_(('POSITION_SEEDED', 'POSITION_EDITED', 'POSITION_DELETED_UNUSED')))).all()
        for ministry_id, old, new in history:
            for values in (old, new):
                if values:
                    managed[ministry_id][0].add(str(values.get('code') or '').upper())
                    managed[ministry_id][1].add(str(values.get('name') or '').casefold())

        for ministry in ministries:
            result['ministries'] += 1
            for order, (code, title) in enumerate(DEFAULT_POSITIONS, start=1):
                name = position_name(ministry.name, title)
                names = {name.casefold(), title.casefold()}
                codes, existing_names = current[ministry.id]
                old_codes, old_names = managed[ministry.id]
                if code in codes or names.intersection(existing_names):
                    result['existing'] += 1
                    continue
                if code in old_codes or names.intersection(old_names):
                    result['managed'] += 1
                    continue
                values = dict(code=code, name=name, description=None, sort_order=order*10,
                    is_leadership=True, is_active=bool(ministry.is_active and ministry.archived_at is None),
                    max_current_holders=1)
                pid = db.scalar(insert(MinistryPosition).values(id=uuid4(), ministry_id=ministry.id,
                    created_by_user_id=access.user_id, updated_by_user_id=access.user_id, **values)
                    .on_conflict_do_nothing().returning(MinistryPosition.id))
                if pid is None:
                    result['existing'] += 1
                    continue
                db.add(MinistryLeadershipAuditLog(ministry_id=ministry.id, position_id=pid,
                    actor_user_id=access.user_id, action='POSITION_SEEDED',
                    new_values=dict(values, source='default_ministry_positions')))
                codes.add(code)
                existing_names.add(name.casefold())
                result['created'] += 1
        db.commit()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actor-id', type=UUID, help='Administrator UUID; defaults to the configured seed administrator.')
    args = parser.parse_args()
    result = seed(actor_user_id=args.actor_id)
    print('Ministry positions ready. ' + ', '.join(f'{key}: {value}' for key, value in result.items()))


if __name__ == '__main__':
    main()
