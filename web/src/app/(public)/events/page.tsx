import {PublicCollection} from "@/features/public/site";
import {publicMetadata} from "@/features/public/server";
export const metadata=publicMetadata("Events","Published HOPFAN events.","/events");
export default function Page({searchParams}:{searchParams:Promise<Record<string,string|undefined>>}){return <PublicCollection section="events" searchParams={searchParams}/>;}
