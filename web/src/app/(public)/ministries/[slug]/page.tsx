import {PublicDetail} from "@/features/public/site";
import {getPublic,publicMetadata,type PublicContent} from "@/features/public/server";
export async function generateMetadata({params}:{params:Promise<{slug:string}>}){const {slug}=await params;const item=await getPublic<PublicContent>("ministries/"+encodeURIComponent(slug));return publicMetadata(item?.seo_title||item?.title||"HOPFAN ministries",item?.seo_description||item?.summary||"House of Prayer for All Nations.","/ministries/"+slug,item?.image);}
export default async function Page({params}:{params:Promise<{slug:string}>}){return <PublicDetail section="ministries" slug={(await params).slug}/>;}
