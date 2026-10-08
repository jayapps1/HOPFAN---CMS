"""Loopback-only Playwright fixture using real auth in a disposable schema.

Never import this from the production API. No production identity is changed.
"""
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
import json
import subprocess,os
import shutil
from pathlib import Path
import re
from typing import Annotated
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from fastapi import Depends, HTTPException, Request
import pyotp
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from src.api.dependencies import get_db, require_ministry_permission
from src.api.main import create_app
from src.api.security.session import read_session_cookie
from src.config.database import engine
from src.config.online_settings import OnlineSettings
from src.database.base import Base
from src.models import (Member, MemberStatus, Ministry, Permission, Role, User, UserStatus,
                        UserMinistryScope, SundaySchoolClass, SundaySchoolUserClassScope, WebSession,
                        MemberMinistry, MinistryPosition, MinistryLeadershipAssignment,
                        SundaySchoolStudent, SundaySchoolEnrollment, SundaySchoolTeacherAssignment,
                        Household, HouseholdMember)
from src.security.application_permissions import PERMISSIONS as APP
from src.security.attendance_permissions import PERMISSIONS as ATT
from src.security.administration_permissions import PERMISSIONS as ADMIN
from src.security.sunday_school_permissions import TEACHER_PERMISSIONS
from src.services.api_readiness_service import check_api_database_access
from src.services.totp_service import TotpService
from src.services.web_security import session_hash
from src.security.content_permissions import OWN_EDITOR
from src.services.website_media_service import LocalWebsiteStorage
from src.services.content_contracts import ContentWrite,SiteConfiguration
from src.models import ContentEntry,WebsiteMedia,ContentMediaLink,WebsiteSettings,Event,Announcement
from PIL import Image
from src.models.sermon import SermonSeries,SermonCategory,SermonMediaAsset
from src.services.sermon_contracts import SermonWrite
from src.services.sermon_storage import MediaStorageService,SermonStorageSettings
from tests.payment_fixtures import TestPaystack
from src.models import DonationCategory

PASSWORD = "Portal-Synthetic!2026"
ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "logs" / "portal_e2e_state.json"
schema = "hcms_portal_e2e_" + uuid4().hex
test_engine = engine.execution_options(schema_translate_map={None: schema})
factory = sessionmaker(bind=test_engine, expire_on_commit=False)
fixture_data = {}
totp_secret = pyotp.random_base32()
MEDIA_DIR=ROOT/"logs"/("portal_assets_"+schema.rsplit("_",1)[-1])
media_storage=LocalWebsiteStorage(MEDIA_DIR)


def drop_fixture_schema(target: str) -> None:
    if not re.fullmatch(r"hcms_portal_e2e_[a-f0-9]{32}", target):
        raise ValueError("Refusing to remove an unrelated schema.")
    with engine.begin() as connection:
        connection.execute(DropSchema(target, cascade=True, if_exists=True))


def cleanup() -> None:
    if STATE.exists():
        recorded = json.loads(STATE.read_text(encoding="utf-8"))
        drop_fixture_schema(recorded["schema"])
        asset_dir=recorded.get('media_dir')
        if asset_dir:
            target=Path(asset_dir).resolve()
            if not target.is_relative_to((ROOT/'logs').resolve()) or not re.fullmatch(r'portal_assets_[a-f0-9]{32}',target.name):raise ValueError('Unsafe fixture media cleanup path.')
            if target.exists():shutil.rmtree(target)
        STATE.unlink()


