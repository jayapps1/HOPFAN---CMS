"use client";
import { useRef,useState,type ReactNode } from "react";
import Link from "next/link";
import { useParams,usePathname } from "next/navigation";
import { useAuth } from "@/features/auth/auth-provider";
import { useWorkspace } from "@/features/workspace/workspace-provider";
import { useResource } from "@/features/workspace/use-resource";
import { useFilters } from "@/features/workspace/directories";
import { RecordState,Pagination,Empty } from "@/features/workspace/records-ui";
import { Button,Card,Badge,Input,Avatar } from "@/components/ui/primitives";
import { AccessDenied } from "@/components/ui/feedback";
import { api,ApiError } from "@/lib/api/client";
import { canAccess,modules } from "@/lib/permissions";
import { parseSchoolDashboard,parseClasses,parseClass,parseStudents,parseStudent,parseTeachers,parseLessons,parseLesson,parseReports,
  displayDate,storageDate,statusLabel,type Lesson } from "@/lib/api/operations";
import { OperationalModal,FormActions } from "./operational-ui";

export const schoolSections=[
  {id:"classes",label:"Classes",permission:"SUNDAY_SCHOOL_CLASS_VIEW"},
  {id:"students",label:"Students",permission:"SUNDAY_SCHOOL_STUDENT_VIEW"},
  {id:"teachers",label:"Teachers",permission:"SUNDAY_SCHOOL_TEACHER_VIEW"},
  {id:"lessons",label:"Lessons",permission:"SUNDAY_SCHOOL_LESSON_VIEW"},
  {id:"attendance",label:"Attendance",permission:"SUNDAY_SCHOOL_ATTENDANCE_VIEW"},
  {id:"reports",label:"Reports",permission:"SUNDAY_SCHOOL_REPORT_VIEW"},
];
export function SchoolArea({children}:{children:ReactNode}) {
  const {user}=useAuth();const path=usePathname();const module=modules.find(item=>item.id==="sunday-school")!;
  if(!user)return null;
  if(!canAccess(user,module))return <AccessDenied/>;
  const section=schoolSections.find(item=>path.startsWith("/portal/sunday-school/"+item.id));
  if(section&&!user.permissions.includes(section.permission))return <AccessDenied/>;
  return <><nav className="school-navigation" aria-label="Sunday School navigation"><Link href="/portal/sunday-school" aria-current={path==="/portal/sunday-school"?"page":undefined}>Overview</Link>
    {schoolSections.filter(item=>user.permissions.includes(item.permission)).map(item=><Link key={item.id} href={"/portal/sunday-school/"+item.id} aria-current={section?.id===item.id?"page":undefined}>{item.label}</Link>)}</nav>{children}</>;
}
export function SchoolOverview() {
  const workspace=useWorkspace();const {user}=useAuth();
  const data=useResource(user?.permissions.includes("SUNDAY_SCHOOL_CLASS_VIEW")?"/api/v1/sunday-school/dashboard"+(workspace.classId?"?class_id="+workspace.classId:""):null,parseSchoolDashboard);
  return <><Heading title="Sunday School" detail="Your classes, students, lessons and attendance."/><RecordState {...data}/>
    {data.data&&<div className="metric-grid">{Object.entries(data.data).filter(([,value])=>value!==null).map(([key,value])=><Card key={key}><p className="muted">{statusLabel(key)}</p><strong className="metric-value">{value}{key==="rate"?"%":""}</strong></Card>)}</div>}
    <div className="workspace-cards">{schoolSections.filter(item=>user?.permissions.includes(item.permission)).map(item=><Link key={item.id} href={"/portal/sunday-school/"+item.id} className="workspace-card"><h2>{item.label}</h2><p>View your permitted {item.label.toLowerCase()}.</p><span className="card-link">Open workspace →</span></Link>)}</div>
    {user?.permissions.includes("SUNDAY_SCHOOL_LESSON_VIEW")&&<div className="school-overview-section"><h2>Current and upcoming lessons</h2><LessonDirectory compact/></div>}
    {user?.permissions.includes("SUNDAY_SCHOOL_ATTENDANCE_VIEW")&&<RecentClassAttendance/>}
  </>;
}
function Heading({title,detail}:{title:string;detail:string}) {return <div className="page-heading"><div><p className="eyebrow">SUNDAY SCHOOL</p><h1>{title}</h1><p>{detail}</p></div></div>;}
function SearchForm({placeholder="Name or code"}:{placeholder?:string}) {
  const {params,update}=useFilters();
  return <form className="record-filters" onSubmit={event=>{event.preventDefault();update({search:String(new FormData(event.currentTarget).get("search")??"")});}}><label className="search-field">Search<Input name="search" defaultValue={params.get("search")??""} key={params.get("search")} placeholder={placeholder}/></label><Button type="submit" variant="secondary">Search</Button></form>;
}
export function ClassDirectory() {
  const workspace=useWorkspace();const {params,page,update}=useFilters();const query=new URLSearchParams({page:String(page),search:params.get("search")??""});if(workspace.classId)query.set("class_id",workspace.classId);const data=useResource("/api/v1/sunday-school/classes?"+query,parseClasses);
  return <><Heading title="Classes" detail="Explore your permitted teaching spaces."/><SearchForm/><RecordState {...data}/>
    {data.data&&<>{data.data.items.length?<div className="ministry-grid">{data.data.items.map(item=><Link key={item.id} className="card ministry-card" href={"/portal/sunday-school/classes/"+item.id}><Badge tone={item.status==="ACTIVE"?"green":"neutral"}>{statusLabel(item.status)}</Badge><h2>{item.name}</h2><p>{item.description||item.room_location||"Sunday School class"}</p><p>{item.students===null?"Student summary unavailable":item.students+" current enrollments"} · {item.teachers===null?"Teacher summary unavailable":item.teachers+" teachers"}</p><span className="card-link">View class →</span></Link>)}</div>:<Empty title="No classes found">Try another search or ask your coordinator about your class assignment.</Empty>}<Pagination {...data.data} change={value=>update({page:String(value)})}/></>}
  </>;
}
export function ClassProfile() {
  const {classId}=useParams<{classId:string}>();const {user}=useAuth();const data=useResource("/api/v1/sunday-school/classes/"+encodeURIComponent(classId),parseClass);
  return <><Link className="back-link" href="/portal/sunday-school/classes">← Classes</Link><RecordState {...data}/>{data.data&&<><Heading title={data.data.name} detail={data.data.description}/>
    <div className="profile-grid"><Card className="school-class-details"><h2>Class details</h2><p>Recommended ages: {data.data.minimum_age??"Any"} – {data.data.maximum_age??"Any"}</p><p>Room: {data.data.room_location||"Not set"}</p><p>Capacity: {data.data.capacity??"Unlimited"}</p><Badge>{statusLabel(data.data.status)}</Badge></Card>
      <Card className="school-class-details"><h2>Class connections</h2>{data.data.students!==null&&<p>{data.data.students} current enrollments</p>}{data.data.teachers!==null&&<p>{data.data.teachers} current teachers</p>}</Card></div>
    {user?.permissions.includes("SUNDAY_SCHOOL_STUDENT_VIEW")&&<div className="school-overview-section"><h2>Current students</h2><StudentDirectory classId={classId} compact/></div>}
    {user?.permissions.includes("SUNDAY_SCHOOL_TEACHER_VIEW")&&<div className="school-overview-section"><h2>Teacher assignments</h2><TeacherDirectory classId={classId} compact/></div>}
    {user?.permissions.includes("SUNDAY_SCHOOL_LESSON_VIEW")&&<div className="school-overview-section"><h2>Lessons</h2><LessonDirectory classId={classId} compact/></div>}
    {user?.permissions.includes("SUNDAY_SCHOOL_ATTENDANCE_VIEW")&&<RecentClassAttendance classId={classId}/>}
  </>}</>;
}
export function StudentDirectory({classId,compact=false}:{classId?:string;compact?:boolean}) {
  const workspace=useWorkspace();const {params,page,update}=useFilters();const {user}=useAuth();
  const query=new URLSearchParams({page:String(compact?1:page),search:compact?"":params.get("search")??"",status:params.get("studentStatus")??"ACTIVE"});
  const selected=classId??workspace.classId;if(selected)query.set("class_id",selected);
  for(const key of ["minimum_age","maximum_age","gender"])if(params.get(key))query.set(key,params.get(key)!);
  const data=useResource("/api/v1/sunday-school/students?"+query,parseStudents);
  return <>{!compact&&<><Heading title="Students" detail="Existing members enrolled in your permitted classes."/><SearchForm placeholder="Name or member number"/>
    <div className="record-filters"><label>Admission status<select value={params.get("studentStatus")??"ACTIVE"} onChange={event=>update({studentStatus:event.target.value})}>{["ACTIVE","INACTIVE","ALL"].map(value=><option key={value}>{value}</option>)}</select></label>
    <label>Minimum age<Input type="number" min={0} max={125} value={params.get("minimum_age")??""} onChange={event=>update({minimum_age:event.target.value})}/></label>
    <label>Maximum age<Input type="number" min={0} max={125} value={params.get("maximum_age")??""} onChange={event=>update({maximum_age:event.target.value})}/></label>
    {user?.permissions.includes("SUNDAY_SCHOOL_VIEW_ALL")&&<label>Gender<select value={params.get("gender")??""} onChange={event=>update({gender:event.target.value})}><option value="">All genders</option><option value="MALE">Male</option><option value="FEMALE">Female</option></select></label>}</div></>}
    <RecordState {...data}/>{data.data&&<>{data.data.items.length?<div className="school-people">{data.data.items.map(item=><Link className="card school-person" key={item.id} href={"/portal/sunday-school/students/"+item.member_id}><Avatar name={item.full_name}/><div><h3>{item.full_name}</h3><p>{item.member_no} · {item.class_name||"Not assigned"}</p><p>{item.age===null?"Age not provided":"Age "+item.age}</p></div><Badge>{statusLabel(item.status)}</Badge></Link>)}</div>:<Empty title="No students found">Adjust the filters to find a current enrollment.</Empty>}{!compact&&<Pagination {...data.data} change={value=>update({page:String(value)})}/>}</>}
  </>;
}
export function StudentProfile() {
  const {memberId}=useParams<{memberId:string}>();const data=useResource("/api/v1/sunday-school/students/"+encodeURIComponent(memberId),parseStudent);
  return <><Link className="back-link" href="/portal/sunday-school/students">← Students</Link><RecordState {...data}/>{data.data&&<><Heading title={data.data.full_name} detail={data.data.member_no+" · "+data.data.class_name}/>
    <div className="profile-grid"><Card className="school-class-details"><h2>Student summary</h2><p>Age: {data.data.age??"Not provided"}</p><p>Admission: {statusLabel(data.data.status)}</p>{data.data.attendance_rate!==undefined&&<p>Attendance rate: {data.data.attendance_rate===null?"Unavailable":data.data.attendance_rate+"%"}</p>}</Card>
    {data.data.guardians&&<Card className="school-class-details"><h2>Guardian contacts</h2>{data.data.guardians.length?data.data.guardians.map((guardian,index)=><div className="guardian-contact" key={index}><h3>{guardian.full_name}</h3><p>{statusLabel(guardian.relationship)}</p><p>{guardian.phone||"Contact not provided"}</p><p>SMS consent: {guardian.can_receive_sms?"Yes":"No"}</p></div>):<p>No guardian contact is recorded.</p>}</Card>}
    <Card className="school-class-details"><h2>Enrollment history</h2>{data.data.history?.map((item,index)=><p key={index}>{item.class_name} · {displayDate(item.start_date)}{item.end_date?" to "+displayDate(item.end_date):" · Current"}</p>)}</Card></div>
  </>}</>;
}
export function TeacherDirectory({classId,compact=false}:{classId?:string;compact?:boolean}) {
  const workspace=useWorkspace();const {params,page,update}=useFilters();const query=new URLSearchParams({page:String(compact?1:page),search:compact?"":params.get("search")??""});
  if(classId??workspace.classId)query.set("class_id",(classId??workspace.classId)!);
  const data=useResource("/api/v1/sunday-school/teachers?"+query,parseTeachers);
  return <>{!compact&&<><Heading title="Teachers" detail="Current teaching assignments in your permitted classes."/><SearchForm/></>}<RecordState {...data}/>
    {data.data&&<>{data.data.items.length?<div className="school-people">{data.data.items.map(item=><article className="card school-person" key={item.id}><Avatar name={item.full_name}/><div><h3>{item.full_name}</h3><p>{item.role_label} · {item.class_name}</p><p>From {displayDate(item.start_date)}</p></div></article>)}</div>:<Empty title="No teaching assignments">No current teachers are recorded in this selection.</Empty>}{!compact&&<Pagination {...data.data} change={value=>update({page:String(value)})}/>}</>}
  </>;
}
export function LessonDirectory({classId,compact=false}:{classId?:string;compact?:boolean}) {
  const {user}=useAuth();const workspace=useWorkspace();const {params,page,update}=useFilters();const [editing,setEditing]=useState<Lesson|"new"|null>(null);
  const query=new URLSearchParams({page:String(compact?1:page),search:compact?"":params.get("search")??"",view:params.get("view")??(compact?"UPCOMING":"ALL")});
  if(classId??workspace.classId)query.set("class_id",(classId??workspace.classId)!);
  const data=useResource("/api/v1/sunday-school/lessons?"+query,parseLessons);
  return <>{!compact&&<><div className="page-heading"><div><p className="eyebrow">SUNDAY SCHOOL</p><h1>Lessons</h1><p>Prepare, publish and review permitted lesson plans.</p></div>{user?.permissions.includes("SUNDAY_SCHOOL_LESSON_CREATE")&&<Button onClick={()=>setEditing("new")}>Create lesson</Button>}</div><SearchForm placeholder="Lesson title or topic"/>
      <div className="record-filters"><label>Lesson view<select value={params.get("view")??"ALL"} onChange={event=>update({view:event.target.value})}>{["ALL","UPCOMING","RECENT","DRAFT","PUBLISHED","ARCHIVED"].map(value=><option key={value} value={value}>{statusLabel(value)}</option>)}</select></label></div></>}
    <RecordState {...data}/>{data.data&&<>{data.data.items.length?<div className="lesson-list">{data.data.items.map(item=><Card key={item.id} className="lesson-card"><div className="card-heading"><Badge tone={item.status==="PUBLISHED"?"green":"neutral"}>{statusLabel(item.status)}</Badge><strong>{displayDate(item.lesson_date)}</strong></div><h2>{item.title}</h2><p>{item.topic}{item.scripture_reference?" · "+item.scripture_reference:""}</p><p className="muted">{item.applies_to_all?"All Sunday School classes":item.classes.map(cls=>cls.name).join(", ")}</p><div className="lesson-content">{item.objective&&<><h3>Objective</h3><p>{item.objective}</p></>}{item.lesson_summary&&<><h3>Lesson summary</h3><p>{item.lesson_summary}</p></>}{item.teacher_notes&&<><h3>Teacher notes</h3><p>{item.teacher_notes}</p></>}</div>{item.can_edit&&!compact&&<Button variant="secondary" onClick={()=>setEditing(item)}>Edit lesson</Button>}</Card>)}</div>:<Empty title="No lessons found">Try another lesson view or class workspace.</Empty>}{!compact&&<Pagination {...data.data} change={value=>update({page:String(value)})}/>}</>}
    {editing&&<LessonEditor lesson={editing==="new"?null:editing} close={()=>setEditing(null)} saved={()=>{setEditing(null);data.retry();}}/>}
  </>;
}
function LessonEditor({lesson,close,saved}:{lesson:Lesson|null;close:()=>void;saved:()=>void}) {
  const workspace=useWorkspace();const {user}=useAuth();const [all,setAll]=useState(lesson?.applies_to_all??false);
  const [classes,setClasses]=useState<string[]>(lesson?.classes.map(cls=>cls.id)??(workspace.classId?[workspace.classId]:[]));
  const [pending,setPending]=useState(false);const [error,setError]=useState("");const busy=useRef(false);
  return <OperationalModal title={lesson?"Edit lesson":"Create lesson"} description="Select permitted classes and save a draft, published or archived lesson." close={()=>{if(!pending)close();}}>
    <form className="operational-form" onSubmit={async event=>{event.preventDefault();if(busy.current)return;busy.current=true;setPending(true);setError("");
      try{const fields=new FormData(event.currentTarget);const body={title:String(fields.get("title")),lesson_date:storageDate(String(fields.get("lesson_date"))),status:String(fields.get("status")),
        topic:String(fields.get("topic")),scripture_reference:String(fields.get("scripture_reference")),objective:String(fields.get("objective")),lesson_summary:String(fields.get("lesson_summary")),teacher_notes:String(fields.get("teacher_notes")),all_classes:all,class_ids:all?[]:classes,expected_updated_at:lesson?.updated_at??null};
        await api.mutate("/api/v1/sunday-school/lessons"+(lesson?"/"+lesson.id:""),body,parseLesson,lesson?"PATCH":"POST");saved();}
      catch(error){setError(error instanceof ApiError||error instanceof Error?error.message:"Unable to save lesson.");}finally{busy.current=false;setPending(false);}}}>
      <label>Title<Input name="title" required defaultValue={lesson?.title} maxLength={200}/></label>
      <label>Lesson date (DD/MM/YYYY)<Input name="lesson_date" required defaultValue={displayDate(lesson?.lesson_date??new Date().toISOString())} inputMode="numeric"/></label>
      <label>Topic<Input name="topic" defaultValue={lesson?.topic} maxLength={200}/></label><label>Scripture reference<Input name="scripture_reference" defaultValue={lesson?.scripture_reference} maxLength={200}/></label>
      {(["objective","lesson_summary","teacher_notes"] as const).map(key=><label key={key}>{statusLabel(key)}<textarea name={key} defaultValue={lesson?.[key]} rows={3} maxLength={10000}/></label>)}
      <label>Lesson status<select aria-label="Lesson status" name="status" defaultValue={lesson?.status??"DRAFT"}>{["DRAFT","PUBLISHED","ARCHIVED"].map(value=><option key={value}>{value}</option>)}</select></label>
      {user?.permissions.includes("SUNDAY_SCHOOL_VIEW_ALL")&&<label className="checkbox-label"><input type="checkbox" checked={all} onChange={event=>setAll(event.target.checked)}/>All Sunday School classes</label>}
      {!all&&<fieldset className="class-choices"><legend>Classes</legend>{workspace.options.map(cls=><label className="checkbox-label" key={cls.id}><input type="checkbox" checked={classes.includes(cls.id)} onChange={event=>setClasses(previous=>event.target.checked?[...previous,cls.id]:previous.filter(id=>id!==cls.id))}/>{cls.name}</label>)}</fieldset>}
      <FormActions pending={pending} error={error} close={close} label={lesson?"Save lesson":"Create lesson"}/>
    </form></OperationalModal>;
}
export function SchoolReports() {
  const workspace=useWorkspace();const {params,update,page}=useFilters();const {user}=useAuth();const query=new URLSearchParams({kind:params.get("kind")??"classes",page:String(page)});
  if(workspace.classId)query.set("class_id",workspace.classId);
  const data=useResource("/api/v1/sunday-school/reports/attendance?"+query,parseReports);
  const [exporting,setExporting]=useState(false);const [exportError,setExportError]=useState("");
  const exportCsv=async()=>{if(exporting)return;setExporting(true);setExportError("");try{const text=await api.csv("/api/v1/sunday-school/reports/attendance.csv?"+query);const url=URL.createObjectURL(new Blob([text],{type:"text/csv;charset=utf-8"}));const link=document.createElement("a");link.href=url;link.download="sunday-school-attendance.csv";link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(error){setExportError(error instanceof ApiError?error.message:"Unable to export this report.");}finally{setExporting(false);}};
  return <><Heading title="Reports" detail="Recorded attendance from closed class sessions."/><div className="record-filters"><label>Report<select value={params.get("kind")??"classes"} onChange={event=>update({kind:event.target.value})}><option value="classes">Attendance by class</option><option value="dates">Attendance by date</option>{user?.permissions.includes("SUNDAY_SCHOOL_STUDENT_VIEW")&&<option value="students">Attendance by student</option>}</select></label></div>{user?.permissions.includes("SUNDAY_SCHOOL_REPORT_EXPORT")&&<Button variant="secondary" pending={exporting} onClick={()=>{void exportCsv();}}>Export CSV</Button>}<RecordState {...data}/>{exportError&&<p role="alert">{exportError}</p>}
    {data.data&&<>{data.data.items.length?<div className="report-list">{data.data.items.map(item=><Card className="report-card" key={item.id}><h2>{item.label}</h2><p>{item.member_no??""}</p><div className="report-values"><span>{item.eligible} eligible</span><span>{item.present} present</span><span>{item.late} late</span><span>{item.excused} excused</span><span>{item.absent} absent</span><strong>{item.rate===null?"Rate unavailable":item.rate+"%"}</strong></div></Card>)}</div>:<Empty title="No closed attendance found">Close a permitted class session to include its recorded attendance.</Empty>}<Pagination {...data.data} change={value=>update({page:String(value)})}/></>}
  </>;
}
function RecentClassAttendance({classId}:{classId?:string}) {
  const workspace=useWorkspace();const selected=classId??workspace.classId;
  const data=useResource("/api/v1/sunday-school/attendance/sessions?page_size=5"+(selected?"&class_id="+selected:""),parseSchoolSessions);
  return <div className="school-overview-section"><h2>Recent class attendance</h2><RecordState {...data}/>{data.data?.items.map(item=><Link className="card session-card-row" key={item.id} href={"/portal/sunday-school/attendance/"+item.id}><div><h3>{item.title}</h3><p>{item.context_name} · {displayDate(item.session_date)}</p></div><Badge tone={item.sessionState==="OPEN"?"green":"neutral"}>{statusLabel(item.sessionState)}</Badge></Link>)}</div>;
}
import { parseSchoolSessions } from "@/lib/api/operations";
