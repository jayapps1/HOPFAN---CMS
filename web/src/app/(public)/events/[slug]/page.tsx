import {PublicDetail} from "@/features/public/site";
import {getPublic,publicMetadata,type PublicContent} from "@/features/public/server";
export async function generateMetadata({params}:{params:Promise<{slug:string}>}){const {slug}=await params;const item=await getPublic<PublicContent & {description?:string}>("events/"+encodeURIComponent(slug));return publicMetadata(item?.seo_title||item?.title||"HOPFAN events",item?.seo_description||item?.summary||item?.description||"House of Prayer for All Nations.","/events/"+slug,item?.image);}
export default async function Page({params}:{params:Promise<{slug:string}>}){return <PublicDetail section="events" slug={(await params).slug}/>;}