@asynccontextmanager
async def lifespan(_app):
    # A previous interrupted run can only remove its strictly named fixture.
    cleanup()
    with engine.begin() as connection: connection.execute(CreateSchema(schema))
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps({"schema": schema,"media_dir":str(MEDIA_DIR)}), encoding="utf-8")
    try:
        Base.metadata.create_all(test_engine)
        with factory() as db:
            permissions = {code: Permission(code=code, name=name, module="Fixture", is_active=True) for code, name in (APP | ATT | ADMIN).items()}
            db.add_all(permissions.values())
            officer = {"MEMBERS_VIEW_OWN_MINISTRY", "MINISTRIES_VIEW_OWN", "MINISTRY_LEADERSHIP_VIEW", "ATTENDANCE_VIEW_OWN_MINISTRY", "ATTENDANCE_CREATE_OWN_MINISTRY", "ATTENDANCE_RECORD_OWN_MINISTRY", "ATTENDANCE_CORRECT_OWN_MINISTRY", "ATTENDANCE_CLOSE_SESSION", "ATTENDANCE_EXPORT", "SMS_VIEW_OWN"}
            role_specs = {
                "admin": ("ADMINISTRATOR", "Church Administrator", set(permissions)),
                "secretary": ("CHURCH_SECRETARY", "Church Secretary", {"MEMBERS_VIEW_ALL", "MEMBERS_CREATE", "MEMBERS_EDIT", "ATTENDANCE_VIEW_ALL", "ATTENDANCE_EXPORT"}),
                "overseer": ("GENERAL_OVERSEER", "General Overseer", {"ATTENDANCE_VIEW_ALL", "ATTENDANCE_VIEW_AUDIT", "ATTENDANCE_EXPORT"}),
                "officer": ("MINISTRY_SECRETARY", "Ministry Secretary", officer),
                "teacher": ("SUNDAY_SCHOOL_TEACHER", "Sunday School Teacher", TEACHER_PERMISSIONS),
            }
            officer.update(OWN_EDITOR)
            roles = {name: Role(code=code, name=title, is_active=True, permissions=[permissions[p] for p in grants]) for name, (code, title, grants) in role_specs.items()}
            db.add_all(roles.values())
            ministries = {name: Ministry(code=name.upper(), name=name+" Ministry", is_active=True) for name in ["Youth", "Choir", "Women"]}
            db.add_all(ministries.values())
            classes = {name: SundaySchoolClass(code=name.upper(), name=name+" class", status="ACTIVE") for name in ["Primary", "Juniors"]}
            db.add_all(classes.values()); db.flush()
            hashed = PasswordHasher().hash(PASSWORD)
            account_members={};account_users={}
            for name, role in [("admin", "admin"), ("secretary", "secretary"), ("overseer", "overseer"), ("youth", "officer"), ("multi", "officer"), ("teacher", "teacher")]:
                member = Member(member_no="PORTAL-FIXTURE-"+name.upper(), first_name=name.title(), last_name="Synthetic", status=MemberStatus.ACTIVE)
                db.add(member); db.flush()
                account_members[name]=member
                user = User(username="portal-"+name, email="portal-"+name+"@example.invalid", password_hash=hashed, status=UserStatus.ACTIVE,
                            member_id=member.id, roles=[roles[role]], totp_enabled=name == "youth",
                            totp_secret=TotpService().encrypt_secret(totp_secret) if name == "youth" else None)
                db.add(user); db.flush();account_users[name]=user
                for ministry in ["Youth"] if name == "youth" else ["Youth", "Choir"] if name == "multi" else []:
                    db.add(UserMinistryScope(user_id=user.id, ministry_id=ministries[ministry].id, is_active=True, legacy_attendance_limits=False))
                if name == "teacher": db.add(SundaySchoolUserClassScope(user_id=user.id, class_id=classes["Primary"].id, is_active=True))
            members=[]
            for index in range(30):
                name="Youth" if index<20 else "Choir" if index<25 else "Women"
                member=Member(member_no=f"PORTAL-PERSON-{index:03}",first_name=name,last_name=f"Synthetic{index:03}",
                    phone=f"024555{index:04}",status=MemberStatus.ACTIVE,
                    photo_path="assets/member_photos/fixture-missing.png" if index==0 else None)
                db.add(member);db.flush();members.append(member)
                db.add(MemberMinistry(member_id=member.id,ministry_id=ministries[name].id,is_active=True))
                if index==0:db.add(MemberMinistry(member_id=member.id,ministry_id=ministries["Choir"].id,is_active=True))
            for name in ("youth","multi"):
                db.add(MemberMinistry(member_id=account_members[name].id,ministry_id=ministries["Youth"].id,is_active=True))
            position=MinistryPosition(ministry_id=ministries["Youth"].id,code="COMMUNITY_MENTOR",name="Community Mentor",is_active=True,is_leadership=True)
            vacancy=MinistryPosition(ministry_id=ministries["Youth"].id,code="YOUTH_ORGANIZER",name="Youth Organizer",is_active=True,is_leadership=True)
            db.add_all([position,vacancy]);db.flush()
            db.add(MinistryLeadershipAssignment(ministry_id=ministries["Youth"].id,member_id=members[0].id,
                position_id=position.id,position_name=position.name,position_code=position.code,start_date=date(2026,1,1),is_current=True))
            household=Household(household_name="Synthetic family",household_code="FIXTURE_FAMILY",notes="PRIVATE-HOUSEHOLD-SENTINEL")
            db.add(household);db.flush()
            db.add(HouseholdMember(household_id=household.id,member_id=members[0].id,relationship="CHILD",is_active=True,is_household_head=False))
            for index in range(3):
                cls=classes["Primary" if index<2 else "Juniors"]
                db.add(SundaySchoolStudent(member_id=members[index].id,status="ACTIVE",special_notes="PRIVATE-SCHOOL-SENTINEL"))
                db.flush()
                db.add(SundaySchoolEnrollment(member_id=members[index].id,class_id=cls.id,class_name=cls.name,class_code=cls.code,start_date=date(2026,1,1)))
            db.add(SundaySchoolTeacherAssignment(member_id=account_members["teacher"].id,class_id=classes["Primary"].id,role="TEACHER",start_date=date(2026,1,1)))
            # Published content is synthetic and lives only in this disposable schema.
            key=uuid4().hex;media_storage.put(key,Image.new('RGB',(1200,700),'#0b3151'))
            asset=WebsiteMedia(storage_key=key,alt_text='Synthetic fixture artwork',caption='Synthetic fixture',width=1200,height=700,
                status='PUBLISHED',consent_attested=True,contains_children=False,consent_reference='Synthetic test fixture')
            db.add(asset);db.flush()
            configuration=SiteConfiguration(church_name='HOPFAN',tagline='Synthetic public website fixture',address='Synthetic test location',
                public_email='church@example.invalid',public_phone='0000000000',timezone='UTC',service_times=[dict(id=str(uuid4()),name=name,day_of_week=day,start_time=start,end_time=end,display_order=order) for order,(name,day,start,end) in enumerate([('Sunday Service','SUNDAY','07:00','10:00'),('Wednesday Service','WEDNESDAY','09:00','12:00'),('Friday Evening Service','FRIDAY','18:30','21:00')])])
            db.add(WebsiteSettings(id=1,draft_data=configuration.model_dump(mode='json'),published_data=configuration.model_dump(mode='json'),published_at=datetime.now(timezone.utc)))
            for kind,slug,title in [('HOMEPAGE','home','Synthetic homepage'),('PAGE','about','About HOPFAN'),('PAGE','sunday-school','Sunday School'),
                ('MINISTRY','youth','Youth public ministry'),('LEADERSHIP','synthetic-leader','Synthetic church leader'),('SERMON','fixture-message','Synthetic message'),('GALLERY','fixture-album','Synthetic church gallery')]:
                values=dict(kind=kind,slug=slug,title=title,summary='Approved synthetic public content',body='Synthetic fixture content; no production church facts.',data={'image_id':str(asset.id)})
                if kind=='MINISTRY':values['ministry_id']=ministries['Youth'].id
                if kind=='HOMEPAGE':values['data'].update(hero_headline='A place to belong.',hero_text='Synthetic website design and publication fixture.')
                if kind=='SERMON':values['data'].update(speaker='Synthetic speaker',sermon_date='2026-10-04',scripture_reference='Synthetic scripture')
                if kind=='GALLERY':values['data']['images']=[{'asset_id':str(asset.id),'alt_text':'Synthetic fixture image','caption':'Synthetic church-life fixture'}]
                validated=ContentWrite.model_validate(values);snapshot=validated.model_dump(mode='json',exclude={'expected_updated_at','ministry_id','member_id'})
                entry=ContentEntry(kind=kind,slug=slug,title=title,draft_data=snapshot,published_data=snapshot,status='PUBLISHED',published_at=datetime.now(timezone.utc),ministry_id=validated.ministry_id,created_by=account_users['admin'].id)
                db.add(entry);db.flush();db.add(ContentMediaLink(content_id=entry.id,media_id=asset.id))
            for index in range(1,10):
                slug=f'synthetic-leader-{index}'
                snapshot=ContentWrite.model_validate(dict(kind='LEADERSHIP',slug=slug,title=f'Synthetic leader {index}',summary='Published synthetic ministry responsibility.',data={'public_name':f'Synthetic leader {index}','public_title':'Synthetic ministry leader','display_order':index})).model_dump(mode='json',exclude={'expected_updated_at','ministry_id','member_id'})
                db.add(ContentEntry(kind='LEADERSHIP',slug=slug,title=snapshot['title'],draft_data=snapshot,published_data=snapshot,status='PUBLISHED',published_at=datetime.now(timezone.utc)))
            # Playable sermon files are generated only inside this disposable fixture.
            sermon_storage=MediaStorageService(SermonStorageSettings(root=MEDIA_DIR/'sermons'))
            sample_video=MEDIA_DIR/'synthetic-sermon.mp4';sample_audio=MEDIA_DIR/'synthetic-sermon.wav';sample_image=MEDIA_DIR/'synthetic-thumb.jpg'
            ff_flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=navy:s=640x360:d=15','-f','lavfi','-i','sine=frequency=440:duration=15','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart','-shortest',str(sample_video)],capture_output=True,check=True,timeout=30,creationflags=ff_flags)
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=15','-c:a','pcm_s16le',str(sample_audio)],capture_output=True,check=True,timeout=20,creationflags=ff_flags)
            Image.new('RGB',(1280,720),'#0b3151').save(sample_image)
            series=SermonSeries(name='Synthetic Sermon Series',slug='synthetic-sermon-series',status='PUBLISHED',published_data={'name':'Synthetic Sermon Series','slug':'synthetic-sermon-series','description':'Synthetic playlist fixture','cover_image_id':str(asset.id)},published_at=datetime.now(timezone.utc))
            category=SermonCategory(name='Synthetic Prayer',slug='synthetic-prayer-category',status='PUBLISHED',published_data={'name':'Synthetic Prayer','slug':'synthetic-prayer-category','description':'Synthetic category fixture'},published_at=datetime.now(timezone.utc))
            db.add_all([series,category]);db.flush()
            sermon_id=uuid4();video_id=uuid4();audio_id=uuid4();thumb_id=uuid4()
            values=SermonWrite(title='Synthetic Hosted Sermon',slug='synthetic-hosted-sermon',speaker_name='Synthetic Pastor',sermon_date='2026-10-08',description='Approved synthetic sermon description for browser tests.',short_description='Watch or listen to this synthetic media fixture.',visibility='PUBLIC',featured=True,series_id=series.id,category_id=category.id,tags=['synthetic','prayer'],video_source_type='UPLOADED',video_asset_id=video_id,audio_asset_id=audio_id,thumbnail_asset_id=thumb_id,allow_audio_download=True,allow_video_download=False).editorial().model_dump(mode='json',exclude={'expected_updated_at','member_id','ministry_id'})
            db.add(ContentEntry(id=sermon_id,kind='SERMON',slug=values['slug'],title=values['title'],draft_data=values,published_data=values,status='PUBLISHED',published_at=datetime.now(timezone.utc),created_by=account_users['admin'].id,published_by=account_users['admin'].id));db.flush()
            for aid,kind,path,mime,extension in [(video_id,'VIDEO',sample_video,'video/mp4','mp4'),(audio_id,'AUDIO',sample_audio,'audio/wav','wav'),(thumb_id,'THUMBNAIL',sample_image,'image/jpeg','jpg')]:
                key=f'sermons/{sermon_id}/{aid}.{extension}';sermon_storage.upload(key,path,mime)
                db.add(SermonMediaAsset(id=aid,sermon_id=sermon_id,media_type=kind,storage_provider='LOCAL',storage_key=key,original_filename=path.name,mime_type=mime,file_size=path.stat().st_size,format=extension,duration_seconds=15 if kind!='THUMBNAIL' else None,width=640 if kind=='VIDEO' else 1280 if kind=='THUMBNAIL' else None,height=360 if kind=='VIDEO' else 720 if kind=='THUMBNAIL' else None,processing_status='READY',rights_attested=True,download_allowed=True,quality_label='360p' if kind=='VIDEO' else ''))
            fixture_data.update(sermon_id=str(sermon_id),sermon_slug='synthetic-hosted-sermon',series_slug=series.slug)
            app.state.sermon_storage=sermon_storage

            db.add(DonationCategory(name='Reviewed fixture offering',display_order=0))
            for index in range(1,5):
                db.add(Event(slug=f'synthetic-upcoming-{index}',title=f'Synthetic upcoming event {index}',description='Approved synthetic event summary, used only in the isolated browser fixture.',scope='CHURCH_WIDE',visibility='PUBLIC',status='PUBLISHED',start_datetime=datetime.now(timezone.utc)+timedelta(days=index),location='Synthetic venue',image_id=asset.id if index!=2 else None,published_at=datetime.now(timezone.utc)))
            db.add(Event(slug='synthetic-draft',title='Synthetic private draft event',scope='CHURCH_WIDE',visibility='PUBLIC',status='DRAFT',start_datetime=datetime.now(timezone.utc)+timedelta(days=2)))
            db.add(Event(slug='synthetic-past',title='Synthetic past event',scope='CHURCH_WIDE',visibility='PUBLIC',status='PUBLISHED',start_datetime=datetime.now(timezone.utc)-timedelta(days=4)))
            db.add(Event(slug='fixture-event',title='Synthetic community event',description='A synthetic public event fixture.',scope='CHURCH_WIDE',visibility='PUBLIC',status='PUBLISHED',start_datetime=datetime.now(timezone.utc)+timedelta(days=5),location='Synthetic venue',published_at=datetime.now(timezone.utc)))
            db.add(Announcement(slug='fixture-notice',title='Synthetic announcement',body='An approved synthetic notice.',scope='CHURCH_WIDE',audience='BOTH',status='PUBLISHED',published_at=datetime.now(timezone.utc)))
            db.commit()
            fixture_data.update(ministry_ids={name: str(row.id) for name, row in ministries.items()}, class_ids={name: str(row.id) for name, row in classes.items()}, member_ids=[str(row.id) for row in members])
        yield
    finally:
        cleanup()


