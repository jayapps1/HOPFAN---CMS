import {SermonSeriesPage} from '@/features/sermons/public';
import {getPublic,publicMetadata} from '@/features/public/server';
import type {Collection} from '@/features/sermons/types';
export async function generateMetadata({params}:{params:Promise<{slug:string}>}){const{slug}=await params;const item=await getPublic<Collection>('sermon-series/'+encodeURIComponent(slug));return publicMetadata(item?.name||'Sermon series',item?.description||'HOPFAN sermon series.','/sermons/series/'+slug,item?.image);}
export default async function Page({params,searchParams}:{params:Promise<{slug:string}>;searchParams:Promise<Record<string,string|undefined>>}){return <SermonSeriesPage slug={(await params).slug} searchParams={searchParams}/>;}
