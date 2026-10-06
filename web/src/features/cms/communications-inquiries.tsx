"use client";
import {useRef,useState} from "react";
import {useAuth} from "@/features/auth/auth-provider";
import {useResource} from "@/features/workspace/use-resource";
import {useFilters} from "@/features/workspace/directories";
import {useWorkspace} from "@/features/workspace/workspace-provider";
import {RecordState,Pagination,Empty} from "@/features/workspace/records-ui";
import {OperationalModal,FormActions} from "@/features/operations/operational-ui";
import {PublicationConfirm} from "./content-manager";
import {Button,Card,Input,Badge} from "@/components/ui/primitives";
import {AccessDenied} from "@/components/ui/feedback";
import {api,ApiError} from "@/lib/api/client";
import {obj,bool,parseOptions} from "@/lib/api/workspace";
import {parseCommunications,parseCommunication,parseInquiries,parseInquiry,parseCandidates,type Communication,type Inquiry} from "@/lib/api/content";
const failure=(error:unknown)=>error instanceof ApiError||error instanceof Error?error.message:"Unable to save.";
function parseCommunicationOptions(value:unknown){const o=obj(value);return{ministries:parseOptions(o.ministries),global_create:bool(o.global_create)};}
export function CommunicationsManager({kind}:{kind:"EVENT"|"ANNOUNCEMENT"}){
  const{user}=useAuth(),workspace=useWorkspace();const{params,update,page}=useFilters();const path=kind==="EVENT"?"events":"announcements";
  const[editing,setEditing]=useState<Communication|"new"|null>(null),[acting,setActing]=useState<{row:Communication;action:string}|null>(null);
  const query=new URLSearchParams({page_number:String(page),search:params.get("search")??"",status:params.get("status")??"ALL"});if(workspace.ministryId)query.set("ministry_id",workspace.ministryId);
  const data=useResource("/api/v1/"+path+"?"+query,parseCommunications),options=useResource("/api/v1/"+path+"/options",parseCommunicationOptions);
  const can=(suffix:string)=>user?.permissions.includes(kind+"_"+suffix);
  if(user&&!can("VIEW_ALL")&&!(can("VIEW_OWN_MINISTRY")&&user.ministry_scopes.length))return<AccessDenied/>;
  return<><div className="page-heading"><div><p className="eyebrow">CHURCH COMMUNICATIONS</p><h1>{kind==="EVENT"?"Events":"Announcements"}</h1><p>Create a scoped draft, submit it for approval and publish with permission.</p></div>{(can("CREATE_GLOBAL")||can("CREATE_OWN_MINISTRY"))&&<Button onClick={()=>setEditing("new")}>Create {kind==="EVENT"?"event":"announcement"}</Button>}</div>
    <form className="record-filters" onSubmit={event=>{event.preventDefault();update({search:String(new FormData(event.currentTarget).get("search")??"")});}}><label className="search-field">Search<Input name="search" defaultValue={params.get("search")??""} key={params.get("search")}/></label><Button type="submit" variant="secondary">Search</Button><label>Status<select aria-label="Publication status" value={params.get("status")??"ALL"} onChange={event=>update({status:event.target.value})}>{["ALL","DRAFT","SUBMITTED","APPROVED","PUBLISHED","CANCELLED","ARCHIVED"].map(value=><option key={value}>{value}</option>)}</select></label></form>
    <RecordState {...data}/>{data.data&&<>{data.data.items.length?<div className="cms-content-list">{data.data.items.map(row=><Card className="cms-content-row" key={row.id}><div><Badge tone={row.status==="PUBLISHED"?"green":"neutral"}>{row.status}</Badge><h2>{row.title}</h2><p className="muted">{row.scope==="CHURCH_WIDE"?"Church-wide":options.data?.ministries.find(item=>item.id===row.ministry_id)?.name??"Ministry"} · {row.start_datetime?new Date(row.start_datetime).toLocaleString("en-GB"):row.audience}</p><p>{row.description||row.body}</p></div>
      <div className="live-actions">{["DRAFT","SUBMITTED","APPROVED"].includes(row.status)&&(can("EDIT_GLOBAL")||can("EDIT_OWN_MINISTRY"))&&<Button variant="secondary" onClick={()=>setEditing(row)}>Edit</Button>}
      {row.status==="DRAFT"&&can("SUBMIT")&&<Button onClick={()=>setActing({row,action:"submit"})}>Submit</Button>}
      {row.status==="SUBMITTED"&&can("APPROVE")&&<Button onClick={()=>setActing({row,action:"approve"})}>Approve</Button>}
      {row.status==="APPROVED"&&can("PUBLISH")&&<Button onClick={()=>setActing({row,action:"publish"})}>Publish</Button>}
      {row.status==="PUBLISHED"&&can("PUBLISH")&&<Button variant="secondary" onClick={()=>setActing({row,action:"unpublish"})}>Withdraw</Button>}
      {can("CANCEL")&&row.status!=="ARCHIVED"&&<Button variant="ghost" onClick={()=>setActing({row,action:"archive"})}>Archive</Button>}</div></Card>)}</div>:<Empty title={"No "+path+" found"}>Create a draft or change your filters.</Empty>}<Pagination {...data.data} change={value=>update({page:String(value)})}/></>}
    {editing&&<CommunicationEditor kind={kind} record={editing==="new"?null:editing} options={options.data?.ministries??[]} globalCreate={options.data?.global_create??false} close={()=>setEditing(null)} saved={()=>{setEditing(null);data.retry();}}/>}
    {acting&&<PublicationConfirm title={acting.action+" "+kind.toLowerCase()} path={"/api/v1/"+path+"/"+acting.row.id+"/"+acting.action} version={acting.row.updated_at} decoder={parseCommunication} close={()=>setActing(null)} saved={()=>{setActing(null);data.retry();}}/>}
  </>;
}
function CommunicationEditor({kind,record,options,globalCreate,close,saved}:{kind:"EVENT"|"ANNOUNCEMENT";record:Communication|null;options:{id:string;name:string}[];globalCreate:boolean;close:()=>void;saved:()=>void}){
  const workspace=useWorkspace();const[scope,setScope]=useState(record?.scope??(globalCreate?"CHURCH_WIDE":"MINISTRY")),[ministry,setMinistry]=useState(record?.ministry_id??workspace.ministryId??options[0]?.id??"");
  const[pending,setPending]=useState(false),[error,setError]=useState("");const busy=useRef(false);
  const time=(value:string|null|undefined)=>value?new Date(value).toISOString().slice(0,16):"";
  return<OperationalModal title={record?"Edit draft":"Create "+kind.toLowerCase()} description="Public content requires approval and publication. Drafts remain private." close={()=>{if(!pending)close();}}><form className="operational-form" onSubmit={async event=>{event.preventDefault();if(busy.current)return;busy.current=true;setPending(true);setError("");
    try{const f=new FormData(event.currentTarget),value=(key:string)=>String(f.get(key)??"");const body={slug:value("slug"),title:value("title"),scope,ministry_id:scope==="MINISTRY"?ministry:null,expected_updated_at:record?.updated_at??null};
      const payload=kind==="EVENT"?{...body,description:value("description"),event_type:value("event_type"),visibility:value("visibility"),start_datetime:new Date(value("start_datetime")).toISOString(),end_datetime:value("end_datetime")?new Date(value("end_datetime")).toISOString():null,location:value("location"),image_id:record?.image_id??null}
        :{...body,body:value("body"),audience:value("audience"),publish_from:value("publish_from")?new Date(value("publish_from")).toISOString():null,publish_until:value("publish_until")?new Date(value("publish_until")).toISOString():null,priority:Number(value("priority")||"0")};
      await api.mutate("/api/v1/"+(kind==="EVENT"?"events":"announcements")+(record?"/"+record.id:""),payload,parseCommunication,record?"PATCH":"POST");saved();
    }catch(error){setError(failure(error));}finally{busy.current=false;setPending(false);}}}>
    <label>Title<Input name="title" required maxLength={200} defaultValue={record?.title}/></label><label>Public URL name<Input name="slug" required pattern="[a-z0-9]+(-[a-z0-9]+)*" defaultValue={record?.slug}/></label>
    {globalCreate&&<label>Scope<select aria-label="Communication scope" value={scope} onChange={event=>setScope(event.target.value)}><option value="CHURCH_WIDE">Church-wide</option><option value="MINISTRY">Ministry</option></select></label>}
    {scope==="MINISTRY"&&<label>Ministry{options.length===1?<strong>{options[0].name}</strong>:<select required aria-label="Communication ministry" value={ministry} onChange={event=>setMinistry(event.target.value)}><option value="">Choose ministry</option>{options.map(option=><option value={option.id} key={option.id}>{option.name}</option>)}</select>}</label>}
    {kind==="EVENT"?<><label>Description<textarea name="description" rows={4} defaultValue={record?.description}/></label><label>Event type<select name="event_type" aria-label="Event type" defaultValue={record?.event_type??"OTHER"}>{["SERVICE","CONFERENCE","MEETING","OUTREACH","OTHER"].map(value=><option key={value}>{value}</option>)}</select></label>
      <label>Visibility<select aria-label="Event visibility" name="visibility" defaultValue={record?.visibility??"INTERNAL"}>{["INTERNAL","PUBLIC","BOTH"].map(value=><option key={value}>{value}</option>)}</select></label>
      <label>Start date and time<Input type="datetime-local" name="start_datetime" required defaultValue={time(record?.start_datetime)}/></label><label>End date and time (optional)<Input type="datetime-local" name="end_datetime" defaultValue={time(record?.end_datetime)}/></label><label>Location<Input name="location" defaultValue={record?.location} maxLength={500}/></label></>
      :<><label>Announcement<textarea name="body" rows={5} defaultValue={record?.body}/></label><label>Audience<select name="audience" aria-label="Announcement audience" defaultValue={record?.audience??"INTERNAL"}>{["INTERNAL","PUBLIC","BOTH"].map(value=><option key={value}>{value}</option>)}</select></label><label>Publish from (optional)<Input name="publish_from" type="datetime-local" defaultValue={time(record?.publish_from)}/></label><label>Publish until (optional)<Input name="publish_until" type="datetime-local" defaultValue={time(record?.publish_until)}/></label><label>Priority<Input name="priority" type="number" min={0} max={100} defaultValue={record?.priority??0}/></label></>}
    <FormActions pending={pending} error={error} close={close} label="Save draft"/>
  </form></OperationalModal>;
}
export function InquiriesManager({prayer=false}:{prayer?:boolean}){
  const{user}=useAuth();const{params,page,update}=useFilters();const kind=prayer?"PRAYER":params.get("kind")??"VISITOR";const[editing,setEditing]=useState<Inquiry|null>(null),[converting,setConverting]=useState<Inquiry|null>(null);
  const data=useResource("/api/v1/visitor-inquiries?"+new URLSearchParams({kind,page_number:String(page),search:params.get("search")??"",status:params.get("status")??"ALL"}),parseInquiries);
  if(!user)return null;if(prayer?!user.permissions.includes("PRAYER_REQUEST_VIEW"):!user.permissions.some(code=>["VISITOR_VIEW_ALL","VISITOR_VIEW_OWN"].includes(code)))return<AccessDenied/>;
  return<><div className="page-heading"><div><p className="eyebrow">PRIVATE FOLLOW-UP</p><h1>{prayer?"Prayer requests":"Visitors and contact inquiries"}</h1><p>{prayer?"Sensitive requests are available only to explicitly authorized pastoral users.":"Review inquiries, respect contact consent and link Members only after confirmation."}</p></div></div>
    <form className="record-filters" onSubmit={event=>{event.preventDefault();update({search:String(new FormData(event.currentTarget).get("search")??"")});}}><label className="search-field">Search<Input name="search" defaultValue={params.get("search")??""} key={params.get("search")}/></label><Button variant="secondary" type="submit">Search</Button>
    {!prayer&&<label>Inquiry type<select aria-label="Inquiry type" value={kind} onChange={event=>update({kind:event.target.value})}><option value="VISITOR">Visitors</option><option value="CONTACT">Contact messages</option></select></label>}<label>Status<select aria-label="Follow-up status" value={params.get("status")??"ALL"} onChange={event=>update({status:event.target.value})}>{["ALL","NEW","CONTACTED","FOLLOW_UP","VISITED","CONVERTED","CLOSED"].map(value=><option key={value}>{value}</option>)}</select></label></form><RecordState {...data}/>
    {data.data&&<>{data.data.items.length?<div className="cms-content-list">{data.data.items.map(row=><Card className="cms-inquiry-row" key={row.id}><Badge>{row.status}</Badge><h2>{[row.first_name,row.last_name].filter(Boolean).join(" ")||"Anonymous request"}</h2><p>{row.email} {row.phone}</p><p className="public-prose">{row.message}</p><p className="muted">Contact permission: {row.contact_permission?"Yes":"No"} · Preferred: {row.preferred_contact}</p>{row.private_notes&&<p>Follow-up notes: {row.private_notes}</p>}
      <div className="live-actions">{row.status!=="CONVERTED"&&user.permissions.includes(prayer?"PRAYER_REQUEST_EDIT":"VISITOR_EDIT")&&<Button variant="secondary" onClick={()=>setEditing(row)}>Update follow-up</Button>}{row.kind==="VISITOR"&&row.status!=="CONVERTED"&&user.permissions.includes("VISITOR_CONVERT")&&<Button onClick={()=>setConverting(row)}>Review Member conversion</Button>}{row.converted_member_id&&<Badge tone="green">Linked to a Member</Badge>}</div>
    </Card>)}</div>:<Empty title="No inquiries found">New website submissions will appear here when your account is authorized to view them.</Empty>}<Pagination {...data.data} change={value=>update({page:String(value)})}/></>}
    {editing&&<InquiryEditor row={editing} prayer={prayer} close={()=>setEditing(null)} saved={()=>{setEditing(null);data.retry();}}/>}{converting&&<VisitorConversion row={converting} close={()=>setConverting(null)} saved={()=>{setConverting(null);data.retry();}}/>}
  </>;
}
function InquiryEditor({row,prayer,close,saved}:{row:Inquiry;prayer:boolean;close:()=>void;saved:()=>void}){
  const{user}=useAuth();const candidates=useResource(!prayer&&user?.permissions.includes("VISITOR_ASSIGN")?"/api/v1/visitor-inquiries/assignees":null,parseOptions);
  const[pending,setPending]=useState(false),[error,setError]=useState("");const busy=useRef(false);
  return<OperationalModal title="Update private follow-up" description="Keep notes within this private queue and respect the person’s contact permission." close={()=>{if(!pending)close();}}><form className="operational-form" onSubmit={async event=>{event.preventDefault();if(busy.current)return;busy.current=true;setPending(true);setError("");try{const f=new FormData(event.currentTarget);await api.mutate("/api/v1/visitor-inquiries/"+row.id,{status:String(f.get("status")),private_notes:String(f.get("notes")),assigned_to:f.has("assigned_to")?String(f.get("assigned_to"))||null:row.assigned_to,expected_updated_at:row.updated_at},parseInquiry,"PATCH");saved();}catch(error){setError(failure(error));}finally{busy.current=false;setPending(false);}}}>
    <label>Status<select name="status" aria-label="Updated follow-up status" defaultValue={row.status}>{["NEW","CONTACTED","FOLLOW_UP","VISITED","CLOSED"].map(value=><option key={value}>{value}</option>)}</select></label><label>Private follow-up notes<textarea name="notes" rows={5} defaultValue={row.private_notes}/></label>
    {candidates.data&&<label>Assign follow-up<select name="assigned_to" aria-label="Assign follow-up" defaultValue={row.assigned_to??""}><option value="">Unassigned</option>{candidates.data.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
    <FormActions pending={pending} error={error} close={close} label="Save follow-up"/>
  </form></OperationalModal>;
}
function VisitorConversion({row,close,saved}:{row:Inquiry;close:()=>void;saved:()=>void}){
  const matches=useResource("/api/v1/visitor-inquiries/"+row.id+"/matches",parseCandidates);const[pending,setPending]=useState(false),[error,setError]=useState("");const busy=useRef(false);
  return<OperationalModal title="Review Member conversion" description="Check possible duplicates before registering a Member. Repeated inquiries must not create duplicate identities." close={()=>{if(!pending)close();}}><RecordState {...matches}/>{matches.data&&<form className="operational-form" onSubmit={async event=>{event.preventDefault();if(busy.current)return;busy.current=true;setPending(true);setError("");try{const f=new FormData(event.currentTarget);await api.mutate("/api/v1/visitor-inquiries/"+row.id+"/convert",{existing_member_id:String(f.get("existing_member_id")??"")||null,confirm:f.get("confirm")==="on",expected_updated_at:row.updated_at},parseInquiry);saved();}catch(error){setError(failure(error));}finally{busy.current=false;setPending(false);}}}>
    <p>{row.first_name} {row.last_name}</p><label>Member selection<select aria-label="Member selection" name="existing_member_id" required={matches.data.length>0} defaultValue=""><option value="">{matches.data.length?"Choose a reviewed match":"Register a new Member"}</option>{matches.data.map(item=><option key={item.id} value={item.id}>{item.name} · {item.member_no}</option>)}</select></label>
    <label className="checkbox-label"><input type="checkbox" name="confirm" required/>I have reviewed the identity and confirm this Member link or registration.</label><FormActions pending={pending} error={error} close={close} label="Confirm conversion"/>
  </form>}</OperationalModal>;
}
