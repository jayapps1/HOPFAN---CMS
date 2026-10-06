import type {ReactNode} from "react";
import {getSite,fallbackConfiguration} from "@/features/public/server";
import {PublicHeader} from "@/features/public/navigation";
import {PublicFooter} from "@/features/public/site";
import "./public.css";
export default async function PublicLayout({children}:{children:ReactNode}){
  const site=await getSite();const config=site?.configuration??fallbackConfiguration;
  return <div className="public-site"><a className="skip-link" href="#public-main">Skip to main content</a><PublicHeader name={config.church_name}/><main id="public-main">{children}</main><PublicFooter config={config}/></div>;
}
