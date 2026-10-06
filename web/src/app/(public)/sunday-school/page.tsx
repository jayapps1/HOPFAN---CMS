import {PublicInformation} from "@/features/public/site";
import {getPublic,publicMetadata,type PublicContent} from "@/features/public/server";
export async function generateMetadata(){const page=await getPublic<PublicContent>("pages/sunday-school");return publicMetadata(page?.seo_title||page?.title||"sunday school",page?.seo_description||page?.summary||"House of Prayer for All Nations.","/sunday-school",page?.image);}
export default function Page(){return <PublicInformation slug="sunday-school"/>;}
