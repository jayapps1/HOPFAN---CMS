"""Sunday School extensions reference the single church Member register."""
import uuid
from datetime import date, datetime
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from src.database.base import Base


class SchoolTimestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SundaySchoolClass(SchoolTimestamps, Base):
    __tablename__ = 'sunday_school_classes'
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','INACTIVE')", name='ck_school_class_status'),
        CheckConstraint('minimum_age IS NULL OR minimum_age BETWEEN 0 AND 125', name='ck_school_class_min_age'),
        CheckConstraint('maximum_age IS NULL OR maximum_age BETWEEN 0 AND 125', name='ck_school_class_max_age'),
        CheckConstraint('minimum_age IS NULL OR maximum_age IS NULL OR maximum_age >= minimum_age', name='ck_school_class_age_range'),
        CheckConstraint('capacity IS NULL OR capacity > 0', name='ck_school_class_capacity'),
        CheckConstraint('teacher_capacity IS NULL OR teacher_capacity > 0', name='ck_school_class_teacher_capacity'),
        CheckConstraint('sort_order >= 0', name='ck_school_class_sort'),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    minimum_age: Mapped[int | None] = mapped_column(Integer)
    maximum_age: Mapped[int | None] = mapped_column(Integer)
    room_location: Mapped[str | None] = mapped_column(String(150))
    capacity: Mapped[int | None] = mapped_column(Integer)
    teacher_capacity: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default='ACTIVE', server_default='ACTIVE', nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default='0', nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))


Index('uq_school_class_name', func.lower(SundaySchoolClass.name), unique=True)
Index('uq_school_class_code', func.upper(SundaySchoolClass.code), unique=True)


class SundaySchoolStudent(SchoolTimestamps, Base):
    __tablename__ = 'sunday_school_students'
    __table_args__ = (CheckConstraint("status IN ('ACTIVE','INACTIVE')", name='ck_school_student_status'),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('members.id', ondelete='RESTRICT'), unique=True, nullable=False)
    admission_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default='ACTIVE', server_default='ACTIVE', nullable=False, index=True)
    special_notes: Mapped[str | None] = mapped_column(Text)


class SundaySchoolEnrollment(SchoolTimestamps, Base):
    __tablename__ = 'sunday_school_enrollments'
    __table_args__ = (
        ForeignKeyConstraint(['member_id'], ['sunday_school_students.member_id'], ondelete='RESTRICT', name='fk_school_enrollment_student'),
        CheckConstraint('end_date IS NULL OR end_date >= start_date', name='ck_school_enrollment_dates'),
        CheckConstraint("(is_current AND end_date IS NULL AND status='ACTIVE') OR (NOT is_current AND end_date IS NOT NULL AND status='ENDED')", name='ck_school_enrollment_current'),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('sunday_school_classes.id', ondelete='RESTRICT'), nullable=False, index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('members.id', ondelete='RESTRICT'), nullable=False, index=True)
    class_name: Mapped[str] = mapped_column(String(150), nullable=False)
    class_code: Mapped[str] = mapped_column(String(60), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true', nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default='ACTIVE', server_default='ACTIVE', nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


Index('uq_school_enrollment_current', SundaySchoolEnrollment.member_id, unique=True, postgresql_where=SundaySchoolEnrollment.is_current.is_(True))


class SundaySchoolTeacherAssignment(SchoolTimestamps, Base):
    __tablename__ = 'sunday_school_teacher_assignments'
    __table_args__ = (
        CheckConstraint("role IN ('TEACHER','ASSISTANT_TEACHER','CLASS_COORDINATOR')", name='ck_school_teacher_role'),
        CheckConstraint('end_date IS NULL OR end_date >= start_date', name='ck_school_teacher_dates'),
        CheckConstraint('(is_current AND end_date IS NULL) OR (NOT is_current AND end_date IS NOT NULL)', name='ck_school_teacher_current'),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('sunday_school_classes.id', ondelete='RESTRICT'), nullable=False, index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('members.id', ondelete='RESTRICT'), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true', nullable=False, index=True)


Index('uq_school_teacher_current', SundaySchoolTeacherAssignment.class_id, SundaySchoolTeacherAssignment.member_id,
    unique=True, postgresql_where=SundaySchoolTeacherAssignment.is_current.is_(True))


class SundaySchoolGuardian(SchoolTimestamps, Base):
    __tablename__ = 'sunday_school_guardians'
    __table_args__ = (
        UniqueConstraint('student_id', 'guardian_member_id', name='uq_school_guardian_member'),
        CheckConstraint("relationship IN ('PARENT','GUARDIAN','FATHER','MOTHER','RELATIVE','OTHER')", name='ck_school_guardian_relationship'),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('sunday_school_students.id', ondelete='RESTRICT'), nullable=False, index=True)
    guardian_member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('members.id', ondelete='RESTRICT'), nullable=False, index=True)
    relationship: Mapped[str] = mapped_column(String(16), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false', nullable=False)
    can_receive_sms: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false', nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true', nullable=False)


Index('uq_school_primary_guardian', SundaySchoolGuardian.student_id, unique=True,
    postgresql_where=SundaySchoolGuardian.is_primary.is_(True) & SundaySchoolGuardian.is_active.is_(True))


class SundaySchoolUserClassScope(SchoolTimestamps, Base):
    __tablename__ = 'sunday_school_user_class_scopes'
    __table_args__ = (UniqueConstraint('user_id', 'class_id', name='uq_school_user_class_scope'),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('sunday_school_classes.id', ondelete='RESTRICT'), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true', nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))


class SundaySchoolLesson(SchoolTimestamps, Base):
    __tablename__ = 'sunday_school_lessons'
    __table_args__ = (CheckConstraint("status IN ('DRAFT','PUBLISHED','ARCHIVED')", name='ck_school_lesson_status'),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    lesson_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    topic: Mapped[str | None] = mapped_column(String(200))
    scripture_reference: Mapped[str | None] = mapped_column(String(200))
    objective: Mapped[str | None] = mapped_column(Text)
    lesson_summary: Mapped[str | None] = mapped_column(Text)
    teacher_notes: Mapped[str | None] = mapped_column(Text)
    applies_to_all: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false', nullable=False)
    status: Mapped[str] = mapped_column(String(16), default='DRAFT', server_default='DRAFT', nullable=False, index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))


class SundaySchoolLessonClass(Base):
    __tablename__ = 'sunday_school_lesson_classes'
    lesson_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('sunday_school_lessons.id', ondelete='RESTRICT'), primary_key=True)
    class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('sunday_school_classes.id', ondelete='RESTRICT'), primary_key=True, index=True)


