"use client";
import {useState} from 'react';
import {Church} from 'lucide-react';
export interface Photo {url:string;alt_text:string;width:number;height:number}
export function PublicPhoto({image,priority=false,sizes='(max-width: 650px) 100vw, (max-width: 1050px) 50vw, 640px',className=''}:{image:Photo|null;priority?:boolean;sizes?:string;className?:string}){
  const[failed,setFailed]=useState(false);
  const variant=(size:number)=>image?.url.replace(/([?&])size=\d+/,'$1size='+size);
  const sources=image?[320,960,1920].map(size=>({size,width:Math.min(size,image.width)})).filter((item,index,list)=>list.findIndex(other=>other.width===item.width)===index):[];
  return<div className={'homepage-photo '+className}>{image&&!failed?<img src={image.url} srcSet={sources.map(item=>variant(item.size)+' '+item.width+'w').join(', ')} sizes={sizes} alt={image.alt_text} width={image.width} height={image.height} loading={priority?'eager':'lazy'} fetchPriority={priority?'high':'auto'} decoding='async' crossOrigin='anonymous' ref={node=>{if(node?.complete&&node.naturalWidth===0)setFailed(true);}} onError={()=>setFailed(true)}/>:<div className='homepage-photo-fallback' aria-hidden='true'><div className='homepage-photo-arch'/><Church strokeWidth={1}/><span>HOPFAN</span></div>}</div>;
}