app = create_app(OnlineSettings(web_public_origin="", web_portal_origin="http://localhost:3002",
                              web_login_rate_ip_limit=1000, web_login_rate_account_limit=1000, web_csrf_rate_ip_limit=1000))
app.router.lifespan_context = lifespan
app.state.website_storage=media_storage
app.state.payment_provider=TestPaystack()


def database():
    with factory() as db:
        check_api_database_access(db)
        yield db
app.dependency_overrides[get_db] = database


def loopback(request: Request):
    if request.client is None or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(403)


@app.get("/_test/fixtures", dependencies=[Depends(loopback)])
def fixtures(): return fixture_data


@app.get("/_test/totp", dependencies=[Depends(loopback)])
def code(): return {"code": pyotp.TOTP(totp_secret).now()}


@app.post("/_test/expire", dependencies=[Depends(loopback)])
def expire(request: Request):
    cookie = read_session_cookie(request)
    with factory() as db:
        row = db.scalar(select(WebSession).where(WebSession.session_hash == session_hash(cookie)))
        if row is None: raise HTTPException(404)
        row.created_at = datetime.now(timezone.utc)-timedelta(hours=1)
        row.last_activity_at = datetime.now(timezone.utc)-timedelta(minutes=31)
        db.commit()
    return {"expired": True}