class SundaySchoolAttendanceSession(SchoolTimestamps, Base):
    __tablename__ = 'sunday_school_attendance_sessions'
    __table_args__ = (
        UniqueConstraint('class_id', 'session_date', name='uq_school_class_attendance_date'),
        CheckConstraint("state IN ('DRAFT','OPEN','CLOSED')", name='ck_school_session_state'),
        CheckConstraint("(state='DRAFT' AND opened_at IS NULL AND closed_at IS NULL) OR (state='OPEN' AND opened_at IS NOT NULL AND closed_at IS NULL) OR (state='CLOSED' AND opened_at IS NOT NULL AND closed_at IS NOT NULL)", name='ck_school_session_lifecycle'),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('sunday_school_classes.id', ondelete='RESTRICT'), nullable=False, index=True)
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('sunday_school_lessons.id', ondelete='RESTRICT'))
    session_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(String(16), default='DRAFT', server_default='DRAFT', nullable=False, index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SundaySchoolRosterMember(Base):
    __tablename__ = 'sunday_school_roster_members'
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('sunday_school_attendance_sessions.id', ondelete='RESTRICT'), primary_key=True)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('members.id', ondelete='RESTRICT'), primary_key=True, index=True)
    enrollment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('sunday_school_enrollments.id', ondelete='RESTRICT'), nullable=False)


class SundaySchoolAttendanceRecord(SchoolTimestamps, Base):
    __tablename__ = 'sunday_school_attendance_records'
    __table_args__ = (
        ForeignKeyConstraint(['session_id','member_id'], ['sunday_school_roster_members.session_id','sunday_school_roster_members.member_id'], ondelete='RESTRICT', name='fk_school_record_roster'),
        UniqueConstraint('session_id', 'member_id', name='uq_school_session_member_record'),
        CheckConstraint("status IN ('PRESENT','LATE','EXCUSED','ABSENT')", name='ck_school_attendance_status'),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('sunday_school_attendance_sessions.id', ondelete='RESTRICT'), nullable=False, index=True)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('members.id', ondelete='RESTRICT'), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    marked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    marked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class SundaySchoolAuditLog(Base):
    __tablename__ = 'sunday_school_audit_logs'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    member_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    record_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    old_values: Mapped[dict | None] = mapped_column(JSONB)
    new_values: Mapped[dict | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
