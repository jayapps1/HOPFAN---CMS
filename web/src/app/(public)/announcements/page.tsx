import {PublicCollection} from "@/features/public/site";
import {publicMetadata} from "@/features/public/server";
export const metadata=publicMetadata("Announcements","Published HOPFAN announcements.","/announcements");
export default function Page({searchParams}:{searchParams:Promise<Record<string,string|undefined>>}){return <PublicCollection section="announcements" searchParams={searchParams}/>;}
