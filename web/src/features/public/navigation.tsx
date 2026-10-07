"use client";
import {useState} from "react";
import Link from "next/link";
import Image from "next/image";
import * as Dialog from "@radix-ui/react-dialog";
import {Menu,X,ArrowUpRight} from "lucide-react";
const links=[["Home","/"],["About","/about"],["Ministries","/ministries"],["Sunday School","/sunday-school"],["Events","/events"],["Sermons","/sermons"],["Gallery","/gallery"],["Donate","/donate"]];
export function PublicHeader({name}:{name:string}){
  const[open,setOpen]=useState(false);
  return<header className="public-header"><Link href="/" className="public-brand"><Image src="/brand/hopfan-logo.png" width={44} height={47} alt="HOPFAN church logo"/><span>{name}<small>House of Prayer for All Nations</small></span></Link>
    <nav className="public-desktop-nav" aria-label="Public navigation">{links.map(([label,url])=><Link href={url} key={url}>{label}</Link>)}</nav>
    <Link className="public-button public-header-cta" href="/new-here">Plan your visit<ArrowUpRight size={16} aria-hidden="true"/></Link>
    <Dialog.Root open={open} onOpenChange={setOpen}><Dialog.Trigger className="public-menu-button" aria-label="Open public navigation"><Menu size={23}/></Dialog.Trigger><Dialog.Portal><Dialog.Overlay className="dialog-overlay"/><Dialog.Content className="public-drawer">
      <Dialog.Title>Explore HOPFAN</Dialog.Title><Dialog.Description>A welcome, our community, and ways to connect.</Dialog.Description><nav aria-label="Mobile public navigation">{links.map(([label,url])=><Link href={url} key={url} onClick={()=>setOpen(false)}>{label}</Link>)}<Link href="/new-here" onClick={()=>setOpen(false)}>Plan your visit</Link></nav><Dialog.Close className="dialog-close" aria-label="Close public navigation"><X size={20}/></Dialog.Close>
    </Dialog.Content></Dialog.Portal></Dialog.Root></header>;
}
