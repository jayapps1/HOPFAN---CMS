"use client";
import {useCallback,useEffect,useState} from "react";
import Link from "next/link";
import {CheckCircle2,Clock3,CircleAlert} from "lucide-react";
import {api} from "@/lib/api/client";
import {parseReceipt,referencePattern,donationMoney,type DonationReceipt} from "./donation-contracts";
export function DonationResult({reference,cancelled}:{reference:string;cancelled:boolean}){
  const[receipt,setReceipt]=useState<DonationReceipt|null>(null),[pending,setPending]=useState(true),[error,setError]=useState('');
  const check=useCallback(async()=>{setPending(true);setError('');try{
    const token=referencePattern.test(reference)?sessionStorage.getItem('hopfan-donation:'+reference):null;
    if(!token)throw new Error('Open your receipt in the same browser tab used for checkout. Contact the church with your payment reference if you need help.');
    const result=await api.publicMutation('/api/v1/public/donations/'+reference+'/verify',{receipt_token:token},parseReceipt);setReceipt(result);
  }catch(error){setError(error instanceof Error?error.message:'We couldn’t confirm the payment. Please try again.');}finally{setPending(false);}},[reference]);
  useEffect(()=>{let active=true;void Promise.resolve().then(()=>{if(active)void check();});return()=>{active=false;};},[check]);
  const success=receipt?.status==='SUCCESS',failed=receipt&&['FAILED','CANCELLED','INITIALIZATION_FAILED'].includes(receipt.status);
  return<section className="public-section public-page-section public-donation-result" aria-busy={pending}>
    <div className="public-result-icon" aria-hidden="true">{success?<CheckCircle2/>:failed||cancelled?<CircleAlert/>:<Clock3/>}</div>
    <p className="public-eyebrow">Support the Ministry</p><h1>{success?'Thank you for supporting HOPFAN.':failed||cancelled?'Payment was not completed.':'Confirming your donation'}</h1>
    {success?<p>Your support helps the church continue its ministry and community work.</p>:<p>{pending?'We’re checking the payment securely.':receipt&&!failed&&!cancelled?'Your payment is still awaiting confirmation. Check its status before starting another donation.':'You can check the status, try again, or return home.'}</p>}
    {error&&<p className="public-form-error" role="alert">{error}</p>}
    {receipt&&<dl className="public-receipt"><div><dt>Amount</dt><dd>{donationMoney(receipt.amount,receipt.currency)}</dd></div><div><dt>Purpose</dt><dd>{receipt.purpose}</dd></div><div><dt>Reference</dt><dd>{receipt.reference}</dd></div><div><dt>Payment status</dt><dd>{receipt.status.replaceAll('_',' ')}</dd></div></dl>}
    {!receipt&&referencePattern.test(reference)&&<p className="public-receipt-reference">Reference: {reference}</p>}
    <div className="public-hero-actions">{!success&&<button className="public-button" onClick={()=>void check()} disabled={pending}>Check payment status</button>}{(failed||cancelled)&&!success&&<Link href="/donate" className="public-button public-button-outline">Try Again</Link>}<Link className="public-text-link" href="/">Return Home</Link></div>
    <p className="public-privacy-note">Need help with a payment? <Link href="/contact">Contact the church</Link> and quote your reference.</p>
  </section>;
}
