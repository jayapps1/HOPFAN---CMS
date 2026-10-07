"use client";
import {useRef,useState} from "react";
import {ArrowUpRight,ShieldCheck} from "lucide-react";
import Link from "next/link";
import {api,ApiError} from "@/lib/api/client";
import {parseInitialized,type DonationOptions} from "./donation-contracts";
export function DonationForm({options}:{options:DonationOptions|null}){
  const[pending,setPending]=useState(false),[error,setError]=useState('');const busy=useRef(false),attempt=useRef<{payload:string;id:string}|null>(null);
  const enabled=!!options?.enabled&&options.categories.length>0;
  return<form className="public-form public-donation-form" aria-busy={pending} onSubmit={async event=>{
    event.preventDefault();if(busy.current||!enabled)return;busy.current=true;setPending(true);setError('');
    try{
      // Confirm tab storage works before opening checkout; no donor details are stored.
      sessionStorage.setItem('hopfan-donation-storage-check','1');sessionStorage.removeItem('hopfan-donation-storage-check');
      const data=new FormData(event.currentTarget);const payload={donor_name:String(data.get('donor_name')??'').trim(),email:String(data.get('email')??'').trim(),phone:String(data.get('phone')??'').trim(),category_id:String(data.get('category_id')??''),amount:String(data.get('amount')??''),note:String(data.get('note')??'').trim()};
      const serialized=JSON.stringify(payload);
      if(!attempt.current||attempt.current.payload!==serialized)attempt.current={payload:serialized,id:crypto.randomUUID()};
      const result=await api.publicMutation('/api/v1/public/donations',{...payload,request_id:attempt.current.id},parseInitialized);
      sessionStorage.setItem('hopfan-donation:'+result.reference,result.receipt_token);
      window.location.assign(result.authorization_url);
    }catch(error){if(error instanceof ApiError&&error.code==='PAYMENT_UNAVAILABLE')attempt.current=null;setError(error instanceof Error?error.message:'We could not open checkout. Please try again.');busy.current=false;setPending(false);}
  }}>
    <h2>Your donation</h2>
    {options?.enabled&&<p className="public-payment-notice">Test checkout: no real payment will be collected.</p>}
    {!enabled&&<p className="public-payment-notice" role="status">Online checkout is being prepared. <Link href="/contact">Contact the church</Link> for ways to give.</p>}
    <label>Full name<input name="donor_name" autoComplete="name" required maxLength={200}/></label>
    <div className="public-form-pair"><label>Email<input name="email" type="email" autoComplete="email" required maxLength={254}/></label><label>Phone number (optional)<input name="phone" type="tel" autoComplete="tel" maxLength={40} pattern="\+?[0-9 \(\)\-]{7,40}" title="Enter 7 to 15 digits, with an optional country code."/></label></div>
    <div className="public-form-pair"><label>Donation purpose<select name="category_id" aria-label="Donation purpose" required defaultValue=""><option value="" disabled>Choose a purpose</option>{options?.categories.map(category=><option value={category.id} key={category.id}>{category.name}</option>)}</select></label>
      <label>Amount {options?'('+options.currency+')':''}<input name="amount" type="number" inputMode="decimal" min="0.01" max="1000000" step="0.01" required placeholder="0.00"/></label></div>
    <label>Note (optional)<textarea name="note" rows={3} maxLength={2000}/></label>
    <p className="public-privacy-note"><ShieldCheck size={17} aria-hidden="true"/>Your contact details stay private with authorized church finance staff. Card and payment details are entered securely on Paystack.</p>
    {error&&<p className="public-form-error" role="alert">{error}</p>}
    <button type="submit" className="public-button" disabled={!enabled||pending}>{pending?'Opening secure checkout…':'Continue to secure checkout'}<ArrowUpRight size={18} aria-hidden="true"/></button>
  </form>;
}
