from datetime import date, datetime
from contextlib import contextmanager
from pathlib import Path
import shutil
import uuid
import logging

from sqlalchemy import (
    delete,
    func,
    or_,
    select,
    text,
)
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError

from src.config.database import SessionLocal
from src.models.member import (
    Gender,
    MaritalStatus,
    Member,
    MemberStatus,
)
from src.models.member_ministry import MemberMinistry
from src.models.ministry import Ministry
from src.models.ministry_leadership import MinistryLeadershipAssignment
from src.security.attendance_permissions import load_access, AttendancePermissionError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEMBER_PHOTO_DIR = (
    PROJECT_ROOT
    / "assets"
    / "member_photos"
)


class MemberServiceError(Exception):
    pass


class MemberAuthorizationError(MemberServiceError, AttendancePermissionError):
    pass


class MemberService:
    MEMBER_NUMBER_LOCK = 847201

    def __init__(self, user_id=None, session_factory=SessionLocal):
        self.user_id, self.session_factory = user_id, session_factory

    @contextmanager
    def _db(self):
        with self.session_factory() as db:
            try:
                yield db, load_access(db, self.user_id)
            except MemberAuthorizationError:
                raise
            except AttendancePermissionError as exc:
                raise MemberAuthorizationError(str(exc)) from exc
            except SQLAlchemyError as exc:
                db.rollback()
                logging.getLogger(__name__).error("Member database operation failed: %s", type(exc).__name__)
                raise MemberServiceError("The member operation could not be completed. Refresh and retry.") from exc

    @staticmethod
    def _require(access, permission):
        if not access.has(permission):
            raise MemberAuthorizationError("You do not have permission for this member operation.")

    @staticmethod
    def _visible(access, stmt):
        if access.has("MEMBERS_VIEW_ALL"):
            return stmt
        if not access.has("MEMBERS_VIEW_OWN_MINISTRY") or not access.ministry_ids("MEMBERS_VIEW_OWN_MINISTRY"):
            raise MemberAuthorizationError("Member directory access is not assigned.")
        membership = select(MemberMinistry.id).join(Ministry).where(
            MemberMinistry.member_id == Member.id, MemberMinistry.is_active.is_(True),
            Ministry.is_active.is_(True), MemberMinistry.ministry_id.in_(access.ministry_ids("MEMBERS_VIEW_OWN_MINISTRY"))).exists()
        return stmt.where(membership)

    # ------------------------------------------------------
    # DATE HELPERS
    # ------------------------------------------------------

    @staticmethod
    def _parse_date(value):
        if value is None:
            return None

        if isinstance(value, date):
            return value

        value = str(value).strip()

        if not value:
            return None

        try:
            return datetime.strptime(
                value,
                "%Y-%m-%d",
            ).date()

        except ValueError as exc:
            raise MemberServiceError(
                f"Invalid date '{value}'. "
                "Use YYYY-MM-DD."
            ) from exc

    # ------------------------------------------------------
    # MEMBER NUMBER
    # ------------------------------------------------------

    def _next_member_number(
        self,
        db,
    ):
        # PostgreSQL transaction advisory lock prevents
        # two users from generating the same number.
        db.execute(
            text(
                "SELECT pg_advisory_xact_lock(:lock_id)"
            ),
            {
                "lock_id": self.MEMBER_NUMBER_LOCK
            },
        )

        year = datetime.now().year
        prefix = f"HOPFAN-{year}-"

        numbers = db.scalars(
            select(Member.member_no)
            .where(
                Member.member_no.like(
                    f"{prefix}%"
                )
            )
        ).all()

        highest = 0

        for number in numbers:
            try:
                suffix = int(
                    number.rsplit(
                        "-",
                        1,
                    )[1]
                )

                highest = max(
                    highest,
                    suffix,
                )

            except (
                ValueError,
                IndexError,
            ):
                continue

        return (
            f"{prefix}"
            f"{highest + 1:04d}"
        )

    # ------------------------------------------------------
    # FIELD APPLICATION
    # ------------------------------------------------------

    def _apply_fields(
        self,
        member,
        data,
    ):
        first_name = (
            data.get(
                "first_name",
                "",
            )
            .strip()
        )

        last_name = (
            data.get(
                "last_name",
                "",
            )
            .strip()
        )

        if not first_name:
            raise MemberServiceError(
                "First name is required."
            )

        if not last_name:
            raise MemberServiceError(
                "Last name is required."
            )

        member.first_name = first_name
        member.middle_name = (
            data.get(
                "middle_name",
                "",
            ).strip()
            or None
        )

        member.last_name = last_name

        gender = (
            data.get(
                "gender",
                "",
            )
            .strip()
            .upper()
        )

        member.gender = (
            Gender(gender)
            if gender
            in {
                "MALE",
                "FEMALE",
            }
            else None
        )

        member.date_of_birth = (
            self._parse_date(
                data.get(
                    "date_of_birth"
                )
            )
        )

        member.phone = (
            data.get(
                "phone",
                "",
            ).strip()
            or None
        )

        member.alternate_phone = (
            data.get(
                "alternate_phone",
                "",
            ).strip()
            or None
        )

        email = (
            data.get(
                "email",
                "",
            )
            .strip()
            .lower()
        )

        member.email = (
            email
            or None
        )

        member.address = (
            data.get(
                "address",
                "",
            ).strip()
            or None
        )

        member.occupation = (
            data.get(
                "occupation",
                "",
            ).strip()
            or None
        )

        marital = (
            data.get(
                "marital_status",
                "",
            )
            .strip()
            .upper()
        )

        member.marital_status = (
            MaritalStatus(marital)
            if marital
            in {
                "SINGLE",
                "MARRIED",
                "DIVORCED",
                "WIDOWED",
            }
            else None
        )

        member.date_joined = (
            self._parse_date(
                data.get(
                    "date_joined"
                )
            )
        )

        member.baptized = bool(
            data.get(
                "baptized",
                False,
            )
        )

        member.baptism_date = (
            self._parse_date(
                data.get(
                    "baptism_date"
                )
            )
            if member.baptized
            else None
        )

        status = (
            data.get(
                "status",
                "ACTIVE",
            )
            .strip()
            .upper()
        )

        try:
            member.status = (
                MemberStatus(status)
            )
        except ValueError:
            member.status = (
                MemberStatus.ACTIVE
            )

    # ------------------------------------------------------
    # SERIALIZATION
    # ------------------------------------------------------

    @staticmethod
    def _member_dict(
        member,
    ):
        ministry_names = []
        ministry_ids = []

        memberships = getattr(
            member,
            "ministry_memberships",
            [],
        )

        for membership in sorted(memberships, key=lambda row: (not row.is_primary, str(row.ministry_id))):
            if (
                membership.is_active
                and membership.ministry
            ):
                ministry_names.append(
                    membership.ministry.name
                )

                ministry_ids.append(
                    str(
                        membership.ministry.id
                    )
                )

        return {
            "id": str(member.id),
            "member_no": member.member_no,
            "first_name": member.first_name,
            "middle_name": (
                member.middle_name
                or ""
            ),
            "last_name": member.last_name,
            "full_name": member.full_name,
            "gender": (
                member.gender.value
                if member.gender
                else ""
            ),
            "date_of_birth": (
                member.date_of_birth.isoformat()
                if member.date_of_birth
                else ""
            ),
            "phone": (
                member.phone
                or ""
            ),
            "alternate_phone": (
                member.alternate_phone
                or ""
            ),
            "email": (
                member.email
                or ""
            ),
            "address": (
                member.address
                or ""
            ),
            "occupation": (
                member.occupation
                or ""
            ),
            "marital_status": (
                member.marital_status.value
                if member.marital_status
                else ""
            ),
            "date_joined": (
                member.date_joined.isoformat()
                if member.date_joined
                else ""
            ),
            "baptized": member.baptized,
            "baptism_date": (
                member.baptism_date.isoformat()
                if member.baptism_date
                else ""
            ),
            "status": member.status.value,
            "photo_path": (
                member.photo_path
                or ""
            ),
            "ministries": ministry_names,
            "ministry_ids": ministry_ids,
        }

    # ------------------------------------------------------
    # LIST / SEARCH
    # ------------------------------------------------------

    def list_members(
        self,
        search="",
        status="ALL",
        limit=50,
        offset=0,
    ):
        with self._db() as (db, access):
            stmt = (
                select(Member)
                .options(
                    selectinload(
                        Member.ministry_memberships
                    ).selectinload(
                        MemberMinistry.ministry
                    )
                )
            )

            stmt = self._visible(access, stmt)
            search = search.strip()

            if search:
                pattern = (
                    f"%{search}%"
                )

                stmt = stmt.where(
                    or_(
                        Member.member_no.ilike(
                            pattern
                        ),
                        Member.first_name.ilike(
                            pattern
                        ),
                        Member.middle_name.ilike(
                            pattern
                        ),
                        Member.last_name.ilike(
                            pattern
                        ),
                        Member.phone.ilike(
                            pattern
                        ),
                        Member.email.ilike(
                            pattern
                        ),
                    )
                )

            if (
                status
                and status != "ALL"
            ):
                try:
                    stmt = stmt.where(
                        Member.status
                        == MemberStatus(
                            status
                        )
                    )
                except ValueError:
                    pass

            stmt = stmt.order_by(
                Member.last_name.asc(),
                Member.first_name.asc(),
            )

            members = db.scalars(
                stmt.limit(min(max(limit, 1), 200)).offset(max(offset, 0))
            ).unique().all()

            return [
                self._member_dict(
                    member
                )
                for member in members
            ]

    # ------------------------------------------------------
    # GET ONE MEMBER
    # ------------------------------------------------------

    def get_member(
        self,
        member_id,
    ):
        with self._db() as (db, access):
            member = db.scalar(
                self._visible(access, select(Member))
                .options(
                    selectinload(
                        Member.ministry_memberships
                    ).selectinload(
                        MemberMinistry.ministry
                    )
                )
                .where(
                    Member.id
                    == uuid.UUID(
                        str(member_id)
                    )
                )
            )

            if member is None:
                raise MemberAuthorizationError(
                    "Member not found or outside your assigned scope."
                )

            result = self._member_dict(member)
            if access.has('MINISTRY_LEADERSHIP_VIEW') or access.has('MINISTRY_LEADERSHIP_VIEW_ALL'):
                from src.services.ministry_leadership_service import MinistryLeadershipService
                result['leadership'] = MinistryLeadershipService.member_leadership(db, access, member.id)
            else:
                result['leadership'] = []
            return result

    # ------------------------------------------------------
    # STATISTICS
    # ------------------------------------------------------

    def stats(self):
        with self._db() as (db, access):
            total = db.scalar(
                self._visible(access, select(
                    func.count(
                        Member.id
                    )
                ))
            ) or 0

            active = db.scalar(
                self._visible(access, select(
                    func.count(
                        Member.id
                    )
                )).where(
                    Member.status
                    == MemberStatus.ACTIVE
                )
            ) or 0

            inactive = db.scalar(
                self._visible(access, select(
                    func.count(
                        Member.id
                    )
                )).where(
                    Member.status
                    == MemberStatus.INACTIVE
                )
            ) or 0

            baptized = db.scalar(
                self._visible(access, select(
                    func.count(
                        Member.id
                    )
                )).where(
                    Member.baptized.is_(
                        True
                    )
                )
            ) or 0

            return {
                "total": total,
                "active": active,
                "inactive": inactive,
                "baptized": baptized,
            }

    # ------------------------------------------------------
    # MINISTRIES
    # ------------------------------------------------------

    def list_ministries(self, member_id=None):
        with self._db() as (db, access):
            eligible = Ministry.is_active.is_(True)
            if member_id:
                member_uuid = uuid.UUID(str(member_id))
                if not db.scalar(self._visible(access, select(Member.id)).where(Member.id==member_uuid)):
                    raise MemberAuthorizationError('Member not found or outside your scope.')
                existing = select(MemberMinistry.ministry_id).where(MemberMinistry.member_id==member_uuid,
                    MemberMinistry.is_active.is_(True))
                eligible = or_(eligible,Ministry.id.in_(existing))
            stmt = select(Ministry).where(eligible)
            if not (access.has("MINISTRIES_VIEW_ALL") or access.has("MEMBERS_VIEW_ALL")):
                if not (access.has("MINISTRIES_VIEW_OWN") or access.has("MEMBERS_VIEW_OWN_MINISTRY")):
                    raise MemberAuthorizationError("Ministry access is not assigned.")
                stmt = stmt.where(Ministry.id.in_(access.ministry_ids("MEMBERS_VIEW_OWN_MINISTRY")))
            ministries = db.scalars(
                stmt
                .order_by(
                    Ministry.name.asc()
                )
            ).all()

            return [
                {
                    "id": str(
                        ministry.id
                    ),
                    "code": ministry.code,
                    "name": ministry.name,
                    "status": ministry.status,
                }
                for ministry
                in ministries
            ]

    # ------------------------------------------------------
    # CREATE
    # ------------------------------------------------------

    def create_member(
        self,
        data,
        ministry_ids=None,
    ):
        ministry_ids = (
            ministry_ids
            or []
        )

        with self._db() as (db, access):
            self._require(access, "MEMBERS_CREATE")
            self._require(access, "MEMBERS_VIEW_ALL")
            ministry_ids = list(dict.fromkeys(uuid.UUID(str(mid)) for mid in ministry_ids))
            active = set(db.scalars(select(Ministry.id).where(Ministry.id.in_(ministry_ids), Ministry.is_active.is_(True))
                .order_by(Ministry.id).with_for_update(read=True)).all())
            if set(ministry_ids) != active:
                raise MemberServiceError("Select active ministries.")
            member = Member(
                member_no=self._next_member_number(
                    db
                )
            )

            self._apply_fields(
                member,
                data,
            )

            db.add(member)
            db.flush()

            for index, ministry_id in enumerate(
                ministry_ids
            ):
                db.add(
                    MemberMinistry(
                        member_id=member.id,
                        ministry_id=uuid.UUID(
                            str(ministry_id)
                        ),
                        is_primary=(
                            index == 0
                        ),
                        is_active=True,
                        joined_at=(
                            member.date_joined
                        ),
                    )
                )

            db.commit()

            member_id = member.id

        return self.get_member(
            member_id
        )

    # ------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------

    def update_member(
        self,
        member_id,
        data,
        ministry_ids=None,
    ):
        ministry_ids = (
            ministry_ids
            or []
        )

        member_uuid = uuid.UUID(
            str(member_id)
        )

        with self._db() as (db, access):
            self._require(access, "MEMBERS_EDIT")
            member = db.scalar(self._visible(access, select(Member)).where(Member.id == member_uuid).with_for_update())

            if member is None:
                raise MemberAuthorizationError(
                    "Member not found or outside your assigned scope."
                )

            self._apply_fields(
                member,
                data,
            )

            # Retain membership identity, assigned position and participation history.
            selected = list(dict.fromkeys(uuid.UUID(str(mid)) for mid in ministry_ids))
            existing = {row.ministry_id: row for row in db.scalars(select(MemberMinistry).where(
                MemberMinistry.member_id == member_uuid)).all()}
            active_ministries = set(db.scalars(select(Ministry.id).where(
                Ministry.id.in_(selected), Ministry.is_active.is_(True)).order_by(Ministry.id).with_for_update(read=True)).all())
            retained = {mid for mid,row in existing.items() if row.is_active}
            if not set(selected).issubset(active_ministries | retained):
                raise MemberServiceError("Select active ministries. Existing inactive/archived participation may be retained or explicitly removed.")
            current_positions = db.scalars(select(MinistryLeadershipAssignment.ministry_id).where(
                MinistryLeadershipAssignment.member_id == member_uuid, MinistryLeadershipAssignment.is_current.is_(True))).all()
            if any(mid not in selected for mid in current_positions) or (current_positions and member.status != MemberStatus.ACTIVE):
                raise MemberServiceError('End current position assignments before removing ministry participation or deactivating this member.')
            for mid, row in existing.items():
                if mid not in selected and row.is_active:
                    row.is_active, row.is_primary, row.left_at = False, False, date.today()
            for index, mid in enumerate(selected):
                if mid in existing:
                    row = existing[mid]
                    row.is_active, row.is_primary, row.left_at = True, index == 0, None
                else:
                    db.add(MemberMinistry(member_id=member.id, ministry_id=mid,
                        is_primary=index == 0, is_active=True, joined_at=member.date_joined))

            db.commit()

        return self.get_member(
            member_uuid
        )

    # ------------------------------------------------------
    # PHOTO
    # ------------------------------------------------------

    def set_photo(
        self,
        member_id,
        source_path,
    ):
        member_uuid = uuid.UUID(
            str(member_id)
        )

        source = Path(
            source_path
        )

        if not source.exists():
            raise MemberServiceError(
                "Selected photo does not exist."
            )

        allowed = {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
        }

        extension = (
            source.suffix.lower()
        )

        if extension not in allowed:
            raise MemberServiceError(
                "Use JPG, JPEG, PNG or WEBP."
            )

        MEMBER_PHOTO_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self._db() as (db, access):
            self._require(access, "MEMBERS_EDIT")
            member = db.scalar(self._visible(access, select(Member)).where(Member.id == member_uuid))

            if member is None:
                raise MemberAuthorizationError(
                    "Member not found or outside your assigned scope."
                )

            filename = (
                f"{member.member_no}"
                f"{extension}"
            )

            destination = (
                MEMBER_PHOTO_DIR
                / filename
            )

            if (
                source.resolve()
                != destination.resolve()
            ):
                shutil.copy2(
                    source,
                    destination,
                )

            relative = destination.relative_to(
                PROJECT_ROOT
            )

            member.photo_path = (
                relative.as_posix()
            )

            db.commit()

        return self.get_member(
            member_uuid
        )
