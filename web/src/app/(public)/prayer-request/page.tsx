import {PublicInformation} from "@/features/public/site";
import {getPublic,publicMetadata,type PublicContent} from "@/features/public/server";
export async function generateMetadata(){const page=await getPublic<PublicContent>("pages/prayer-request");return publicMetadata(page?.seo_title||page?.title||"prayer request",page?.seo_description||page?.summary||"House of Prayer for All Nations.","/prayer-request",page?.image);}
export default function Page(){return <PublicInformation slug="prayer-request"/>;}
