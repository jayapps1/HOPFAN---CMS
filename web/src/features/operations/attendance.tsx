"use client";
import { useRef,useState } from "react";
import Link from "next/link";
import { useParams,useRouter } from "next/navigation";
import { api,ApiError } from "@/lib/api/client";
import { useAuth } from "@/features/auth/auth-provider";
import { useResource } from "@/features/workspace/use-resource";
import { useWorkspace } from "@/features/workspace/workspace-provider";
import { useFilters } from "@/features/workspace/directories";
import { RecordState,Pagination,Empty,PrivateAvatar } from "@/features/workspace/records-ui";
import { Button,Input,Badge } from "@/components/ui/primitives";
import { ErrorMessage } from "@/components/ui/feedback";
import { STATUS_CODES,statusLabel,displayDate,storageDate,parseSessions,parseSchoolSessions,parseSession,parseSchoolSession,
  parseRoster,parseMark,parseAttendanceOptions,parseLessons,type Session,type RosterRow,type AttendanceStatus,type MarkResult } from "@/lib/api/operations";
import { OperationalModal,SummaryCards,FormActions } from "./operational-ui";

const failure=(error:unknown)=>error instanceof ApiError?error.message:error instanceof Error?error.message:"Unable to save. Please try again.";
const prefix=(school:boolean)=>school?"/api/v1/sunday-school/attendance":"/api/v1/attendance";
const route=(school:boolean)=>school?"/portal/sunday-school/attendance":"/portal/attendance";
export function AttendanceDirectory({ school=false }: {school?:boolean}) {
  const {user}=useAuth();const workspace=useWorkspace();const {params,update,page}=useFilters();
  const router=useRouter();const [creating,setCreating]=useState(false);
  const query=new URLSearchParams({page:String(page),page_size:"25",search:params.get("search")??"",state:params.get("state")??"ALL"});
  const context=school?workspace.classId:workspace.ministryId;
  if(context)query.set(school?"class_id":"ministry_id",context);
  if(!school && params.get("type"))query.set("session_type",params.get("type")!);
  for(const key of ["date_from","date_to"])if(params.get(key))query.set(key,params.get(key)!);
  const [filterError,setFilterError]=useState("");
  const resource=useResource(prefix(school)+"/sessions?"+query,school?parseSchoolSessions:parseSessions);
  const options=useResource(!school?"/api/v1/attendance/options":null,parseAttendanceOptions);
  const canCreate=school?user?.permissions.includes("SUNDAY_SCHOOL_ATTENDANCE_CREATE"):options.data?.can_create;
  return <>
    <div className="page-heading"><div><p className="eyebrow">{school?"SUNDAY SCHOOL":"CHURCH OPERATIONS"}</p><h1>{school?"Class attendance":"Attendance"}</h1><p>Open a session, record attendance and review its summary.</p></div>
    {canCreate&&<Button onClick={()=>setCreating(true)}>Create session</Button>}</div>
    <form className="record-filters" onSubmit={event=>{event.preventDefault();const fields=new FormData(event.currentTarget);try{update({search:String(fields.get("search")??""),date_from:fields.get("date_from")?storageDate(String(fields.get("date_from"))):"",date_to:fields.get("date_to")?storageDate(String(fields.get("date_to"))):""});setFilterError("");}catch(error){setFilterError(failure(error));}}}>
      <label className="search-field">Search<Input name="search" key={params.get("search")} defaultValue={params.get("search")??""} placeholder="Session title" /></label><Button type="submit" variant="secondary">Search</Button>
      <label>Session state<select value={params.get("state")??"ALL"} onChange={event=>update({state:event.target.value})}>{["ALL","DRAFT","OPEN","CLOSED",...(!school?["LOCKED"]:[])].map(value=><option key={value} value={value}>{statusLabel(value)}</option>)}</select></label>
      {!school&&options.data&&<label>Session type<select value={params.get("type")??""} onChange={event=>update({type:event.target.value})}><option value="">All types</option>{options.data.session_types.map(value=><option value={value} key={value}>{statusLabel(value)}</option>)}</select></label>}
      <label>From (DD/MM/YYYY)<Input name="date_from" placeholder="DD/MM/YYYY" defaultValue={params.get("date_from")?displayDate(params.get("date_from")!):""} key={params.get("date_from")} inputMode="numeric"/></label>
      <label>To (DD/MM/YYYY)<Input name="date_to" placeholder="DD/MM/YYYY" defaultValue={params.get("date_to")?displayDate(params.get("date_to")!):""} key={params.get("date_to")} inputMode="numeric"/></label>
    </form>{filterError&&<ErrorMessage message={filterError}/>}<RecordState {...resource}/>
    {resource.data&&<>{!resource.data.items.length?<Empty title="No attendance sessions">Try another filter or create a permitted session.</Empty>:<div className="session-list">{resource.data.items.map(session=><Link key={session.id} className="card session-card-row" href={route(school)+"/"+session.id+(context?"?"+(school?"schoolClass":"ministry")+"="+context:"")}>
      <div><Badge tone={session.sessionState==="OPEN"?"green":"neutral"}>{statusLabel(session.sessionState)}</Badge><h2>{session.title}</h2><p>{session.context_name} · {statusLabel(session.session_type)}</p></div><div><strong>{displayDate(session.session_date)}</strong>{session.stats&&<p>{session.stats.present+session.stats.late} attended · {session.stats.eligible} eligible</p>}<span className="card-link">Open attendance →</span></div>
    </Link>)}</div>}<Pagination {...resource.data} change={value=>update({page:String(value)})}/></>}
    {creating&&<CreateAttendance school={school} globalCreate={options.data?.can_create_global??false} close={()=>setCreating(false)} saved={id=>router.push(route(school)+"/"+id)}/>}
  </>;
}
function CreateAttendance({school,globalCreate,close,saved}:{school:boolean;globalCreate:boolean;close:()=>void;saved:(id:string)=>void}) {
  const workspace=useWorkspace();const options=useResource(!school?"/api/v1/attendance/options":null,parseAttendanceOptions);
  const [kind,setKind]=useState(school?"SUNDAY_SCHOOL":globalCreate?"SUNDAY_SERVICE":"MINISTRY_MEETING");
  const [scope,setScope]=useState(kind==="SUNDAY_SERVICE"?"GLOBAL":"MINISTRY");
  const [selected,setSelected]=useState(school?workspace.classId??workspace.options[0]?.id??"":workspace.ministryId??"");
  const [lesson,setLesson]=useState("");const [error,setError]=useState("");const [pending,setPending]=useState(false);const busy=useRef(false);
  const lessons=useResource(school&&selected?"/api/v1/sunday-school/lessons?view=PUBLISHED&class_id="+selected:null,parseLessons);
  const available=school?workspace.options:options.data?.create_ministries??[];
  const submit=async(event:React.FormEvent<HTMLFormElement>)=>{
    event.preventDefault();if(busy.current)return;busy.current=true;setPending(true);setError("");
    try {
      const fields=new FormData(event.currentTarget);const date=storageDate(String(fields.get("date")));
      const context=selected||available[0]?.id;
      const body=school?{class_id:context,session_date:date,title:String(fields.get("title")),lesson_id:lesson||null,open_now:fields.get("sessionState")==="OPEN"}
        :{title:String(fields.get("title")),description:String(fields.get("description")??""),session_date:date,session_type:kind,
          scope_type:kind==="SUNDAY_SERVICE"?"GLOBAL":scope,ministry_id:kind==="SUNDAY_SERVICE"||scope==="GLOBAL"?null:context,state:String(fields.get("sessionState"))};
      const result=await api.mutate(prefix(school)+"/sessions",body,school?parseSchoolSession:parseSession);saved(result.id);
    } catch(error){setError(failure(error));}finally{busy.current=false;setPending(false);}
  };
  return <OperationalModal title={school?"Create class attendance":"Create attendance session"} description={school?"Plan or open attendance for a permitted class.":"Sunday Service uses one shared whole-church roster."} close={()=>{if(!pending)close();}}>
    <form onSubmit={submit} className="operational-form">
      {!school&&<label>Session type<select aria-label="Session type" value={kind} onChange={event=>{const value=event.target.value;setKind(value);setScope(value==="SUNDAY_SERVICE"?"GLOBAL":"MINISTRY");setSelected(value==="SUNDAY_SERVICE"?"":workspace.ministryId??"");}}>
        {(options.data?.session_types??[]).filter(type=>options.data?.can_create_global||type!=="SUNDAY_SERVICE").map(type=><option value={type} key={type}>{statusLabel(type)}</option>)}</select></label>}
      <label>Title<Input name="title" required={!school} maxLength={school?200:150} placeholder={school?"Optional class session title":"Sunday Service or ministry meeting"}/></label>
      <label>Date (DD/MM/YYYY)<Input name="date" defaultValue={displayDate(new Date().toISOString())} placeholder="DD/MM/YYYY" inputMode="numeric" required/></label>
      {!school&&kind!=="SUNDAY_SERVICE"&&kind!=="MINISTRY_MEETING"&&options.data?.can_create_global&&<label>Scope<select value={scope} onChange={event=>setScope(event.target.value)}><option value="MINISTRY">Ministry</option><option value="GLOBAL">Whole church</option></select></label>}
      {(school||kind!=="SUNDAY_SERVICE"&&scope==="MINISTRY")&&<label>{school?"Class":"Ministry"}{available.length===1?<strong>{available[0].name}</strong>:<select aria-label={school?"Class":"Ministry"} required value={selected} onChange={event=>{setSelected(event.target.value);setLesson("");}}><option value="">Choose {school?"class":"ministry"}</option>{available.map(option=><option key={option.id} value={option.id}>{option.name}</option>)}</select>}</label>}
      {school&&<label>Lesson (optional)<select value={lesson} onChange={event=>setLesson(event.target.value)}><option value="">No lesson selected</option>{lessons.data?.items.map(item=><option key={item.id} value={item.id}>{item.title} · {displayDate(item.lesson_date)}</option>)}</select></label>}
      {!school&&<label>Description<textarea name="description" rows={3} maxLength={10000}/></label>}
      <label>Session state<select aria-label="Session state" name="sessionState" defaultValue="OPEN"><option value="OPEN">Open now</option><option value="DRAFT">Planned / Draft</option></select></label>
      <FormActions pending={pending} error={error} close={close} label="Create session"/>
    </form></OperationalModal>;
}
export function AttendanceSession({school=false}:{school?:boolean}) {
  const {sessionId}=useParams<{sessionId:string}>();const workspace=useWorkspace();const {params,update,page}=useFilters();
  const min=school?null:workspace.ministryId;const suffix=min?"?ministry_id="+min:"";
  const session=useResource(prefix(school)+"/sessions/"+encodeURIComponent(sessionId)+suffix,school?parseSchoolSession:parseSession);
  const query=new URLSearchParams({page:String(page),page_size:"25",search:params.get("search")??"",status:params.get("status")??"ALL"});
  if(min)query.set("ministry_id",min);
  const roster=useResource(session.data?prefix(school)+"/sessions/"+encodeURIComponent(sessionId)+"/roster?"+query:null,parseRoster);
  const [transition,setTransition]=useState<string|null>(null);
  const saved=(result:MarkResult)=>{
    if(params.get("status") && params.get("status")!=="ALL")roster.retry();
    else roster.update(data=>({...data,items:data.items.map(row=>row.id===result.row.id?result.row:row)}));
    session.update(data=>({...data,stats:result.summary}));
  };
  return <><Link className="back-link" href={route(school)}>← Attendance sessions</Link><RecordState {...session}/>
    {session.data&&<><div className="page-heading"><div><p className="eyebrow">{session.data.context_name} · {displayDate(session.data.session_date)}</p><h1>{session.data.title}</h1><p>{statusLabel(session.data.session_type)}</p></div><Badge tone={session.data.sessionState==="OPEN"?"green":"neutral"}>{statusLabel(session.data.sessionState)}</Badge></div>
      <div className="live-actions">{Object.entries(session.data.actions).filter(([,allowed])=>allowed).map(([action])=><Button key={action} variant={action==="open"?"primary":"secondary"} onClick={()=>setTransition(action)}>{statusLabel(action)} session</Button>)}</div>
      {session.data.stats&&<SummaryCards stats={session.data.stats}/>}
      {session.data.sessionState!=="OPEN"&&<p className="state-notice">{session.data.sessionState==="DRAFT"?"Open this session before marking attendance.":"Normal marking has stopped. Permitted corrections require a reason."}</p>}
      <form className="record-filters" onSubmit={event=>{event.preventDefault();update({search:String(new FormData(event.currentTarget).get("search")??"")});}}>
        <label className="search-field">Find a person<Input name="search" key={params.get("search")} defaultValue={params.get("search")??""} placeholder="Name or member number"/></label><Button type="submit" variant="secondary">Search</Button>
        <label>Attendance status<select value={params.get("status")??"ALL"} onChange={event=>update({status:event.target.value})}>{["ALL","UNMARKED",...STATUS_CODES].map(value=><option key={value} value={value}>{statusLabel(value)}</option>)}</select></label>
        <Button type="button" variant="ghost" onClick={()=>{roster.retry();session.retry();}}>Refresh roster</Button>
      </form><RecordState {...roster}/>
      {roster.data&&<>{roster.data.items.length?<div className="attendance-roster">{roster.data.items.map(row=><AttendancePerson key={row.id} row={row} school={school} sessionId={sessionId} suffix={suffix} saved={saved}/>)}</div>:<Empty title="No roster members found">Try another search or status filter.</Empty>}<Pagination {...roster.data} change={value=>update({page:String(value)})}/></>}
      {transition&&<SessionTransition school={school} session={session.data} action={transition} close={()=>setTransition(null)} saved={result=>{session.update(()=>result);roster.retry();setTransition(null);}}/>}
    </>}</>;
}
function AttendancePerson({row,school,sessionId,suffix,saved}:{row:RosterRow;school:boolean;sessionId:string;suffix:string;saved:(result:MarkResult)=>void}) {
  const [pending,setPending]=useState(false);const busy=useRef(false);const [error,setError]=useState("");const [correcting,setCorrecting]=useState<AttendanceStatus|null>(null);
  const mark=async(status:AttendanceStatus)=>{
    if(busy.current)return;if(row.record_id){setCorrecting(status);return;}
    busy.current=true;setPending(true);setError("");
    try{saved(await api.mutate(prefix(school)+"/sessions/"+sessionId+"/mark"+suffix,{member_id:row.id,status},parseMark));}
    catch(error){setError(failure(error));}finally{busy.current=false;setPending(false);}
  };
  return <article className="card attendance-person" aria-label={row.full_name}>
    <div className="attendance-person-identity"><PrivateAvatar name={row.full_name} photo={row.photo_url}/><div><strong>{row.full_name}</strong><small>{row.member_no}</small></div><span className={"attendance-status status-"+(row.status??"unmarked").toLowerCase()}>{row.status?statusLabel(row.status):"Unmarked"}</span></div>
    <div className="attendance-buttons" aria-label={"Attendance for "+row.full_name}>{STATUS_CODES.map(status=><button key={status} aria-label={(row.record_id?"Correct ":"Mark ")+row.full_name+" "+statusLabel(status)} aria-pressed={row.status===status} disabled={pending||!(row.record_id?row.can_correct:row.can_mark)||row.status===status} className={"mark-button mark-"+status.toLowerCase()} onClick={()=>{void mark(status);}}>{statusLabel(status)}</button>)}</div>
    <div className="attendance-save-status" role="status">{pending?"Saving…":row.marked_at?"Saved · "+row.marked_by:"Not yet marked"}</div>
    {error&&<ErrorMessage message={error}/>}
    {correcting&&<Correction school={school} row={row} status={correcting} suffix={suffix} close={()=>setCorrecting(null)} saved={result=>{saved(result);setCorrecting(null);}}/>}
  </article>;
}
function Correction({school,row,status,suffix,close,saved}:{school:boolean;row:RosterRow;status:AttendanceStatus;suffix:string;close:()=>void;saved:(result:MarkResult)=>void}) {
  const [pending,setPending]=useState(false);const [error,setError]=useState("");const busy=useRef(false);
  return <OperationalModal title="Correct attendance" description={row.full_name+": "+statusLabel(row.status??"UNMARKED")+" → "+statusLabel(status)} close={()=>{if(!pending)close();}}>
    <form className="operational-form" onSubmit={async event=>{event.preventDefault();if(busy.current)return;busy.current=true;setPending(true);setError("");const fields=new FormData(event.currentTarget);
      try{saved(await api.mutate(prefix(school)+"/records/"+row.record_id+"/correct"+suffix,{status,reason:String(fields.get("reason")),expected_status:row.status,expected_updated_at:row.updated_at},parseMark));}catch(error){setError(failure(error));}finally{busy.current=false;setPending(false);}}}>
      <label>Correction reason<textarea name="reason" required maxLength={1000} rows={3}/></label><FormActions pending={pending} error={error} close={close} label="Save correction"/>
    </form></OperationalModal>;
}
function SessionTransition({school,session,action,close,saved}:{school:boolean;session:Session;action:string;close:()=>void;saved:(result:Session)=>void}) {
  const [pending,setPending]=useState(false);const [error,setError]=useState("");const busy=useRef(false);
  const reasonRequired=["reopen","lock","unlock"].includes(action);
  return <OperationalModal title={statusLabel(action)+" session"} description={action==="close"?"Remaining unmarked roster members will be recorded as absent.":"Apply this change to the saved attendance session."} close={()=>{if(!pending)close();}}>
    <form className="operational-form" onSubmit={async event=>{event.preventDefault();if(busy.current)return;busy.current=true;setPending(true);setError("");const fields=new FormData(event.currentTarget);
      try{saved(await api.mutate(prefix(school)+"/sessions/"+session.id+"/"+action,{expected_updated_at:session.updated_at,reason:String(fields.get("reason")??"")},school?parseSchoolSession:parseSession));}
      catch(error){setError(failure(error));}finally{busy.current=false;setPending(false);}}}>
      {reasonRequired&&<label>Reason<textarea name="reason" required maxLength={1000} rows={3}/></label>}<FormActions pending={pending} error={error} close={close} label={"Confirm "+action}/>
    </form></OperationalModal>;
}
