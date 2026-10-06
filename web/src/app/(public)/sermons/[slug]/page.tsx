import {PublicDetail} from "@/features/public/site";
import {getPublic,publicMetadata,type PublicContent} from "@/features/public/server";
export async function generateMetadata({params}:{params:Promise<{slug:string}>}){const {slug}=await params;const item=await getPublic<PublicContent>("sermons/"+encodeURIComponent(slug));return publicMetadata(item?.seo_title||item?.title||"HOPFAN sermons",item?.seo_description||item?.summary||"House of Prayer for All Nations.","/sermons/"+slug,item?.image);}
export default async function Page({params}:{params:Promise<{slug:string}>}){return <PublicDetail section="sermons" slug={(await params).slug}/>;}
