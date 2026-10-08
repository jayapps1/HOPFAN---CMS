import {SermonEditor} from '@/features/sermons/cms';
export default async function Page({params}:{params:Promise<{id:string}>}){return <SermonEditor id={(await params).id}/>;}
