"use client";
import {useState} from "react";
import Link from "next/link";
import {ArrowRight} from "lucide-react";
export function LeadershipCard({slug,name,role,summary,image,headingLevel=3}:{slug:string;name:string;role:string;summary:string;image:{src:string;alt:string}|null;headingLevel?:2|3}){
  const[failed,setFailed]=useState(false);const Heading=headingLevel===2?"h2":"h3";
  const initials=name.trim().split(/\s+/).slice(0,2).map(word=>Array.from(word)[0]).join('').toUpperCase()||'H';
  return<Link href={'/leadership/'+slug} className="public-leadership-card">
    <div className="public-leadership-photo">{image&&!failed?<img src={image.src} alt={image.alt||name} loading="lazy" ref={node=>{if(node?.complete&&node.naturalWidth===0)setFailed(true);}} onError={()=>setFailed(true)}/>:<span className="public-leadership-initials" aria-hidden="true">{initials}</span>}</div>
    <div className="public-leadership-copy"><Heading>{name}</Heading>{role&&<p className="public-leadership-role">{role}</p>}{summary&&<p className="public-leadership-summary">{summary}</p>}<span className="public-text-link">Meet {name.split(/\s+/)[0]}<ArrowRight size={16} aria-hidden="true"/></span></div>
  </Link>;
}
