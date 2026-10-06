import type {MetadataRoute} from "next";
import {canonicalOrigin,getPublic,type PublicPage,type PublicContent} from "@/features/public/server";
export default async function sitemap():Promise<MetadataRoute.Sitemap>{
  const origin=canonicalOrigin();if(!origin)return [];
  const paths=["","about","leadership","ministries","sunday-school","events","announcements","sermons","gallery","prayer-request","new-here","contact","give"];
  const entries:MetadataRoute.Sitemap=paths.map(path=>({url:origin+"/"+path}));
  for(const section of ["ministries","events","sermons","gallery"]){
    let page=1;
    for(;;){const data=await getPublic<PublicPage<PublicContent>>(section+"?page_number="+page+"&page_size=100");if(!data)break;
      entries.push(...data.items.map(item=>({url:origin+"/"+section+"/"+item.slug})));if(page>=data.pages)break;page++;
    }
  }
  return entries;
}
