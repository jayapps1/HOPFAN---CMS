import {PublicCollection} from "@/features/public/site";
import {publicMetadata} from "@/features/public/server";
export const metadata=publicMetadata("Leadership","Published HOPFAN leadership.","/leadership");
export default function Page({searchParams}:{searchParams:Promise<Record<string,string|undefined>>}){return <PublicCollection section="leadership" searchParams={searchParams}/>;}
