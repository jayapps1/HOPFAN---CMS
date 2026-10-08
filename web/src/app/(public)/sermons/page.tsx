import {SermonLibrary} from '@/features/sermons/public';
import {publicMetadata} from '@/features/public/server';
export const metadata=publicMetadata('Messages & Sermons','Watch, listen and grow in the Word with HOPFAN messages.','/sermons');
export default function Page({searchParams}:{searchParams:Promise<Record<string,string|undefined>>}){return <SermonLibrary searchParams={searchParams}/>;}
