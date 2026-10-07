import {DonationResult} from "@/features/public/donation-result";
export const metadata={title:'Donation receipt',robots:{index:false,follow:false},referrer:'no-referrer' as const};
export default async function Page({searchParams}:{searchParams:Promise<Record<string,string|string[]|undefined>>}){const params=await searchParams;return<DonationResult key={typeof params.reference==='string'?params.reference:''} reference={typeof params.reference==='string'?params.reference:''} cancelled={params.cancelled==='1'}/>;}
