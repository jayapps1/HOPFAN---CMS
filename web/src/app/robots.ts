import type {MetadataRoute} from "next";
import {canonicalOrigin} from "@/features/public/server";
export default function robots():MetadataRoute.Robots{
  const origin=canonicalOrigin();
  return {rules:{userAgent:"*",allow:origin?"/":undefined,disallow:origin?["/portal/","/login","/api/"]:["/"]},sitemap:origin?origin+"/sitemap.xml":undefined};
}
