"use client";
import {useRef,useState} from "react";
import {CheckCircle2,Send} from "lucide-react";
export function PublicIntakeForm({kind}:{kind:"VISITOR"|"PRAYER"|"CONTACT"}){
  const[pending,setPending]=useState(false),[submitted,setSubmitted]=useState(false),[error,setError]=useState("");const busy=useRef(false);
  const label=kind==="PRAYER"?"prayer request":kind==="VISITOR"?"visit inquiry":"message";
  if(submitted)return<div className="public-confirmation" role="status"><CheckCircle2 size={35}/><h2>Thank you for reaching out.</h2><p>Your {label} has been received privately.</p></div>;
  return<form className="public-form" onSubmit={async event=>{
    event.preventDefault();if(busy.current)return;busy.current=true;setPending(true);setError("");
    const form=event.currentTarget,fields=new FormData(form);
    try{const body={first_name:String(fields.get("first_name")??""),last_name:String(fields.get("last_name")??""),phone:String(fields.get("phone")??""),email:String(fields.get("email")??""),message:String(fields.get("message")??""),contact_permission:fields.get("contact_permission")==="on",preferred_contact:String(fields.get("preferred_contact")??"NONE"),visit_date:String(fields.get("visit_date")??"")||null,privacy:"PRIVATE",website:String(fields.get("website")??"")};
      const path=kind==="PRAYER"?"prayer-requests":kind==="VISITOR"?"visitor-inquiries":"contact";
      const response=await fetch((process.env.NEXT_PUBLIC_API_BASE_URL??"http://localhost:8000")+"/api/v1/public/"+path,{method:"POST",credentials:"omit",cache:"no-store",headers:{"Content-Type":"application/json"},body:JSON.stringify(body),signal:AbortSignal.timeout(15000)});
      if(!response.ok)throw new Error(response.status===429?"Please wait a little before submitting again.":response.status===422?"Check your details and try again.":"We could not receive your message right now. Please try again.");
      form.reset();setSubmitted(true);
    }catch(error){setError(error instanceof Error&&error.name!=="TypeError"?error.message:"Unable to reach HOPFAN. Please try again shortly.");}finally{busy.current=false;setPending(false);}
  }}>
    <div className="public-form-pair"><label>First name{kind==="PRAYER"?" (optional)":""}<input name="first_name" autoComplete="given-name" maxLength={100} required={kind!=="PRAYER"}/></label><label>Last name (optional)<input name="last_name" autoComplete="family-name" maxLength={100}/></label></div>
    <div className="public-form-pair"><label>Email (optional)<input name="email" type="email" autoComplete="email" maxLength={254}/></label><label>Phone (optional)<input name="phone" type="tel" autoComplete="tel" maxLength={40}/></label></div>
    {kind==="VISITOR"&&<label>Planned visit date (optional)<input name="visit_date" type="date"/></label>}
    <label>{kind==="PRAYER"?"Your prayer request":"Your message"+(kind==="VISITOR"?" (optional)":"")}<textarea name="message" rows={5} required={kind!=="VISITOR"} maxLength={10000}/></label>
    <label>Preferred contact<select name="preferred_contact" aria-label="Preferred contact"><option value="NONE">No contact requested</option><option value="EMAIL">Email</option><option value="PHONE">Phone</option></select></label>
    <label className="public-checkbox"><input type="checkbox" name="contact_permission"/>I give permission for the church to contact me about this {label}.</label>
    <div className="public-honeypot" aria-hidden="true"><label>Website<input name="website" tabIndex={-1} autoComplete="off"/></label></div>
    <p className="public-privacy-note">Your details are for the church’s private follow-up. They will not appear on this website.</p>
    {error&&<p className="public-form-error" role="alert">{error}</p>}<button className="public-button" type="submit" disabled={pending}>{pending?"Sending…":"Send "+label}<Send size={17} aria-hidden="true"/></button>
  </form>;
}
