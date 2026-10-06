import {PublicDetail} from "@/features/public/site";
import {getPublic,publicMetadata,type PublicContent} from "@/features/public/server";
export async function generateMetadata({params}:{params:Promise<{slug:string}>}){const {slug}=await params;const item=await getPublic<PublicContent>("gallery/"+encodeURIComponent(slug));return publicMetadata(item?.seo_title||item?.title||"HOPFAN gallery",item?.seo_description||item?.summary||"House of Prayer for All Nations.","/gallery/"+slug,item?.image);}
export default async function Page({params}:{params:Promise<{slug:string}>}){return <PublicDetail section="gallery" slug={(await params).slug}/>;}
