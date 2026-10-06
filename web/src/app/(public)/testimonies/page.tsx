import {PublicCollection} from "@/features/public/site";
import {publicMetadata} from "@/features/public/server";
export const metadata=publicMetadata("Testimonies","Published HOPFAN testimonies.","/testimonies");
export default function Page({searchParams}:{searchParams:Promise<Record<string,string|undefined>>}){return <PublicCollection section="testimonies" searchParams={searchParams}/>;}
