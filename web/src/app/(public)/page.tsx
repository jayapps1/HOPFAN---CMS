import {PublicHome} from "@/features/public/site";
import {publicMetadata} from "@/features/public/server";
export const metadata=publicMetadata("HOPFAN","House of Prayer for All Nations.","/");
export default function Page(){return <PublicHome/>;}