@app.get("/_test/ministry/{ministry_id}", dependencies=[Depends(loopback), Depends(require_ministry_permission("ATTENDANCE_VIEW_OWN_MINISTRY"))])
def scope_probe(ministry_id: UUID): return {"allowed": True}


@app.post("/_test/cleanup", dependencies=[Depends(loopback)])
def cleanup_endpoint():
    cleanup()
    return {"cleaned": True}


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["cleanup"]: cleanup()
    else: raise SystemExit("Use this fixture only through the controlled Playwright runner.")


@app.post('/_test/payments/{reference}',dependencies=[Depends(loopback)])
def payment_status(reference:str,status:str):
    if status not in {'success','failed','abandoned','pending'} or reference not in app.state.payment_provider.transactions:raise HTTPException(404)
    app.state.payment_provider.transactions[reference]['status']=status
    return {'configured':True}


_hidden_home_events={}
@app.post('/_test/home-events',dependencies=[Depends(loopback)])
def show_home_events(visible:bool):
    with factory() as db:
        if visible:
            for event_id,status in _hidden_home_events.items():
                event=db.get(Event,event_id)
                if event:event.status=status
            _hidden_home_events.clear()
        else:
            for event in db.scalars(select(Event).where(Event.status=='PUBLISHED',Event.visibility.in_(('PUBLIC','BOTH')),Event.start_datetime>=datetime.now(timezone.utc))):
                _hidden_home_events[event.id]=event.status;event.status='DRAFT'
        db.commit()
    return {'configured':True}


@app.get('/_test/sermon-file/{kind}',dependencies=[Depends(loopback)])
def sermon_file(kind:str):
    from starlette.responses import FileResponse
    files={'video':('synthetic-sermon.mp4','video/mp4'),'audio':('synthetic-sermon.wav','audio/wav'),'thumbnail':('synthetic-thumb.jpg','image/jpeg')}
    if kind not in files:raise HTTPException(404)
    name,mime=files[kind]
    return FileResponse(MEDIA_DIR/name,media_type=mime,filename=name)
