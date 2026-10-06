"use client";
import {useState} from "react";
import * as Dialog from "@radix-ui/react-dialog";
import {X} from "lucide-react";
export function PublicGalleryGrid({images}:{images:{url:string;alt_text:string;caption:string;width:number;height:number}[]}){
  const[selected,setSelected]=useState<number|null>(null);return<>
    <div className="public-gallery-grid">{images.map((image,index)=><button className="public-gallery-tile" key={image.url} onClick={()=>setSelected(index)} aria-label={"View "+image.alt_text}><img src={image.url} alt={image.alt_text} width={image.width} height={image.height} loading="lazy"/>{image.caption&&<span>{image.caption}</span>}</button>)}</div>
    <Dialog.Root open={selected!==null} onOpenChange={open=>{if(!open)setSelected(null);}}><Dialog.Portal><Dialog.Overlay className="dialog-overlay"/><Dialog.Content className="public-lightbox">
      <Dialog.Title className="sr-only">Gallery photo</Dialog.Title><Dialog.Description className="sr-only">{selected!==null?images[selected].alt_text:""}</Dialog.Description>
      {selected!==null&&<><img src={images[selected].url} alt={images[selected].alt_text} width={images[selected].width} height={images[selected].height}/><p>{images[selected].caption}</p></>}<Dialog.Close className="dialog-close" aria-label="Close photo"><X size={20}/></Dialog.Close>
    </Dialog.Content></Dialog.Portal></Dialog.Root>
  </>;
}
