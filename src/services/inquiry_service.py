"""Private intake and explicit, atomic visitor conversion through MemberService."""
import hashlib,json
from sqlalchemy import select,func,or_,text
from sqlalchemy.dialects.postgresql import insert
from src.models import Member,User,UserStatus
from src.models.content import PublicInquiry,WebsiteSettings
from src.services.content_base import ContentBase,ContentError,ContentDenied,ContentMissing,ContentConflict,check_version,ident,now
from src.services.content_contracts import IntakeWrite,SiteConfiguration
from src.services.web_rate_limit_service import WebRateLimitService

class InquiryService(ContentBase):
    @staticmethod
    def visible(access,stmt,kind=None):
        if kind=='PRAYER':
            access.require_permission('PRAYER_REQUEST_VIEW')
            return stmt.where(PublicInquiry.kind=='PRAYER')
        stmt=stmt.where(PublicInquiry.kind!='PRAYER')
        if access.has('VISITOR_VIEW_ALL'):return stmt
        access.require_permission('VISITOR_VIEW_OWN')
        return stmt.where(PublicInquiry.assigned_to==access.user_id)
    def list(self,kind='VISITOR',search='',status='ALL',limit=25,offset=0):
        with self._db() as (db,access):
            stmt=self.visible(access,select(PublicInquiry),kind).where(PublicInquiry.kind==kind)
            if status!='ALL':stmt=stmt.where(PublicInquiry.status==status)
            if search:
                pattern='%'+search.replace('%','\\%').replace('_','\\_')+'%'
                stmt=stmt.where(or_(PublicInquiry.first_name.ilike(pattern,escape='\\'),PublicInquiry.last_name.ilike(pattern,escape='\\'),PublicInquiry.email.ilike(pattern,escape='\\')))
            total=db.scalar(select(func.count()).select_from(stmt.subquery()))
            rows=db.scalars(stmt.order_by(PublicInquiry.created_at.desc(),PublicInquiry.id).limit(min(limit,100)).offset(offset))
            return dict(total=total,rows=[self.dto(row) for row in rows])
    @staticmethod
    def dto(row):
        keys=('id','kind','first_name','last_name','phone','email','message','private_notes','status','contact_permission','preferred_contact','visit_date','assigned_to','converted_member_id','created_at','updated_at')
        return {key:str(getattr(row,key)) if key in ('id','assigned_to','converted_member_id') and getattr(row,key) is not None else getattr(row,key) for key in keys}
    def _get(self,db,access,inquiry_id):
        row=db.scalar(select(PublicInquiry).where(PublicInquiry.id==ident(inquiry_id)).with_for_update().execution_options(populate_existing=True))
        if not row:raise ContentMissing('Inquiry not found.')
        permitted=self.visible(access,select(PublicInquiry.id),row.kind)
        if not db.scalar(permitted.where(PublicInquiry.id==row.id)):raise ContentDenied('Inquiry is not assigned.')
        return row
    def get(self,inquiry_id):
        with self._db() as (db,access):return self.dto(self._get(db,access,inquiry_id))
    def update(self,inquiry_id,data):
        with self._db() as (db,access):
            row=self._get(db,access,inquiry_id)
            access.require_permission('PRAYER_REQUEST_EDIT' if row.kind=='PRAYER' else 'VISITOR_EDIT')
            check_version(row,data['expected_updated_at'])
            if row.status=='CONVERTED':raise ContentConflict('A converted visitor keeps its Member link.')
            if data.get('assigned_to')!=row.assigned_to:
                access.require_permission('VISITOR_ASSIGN')
                if row.kind=='PRAYER':raise ContentDenied('Pastoral assignments use explicit pastoral administration.')
                actor=db.get(User,data['assigned_to']) if data.get('assigned_to') else None
                if data.get('assigned_to') and (not actor or actor.status!=UserStatus.ACTIVE):raise ContentError('Choose an active assignee.')
            row.status=data['status'];row.private_notes=data['private_notes'];row.assigned_to=data.get('assigned_to');row.updated_at=now()
            self.audit(db,access,row.kind,row.id,'INQUIRY_UPDATED',status=row.status);db.commit();return self.dto(row)
    def assignees(self):
        with self._db('VISITOR_ASSIGN') as (db,access):
            return [dict(id=str(row.id),name=row.username) for row in db.scalars(select(User).where(User.status==UserStatus.ACTIVE).order_by(User.username).limit(100))]
    @staticmethod
    def matching(db,row):
        clauses=[]
        if row.email:clauses.append(func.lower(Member.email)==row.email.lower())
        phone=''.join(char for char in row.phone if char.isdigit())
        if phone:clauses.append(func.regexp_replace(Member.phone,'[^0-9]','','g')==phone)
        if row.first_name and row.last_name:clauses.append((func.lower(Member.first_name)==row.first_name.lower())&(func.lower(Member.last_name)==row.last_name.lower()))
        return db.scalars(select(Member).where(or_(*clauses)).limit(10)).all() if clauses else []
    def candidates(self,inquiry_id):
        with self._db('VISITOR_CONVERT') as (db,access):
            access.require_permission('MEMBERS_VIEW_ALL');row=self._get(db,access,inquiry_id)
            return [dict(id=str(member.id),name=member.full_name,member_no=member.member_no) for member in self.matching(db,row)]
    def convert(self,inquiry_id,data):
        from src.services.member_service import MemberService
        from contextlib import contextmanager
        with self._db('VISITOR_CONVERT') as (db,access):
            access.require_permission('MEMBERS_VIEW_ALL')
            row=self._get(db,access,inquiry_id);check_version(row,data['expected_updated_at'])
            if row.kind!='VISITOR' or row.status=='CONVERTED' or not data['confirm']:raise ContentConflict('Review and confirm a visitor conversion.')
            db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':MemberService.MEMBER_NUMBER_LOCK})
            matches=self.matching(db,row)
            existing=data.get('existing_member_id')
            if existing:
                member=db.get(Member,ident(existing))
                if not member or member.id not in {item.id for item in matches}:raise ContentError('Choose a reviewed matching Member.')
            else:
                access.require_permission('MEMBERS_CREATE')
                if matches:raise ContentConflict('A matching Member exists. Link the reviewed existing record.')
                if not row.first_name or not row.last_name:raise ContentError('A full reviewed name is required for Member registration.')
                @contextmanager
                def borrowed():yield db
                saved=MemberService(access.user_id,borrowed).create_member(dict(first_name=row.first_name,last_name=row.last_name,
                    email=row.email,phone=row.phone,date_joined=now().date(),status='ACTIVE'),commit=False)
                member=db.get(Member,ident(saved['id']))
            row.converted_member_id=member.id;row.status='CONVERTED';row.updated_at=now()
            self.audit(db,access,'VISITOR',row.id,'VISITOR_CONVERTED',member_id=str(member.id));db.commit();return self.dto(row)
    @staticmethod
    def submit(db,kind,data,peer):
        values=IntakeWrite.model_validate(data)
        WebRateLimitService.consume(db,[('public-intake-ip',peer,5,600)])
        if values.website:return
        settings=db.get(WebsiteSettings,1)
        configuration=SiteConfiguration.model_validate(settings.published_data if settings and settings.published_data else {})
        flag={'VISITOR':'visitor_form_enabled','PRAYER':'prayer_form_enabled','CONTACT':'contact_form_enabled'}[kind]
        if not getattr(configuration,flag):raise ContentMissing('Public submission is unavailable.')
        if kind=='PRAYER' and not values.message.strip():raise ContentError('Enter a prayer request.')
        if kind!='PRAYER' and not values.first_name.strip():raise ContentError('Enter your name.')
        if values.preferred_contact=='EMAIL' and not values.email or values.preferred_contact=='PHONE' and not values.phone:raise ContentError('Provide the selected contact method.')
        payload=values.model_dump(mode='json',exclude={'website'})
        digest=hashlib.sha256((kind+now().date().isoformat()+json.dumps(payload,sort_keys=True)).encode()).hexdigest()
        raw=values.model_dump(exclude={'website'})
        key=db.scalar(insert(PublicInquiry).values(kind=kind,dedupe_key=digest,**raw).on_conflict_do_nothing(index_elements=[PublicInquiry.dedupe_key]).returning(PublicInquiry.id))
        if key:ContentBase.audit(db,None,kind,key,'PUBLIC_INQUIRY_RECEIVED')
        db.commit()
