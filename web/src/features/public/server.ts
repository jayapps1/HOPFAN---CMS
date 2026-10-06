import {cache} from "react";
import type {Metadata} from "next";
export interface PublicImage {url:string;alt_text:string;width:number;height:number;caption:string}
export interface PublicContent {slug:string;title:string;summary:string;body:string;seo_title:string;seo_description:string;image:PublicImage|null;public_name?:string;public_title?:string;meeting_information?:string;public_contact?:string;speaker?:string;sermon_date?:string;scripture_reference?:string;series?:string;video_embed_url?:string;audio_url?:string;images?:PublicImage[]}
export interface PublicEvent {slug:string;title:string;description:string;start_datetime:string;end_datetime:string|null;location:string;event_type:string;image:PublicImage|null}
export interface PublicAnnouncement {slug:string;title:string;body:string;publish_from:string|null;publish_until:string|null}
export interface Configuration {church_name:string;full_name:string;tagline:string;address:string;public_phone:string;public_email:string;service_times:{name:string;schedule:string}[];social_links:{label:string;url:string}[];map_url:string;footer_text:string;visitor_form_enabled:boolean;prayer_form_enabled:boolean;contact_form_enabled:boolean}
export interface PublicSite {configuration:Configuration;hero:{headline:string;text:string;primary_label:string;primary_href:string;secondary_label:string;secondary_href:string;image:PublicImage|null};section_order:string[];welcome:PublicContent|null;ministries:PublicContent[];leadership:PublicContent[];sermons:PublicContent[];galleries:PublicContent[];events:PublicEvent[];announcements:PublicAnnouncement[]}
export interface PublicPage<T>{items:T[];page:number;page_size:number;total:number;pages:number}
const origin=process.env.PUBLIC_API_ORIGIN??process.env.NEXT_PUBLIC_API_BASE_URL??"http://localhost:8000";
export const getPublic=cache(async function<T>(path:string):Promise<T|null>{
  if(!/^[a-z0-9/?!&=_%+.-]+$/i.test(path))throw new Error("Invalid public resource");
  try{const response=await fetch(origin+"/api/v1/public/"+path,{cache:"no-store",credentials:"omit",signal:AbortSignal.timeout(8000)});
    if(!response.ok)return null;return await response.json() as T;}catch{return null;}
});
export const getSite=()=>getPublic<PublicSite>("site");
export function publicImageUrl(image:PublicImage|null|undefined){return image?.url.startsWith("/api/v1/public/media/")?origin+image.url:"";}
export const fallbackConfiguration:Configuration={church_name:"HOPFAN",full_name:"House of Prayer for All Nations",tagline:"",address:"",public_phone:"",public_email:"",service_times:[],social_links:[],map_url:"",footer_text:"",visitor_form_enabled:true,prayer_form_enabled:true,contact_form_enabled:true};
export function canonicalOrigin():string|null {
  const raw=process.env.SITE_PUBLIC_ORIGIN;
  if(!raw)return null;
  try{const url=new URL(raw);if(url.protocol!=="https:"||url.username||url.password||url.pathname!=="/"||url.search||url.hash)throw new Error();return url.origin;}catch{return null;}
}
export function jsonLd(value: unknown) { return JSON.stringify(value).replaceAll("<","\\u003c"); }
export function publicMetadata(title:string,description:string,path:string,image?:PublicImage|null):Metadata {
  const canonical=canonicalOrigin();const url=canonical?canonical+path:undefined;
  return{title,description,robots:{index:!!canonical,follow:!!canonical},alternates:url?{canonical:url}:undefined,
    openGraph:{title,description,url,type:"website",images:image?[{url:publicImageUrl(image),alt:image.alt_text}]:undefined}};
}
