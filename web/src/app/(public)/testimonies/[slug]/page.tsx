import {PublicDetail} from "@/features/public/site";
import {getPublic,publicMetadata,type PublicContent} from "@/features/public/server";
export async function generateMetadata({params}:{params:Promise<{slug:string}>}){const {slug}=await params;const item=await getPublic<PublicContent>("testimonies/"+encodeURIComponent(slug));return publicMetadata(item?.seo_title||item?.title||"HOPFAN testimonies",item?.seo_description||item?.summary||"House of Prayer for All Nations.","/testimonies/"+slug,item?.image);}
export default async function Page({params}:{params:Promise<{slug:string}>}){return <PublicDetail section="testimonies" slug={(await params).slug}/>;}
