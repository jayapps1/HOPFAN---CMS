"use client";
import {useState} from 'react';
import {useResource} from '@/features/workspace/use-resource';
import {useAuth} from '@/features/auth/auth-provider';
import {AccessDenied,ErrorMessage} from '@/components/ui/feedback';
import {parseDonationPage,donationMoney} from '@/features/public/donation-contracts';
export function DonationWorkspace(){const{user}=useAuth();const[page,setPage]=useState(1);const allowed=!!user?.permissions.includes('DONATIONS_VIEW');
  const resource=useResource(allowed?'/api/v1/finance/donations?page_number='+page:null,parseDonationPage);
  const data=resource.data,error=resource.error?.message;
  if(!allowed)return<AccessDenied/>;
  return<><div className="page-heading"><div><p className="eyebrow">PRIVATE FINANCE RECORDS</p><h1>Online donations</h1><p>Test payments and donor details. Only authorized finance staff can access these records.</p></div></div>
    {error&&<><ErrorMessage message={error}/><button className="button button-secondary" onClick={resource.retry}>Retry</button></>}
    {!data&&!error&&<p role="status">Loading donations…</p>}
    {data&&!data.items.length&&<p className="empty-state">No online donation records yet.</p>}
    {data&&<div className="cms-content-list">{data.items.map(row=><article className="card cms-content-row" key={row.id}><div><h2>{row.donor_name}</h2><p>{donationMoney(row.amount,row.currency)} · {row.purpose} · {row.status}</p><p>{row.reference}</p><p>{row.email}{row.phone?' · '+row.phone:''}</p>{row.note&&<p>{row.note}</p>}<p className="muted">Created {new Date(row.created_at).toLocaleString()}{row.paid_at?' · Paid '+new Date(row.paid_at).toLocaleString():''}</p></div></article>)}</div>}
    {data&&data.pages>1&&<div className="pagination"><button className="button button-secondary" disabled={page===1} onClick={()=>setPage(value=>value-1)}>Previous</button><span>Page {page} of {data.pages}</span><button className="button button-secondary" disabled={page>=data.pages} onClick={()=>setPage(value=>value+1)}>Next</button></div>}</>;
}
