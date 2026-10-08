import {SermonWatch} from '@/features/sermons/public';
import {getPublic,publicMetadata} from '@/features/public/server';
import type {Sermon} from '@/features/sermons/types';
export async function generateMetadata({params}:{params:Promise<{slug:string}>}){const{slug}=await params;const item=await getPublic<Sermon>('sermons/'+encodeURIComponent(slug));return publicMetadata(item?.seo_title||item?.title||'Sermon',item?.seo_description||item?.summary||'HOPFAN message.','/sermons/'+slug,item?.image);}
export default async function Page({params,searchParams}:{params:Promise<{slug:string}>;searchParams:Promise<Record<string,string|undefined>>}){return <SermonWatch slug={(await params).slug} mode={(await searchParams).mode}/>;}
