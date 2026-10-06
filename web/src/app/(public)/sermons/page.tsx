import {PublicCollection} from "@/features/public/site";
import {publicMetadata} from "@/features/public/server";
export const metadata=publicMetadata("Sermons","Published HOPFAN sermons.","/sermons");
export default function Page({searchParams}:{searchParams:Promise<Record<string,string|undefined>>}){return <PublicCollection section="sermons" searchParams={searchParams}/>;}
