"use client";
import {useRef,useState} from "react";
import {useAuth} from "@/features/auth/auth-provider";
import {useResource} from "@/features/workspace/use-resource";
import {useFilters} from "@/features/workspace/directories";
import {RecordState,Pagination,Empty} from "@/features/workspace/records-ui";
import {OperationalModal,FormActions} from "@/features/operations/operational-ui";
import {Button,Card,Input,Badge} from "@/components/ui/primitives";
import {AccessDenied} from "@/components/ui/feedback";
import {api,ApiError} from "@/lib/api/client";
import {parseSettings,parseMediaList,parseMedia,type SettingsRecord,type MediaRecord} from "@/lib/api/content";
import {PublicationConfirm} from "./content-manager";
import {ServiceTimesEditor} from './service-times-editor';
const failure=(error:unknown)=>error instanceof ApiError||error instanceof Error?error.message:"Unable to save.";
export function WebsiteSettingsManager({servicesOnly=false}:{servicesOnly?:boolean}){
  const{user}=useAuth();const data=useResource("/api/v1/website/settings",parseSettings);const[publishing,setPublishing]=useState(false);
  if(!user?.permissions.includes("WEBSITE_SETTINGS_MANAGE"))return<AccessDenied/>;
  return<><div className="page-heading"><div><p className="eyebrow">WEBSITE CONFIGURATION</p><h1>{servicesOnly?'Service Times':'Contact and service times'}</h1><p>Publish only approved public church details.</p></div>{user.permissions.includes("WEBSITE_PAGE_PUBLISH")&&data.data?.updated_at&&<Button onClick={()=>setPublishing(true)}>Publish settings</Button>}</div><RecordState {...data}/>{data.data&&<SettingsForm key={data.data.updated_at??"new"} record={data.data} servicesOnly={servicesOnly} saved={()=>data.retry()}/>}
    {publishing&&data.data?.updated_at&&<PublicationConfirm title="Publish website settings" path="/api/v1/website/settings/publish" version={data.data.updated_at} decoder={parseSettings} close={()=>setPublishing(false)} saved={()=>{setPublishing(false);data.retry();}}/>}</>;
}
function SettingsForm({record,saved,servicesOnly}:{record:SettingsRecord;saved:()=>void;servicesOnly:boolean}){
  const[times,setTimes]=useState(record.data.service_times),[social,setSocial]=useState(record.data.social_links);const[pending,setPending]=useState(false),[error,setError]=useState("");const busy=useRef(false);
  const fields=[["church_name","Church name"],["full_name","Full church name"],["tagline","Tagline"],["address","Public address"],["public_phone","Public phone"],["public_email","Public email"],["map_url","Map or directions link"],["footer_text","Footer description"]] as const;
  return<Card className="cms-form-card"><form className="operational-form" onSubmit={async event=>{event.preventDefault();if(busy.current)return;busy.current=true;setPending(true);setError("");
    try{const f=new FormData(event.currentTarget);const body={...record.data,...(!servicesOnly?Object.fromEntries(fields.map(([key])=>[key,String(f.get(key)??"")])):{}),timezone:String(f.get("timezone")??"UTC"),service_times:times,social_links:social,contact_form_enabled:servicesOnly?record.data.contact_form_enabled:f.get("contact_form_enabled")==="on",visitor_form_enabled:servicesOnly?record.data.visitor_form_enabled:f.get("visitor_form_enabled")==="on",prayer_form_enabled:servicesOnly?record.data.prayer_form_enabled:f.get("prayer_form_enabled")==="on"};
      await api.mutate("/api/v1/website/settings",{data:body,expected_updated_at:record.updated_at},parseSettings,"PATCH");saved();
    }catch(error){setError(failure(error));}finally{busy.current=false;setPending(false);}}}>
      {!servicesOnly&&fields.map(([key,label])=><label key={key}>{label}<Input name={key} defaultValue={record.data[key]} required={key==="church_name"}/></label>)}
      <label>Church timezone<Input name="timezone" required defaultValue={record.data.timezone} placeholder="UTC or Africa/Accra" maxLength={100}/></label><ServiceTimesEditor value={times} change={setTimes}/>
      {!servicesOnly&&<fieldset className="class-choices"><legend>Social links</legend>{social.map((item,index)=><div className="cms-repeat-row" key={index}><label>Label<Input required value={item.label} onChange={event=>setSocial(previous=>previous.map((row,i)=>i===index?{...row,label:event.target.value}:row))}/></label><label>HTTPS link<Input required value={item.url} onChange={event=>setSocial(previous=>previous.map((row,i)=>i===index?{...row,url:event.target.value}:row))}/></label><Button type="button" variant="ghost" onClick={()=>setSocial(previous=>previous.filter((_,i)=>i!==index))}>Remove</Button></div>)}<Button type="button" variant="secondary" onClick={()=>setSocial(previous=>[...previous,{label:"",url:""}])}>Add social link</Button></fieldset>}
      {!servicesOnly&&(["contact_form_enabled","visitor_form_enabled","prayer_form_enabled"] as const).map(key=><label className="checkbox-label" key={key}><input name={key} type="checkbox" defaultChecked={record.data[key]}/>{key==="contact_form_enabled"?"Enable contact form":key==="visitor_form_enabled"?"Enable visitor inquiry form":"Enable private prayer request form"}</label>)}
      <FormActions pending={pending} error={error} close={saved} label="Save settings draft"/>
    </form></Card>;
}
export function WebsiteMediaManager(){
  const{user}=useAuth();const{page,update}=useFilters();const data=useResource("/api/v1/website/media?page_number="+page,parseMediaList);
  const[uploading,setUploading]=useState(false),[reviewing,setReviewing]=useState<MediaRecord|null>(null),[archiving,setArchiving]=useState<MediaRecord|null>(null);
  return<><div className="page-heading"><div><p className="eyebrow">REVIEWED WEBSITE MEDIA</p><h1>Media library</h1><p>Uploads stay private. Review rights, consent and alt text before approval.</p></div>{user?.permissions.includes("WEBSITE_MEDIA_MANAGE")&&<Button onClick={()=>setUploading(true)}>Upload image</Button>}</div><RecordState {...data}/>{data.data&&<>{data.data.items.length?<div className="ministry-grid">{data.data.items.map(item=><Card key={item.id} className="cms-media-card"><img src={api.assetUrl(item.preview_url)} alt={item.alt_text||"Unreviewed uploaded image"} width={320} height={180}/><div><Badge tone={item.status==="PUBLISHED"?"green":"neutral"}>{item.status==="PUBLISHED"?"Approved":"Pending review"}</Badge><h2>{item.alt_text||"Alt text needed"}</h2><p>{item.caption}</p>{item.contains_children&&<Badge>Child consent required</Badge>}{user?.permissions.includes("WEBSITE_MEDIA_PUBLISH")&&<Button variant="secondary" onClick={()=>setReviewing(item)}>Review and approve</Button>}{item.status!=="ARCHIVED"&&user?.permissions.includes("WEBSITE_MEDIA_PUBLISH")&&<Button variant="ghost" onClick={()=>setArchiving(item)}>Withdraw image</Button>}</div></Card>)}</div>:<Empty title="No website images yet">Upload approved church photographs. Member photos are kept separate.</Empty>}<Pagination {...data.data} change={value=>update({page:String(value)})}/></>}
    {archiving&&<PublicationConfirm title="Withdraw website image" path={"/api/v1/website/media/"+archiving.id+"/archive"} version={archiving.updated_at} decoder={parseMedia} close={()=>setArchiving(null)} saved={()=>{setArchiving(null);data.retry();}}/>}{uploading&&<MediaUploadForm close={()=>setUploading(false)} saved={()=>{setUploading(false);data.retry();}}/>}{reviewing&&<MediaReviewForm record={reviewing} close={()=>setReviewing(null)} saved={()=>{setReviewing(null);data.retry();}}/>}
  </>;
}
function MediaUploadForm({close,saved}:{close:()=>void;saved:()=>void}){
  const[pending,setPending]=useState(false),[error,setError]=useState("");const busy=useRef(false);
  return<OperationalModal title="Upload website image" description="JPEG, PNG or WebP, up to 8 MB. Uploaded images are not published automatically." close={()=>{if(!pending)close();}}><form className="operational-form" onSubmit={async event=>{event.preventDefault();if(busy.current)return;busy.current=true;setPending(true);setError("");
    try{const f=new FormData(event.currentTarget),file=f.get("image");if(!(file instanceof File)||!file.size||file.size>8*1024*1024)throw new Error("Choose an image up to 8 MB.");
      const encoded=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(new Error("Unable to read the image."));reader.readAsDataURL(file);});
      await api.mutate("/api/v1/website/media",{image_base64:encoded,alt_text:String(f.get("alt_text")),caption:String(f.get("caption")),contains_children:f.get("contains_children")==="on"},parseMedia);saved();
    }catch(error){setError(failure(error));}finally{busy.current=false;setPending(false);}}}>
    <label>Image<input type="file" name="image" accept="image/jpeg,image/png,image/webp" required/></label><label>Alt text<Input name="alt_text" maxLength={500}/></label><label>Caption<Input name="caption" maxLength={1000}/></label><label className="checkbox-label"><input type="checkbox" name="contains_children"/>This image includes children.</label><FormActions pending={pending} error={error} close={close} label="Upload privately"/>
  </form></OperationalModal>;
}
function MediaReviewForm({record,close,saved}:{record:MediaRecord;close:()=>void;saved:()=>void}){
  const[pending,setPending]=useState(false),[error,setError]=useState("");const[children,setChildren]=useState(record.contains_children);const busy=useRef(false);
  return<OperationalModal title="Review image for publication" description="Confirm approved rights and consent. An approved image becomes public only when linked to published content." close={()=>{if(!pending)close();}}><form className="operational-form" onSubmit={async event=>{event.preventDefault();if(busy.current)return;busy.current=true;setPending(true);setError("");
    try{const f=new FormData(event.currentTarget);await api.mutate("/api/v1/website/media/"+record.id+"/approve",{alt_text:String(f.get("alt_text")),caption:String(f.get("caption")),contains_children:children,consent_attested:f.get("consent")==="on",consent_reference:String(f.get("consent_reference")??""),expected_updated_at:record.updated_at},parseMedia);saved();}
    catch(error){setError(failure(error));}finally{busy.current=false;setPending(false);}}}>
    <img className="cms-review-image" src={api.assetUrl(record.preview_url)} alt={record.alt_text||"Image under review"} width={320} height={180}/>
    <label>Alt text<Input name="alt_text" required defaultValue={record.alt_text} maxLength={500}/></label><label>Caption<Input name="caption" defaultValue={record.caption} maxLength={1000}/></label>
    <label className="checkbox-label"><input type="checkbox" checked={children} onChange={event=>setChildren(event.target.checked)}/>This image includes children.</label>
    <label>Approved consent reference{children?" (required)":""}<Input name="consent_reference" required={children} defaultValue={record.consent_reference} maxLength={300}/></label>
    <label className="checkbox-label"><input name="consent" type="checkbox" required/>I confirm the church has approved the rights and consent for public use.</label>
    <FormActions pending={pending} error={error} close={close} label="Approve image"/>
  </form></OperationalModal>;
}
