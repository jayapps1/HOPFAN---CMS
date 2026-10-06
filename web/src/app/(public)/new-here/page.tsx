import {PublicInformation} from "@/features/public/site";
import {getPublic,publicMetadata,type PublicContent} from "@/features/public/server";
export async function generateMetadata(){const page=await getPublic<PublicContent>("pages/new-here");return publicMetadata(page?.seo_title||page?.title||"new here",page?.seo_description||page?.summary||"House of Prayer for All Nations.","/new-here",page?.image);}
export default function Page(){return <PublicInformation slug="new-here"/>;}
