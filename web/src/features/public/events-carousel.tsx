"use client";
import {useRef,useState,useId} from 'react';
import Link from 'next/link';
import {ChevronLeft,ChevronRight,ArrowRight,Clock3,MapPin} from 'lucide-react';
import {PublicPhoto} from './public-photo';
import {eventFacts} from './home-format';
import type {PublicEvent} from './server';
export function EventsCarousel({events,timeZone}:{events:PublicEvent[];timeZone:string}){
  const track=useRef<HTMLDivElement>(null),[active,setActive]=useState(0),id=useId();
  function move(index:number){const node=track.current;if(!node)return;const slide=node.children[index] as HTMLElement|undefined;if(!slide)return;
    const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    node.scrollTo({left:slide.offsetLeft-node.offsetLeft,behavior:reduced?'instant':'smooth'});setActive(index);
  }
  function position(){const node=track.current;if(!node)return;let closest=0,distance=Infinity;
    Array.from(node.children).forEach((child,index)=>{const gap=Math.abs((child as HTMLElement).offsetLeft-node.offsetLeft-node.scrollLeft);if(gap<distance){closest=index;distance=gap;}});setActive(closest);
  }
  return<div className='homepage-carousel' role='region' aria-roledescription='carousel' aria-label='Upcoming events'>
    <div className='homepage-carousel-controls'><span aria-live='polite' aria-atomic='true'>Event {active+1} of {events.length}</span><div><button aria-label='Previous event' aria-controls={id} disabled={active===0} onClick={()=>move(active-1)}><ChevronLeft size={22}/></button><button aria-label='Next event' aria-controls={id} disabled={active===events.length-1} onClick={()=>move(active+1)}><ChevronRight size={22}/></button></div></div>
    <div className='homepage-carousel-track' ref={track} id={id} role='group' onScroll={position} tabIndex={0} aria-label='Event slides. Use left and right arrow keys to browse.' onKeyDown={event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();move(event.key==='Home'?0:event.key==='End'?events.length-1:Math.max(0,Math.min(events.length-1,active+(event.key==='ArrowRight'?1:-1))));}}}>
      {events.map((event,index)=>{const facts=eventFacts(event,timeZone);return<article className='homepage-event' key={event.slug} role='group' aria-roledescription='slide' aria-label={`${index+1} of ${events.length}: ${event.title}`}>
        <div className='homepage-event-visual'><PublicPhoto image={event.image} sizes='(max-width: 700px) 92vw, 500px'/><div className='homepage-event-date'><span>{facts.month}</span><strong>{facts.day}</strong>{facts.range&&<small>{facts.range}</small>}</div></div>
        <div className='homepage-event-copy'><p className='public-eyebrow'>{event.event_type.replaceAll('_',' ')}</p><h3>{event.title}</h3>{event.description&&<p className='homepage-excerpt'>{event.description}</p>}<div className='homepage-event-details'><p><Clock3 size={18} aria-hidden='true'/><time dateTime={event.start_datetime}>{facts.weekday} · {facts.time}</time></p>{event.location&&<p><MapPin size={18} aria-hidden='true'/>{event.location}</p>}</div><Link className='public-button' href={'/events/'+event.slug}>View Event<ArrowRight size={18} aria-hidden='true'/></Link></div>
      </article>;})}
    </div>
    {events.length>1&&<div className='homepage-carousel-dots' role='group' aria-label='Choose an event'>{events.map((event,index)=><button key={event.slug} aria-label={`Show event ${index+1}: ${event.title}`} aria-disabled={active===index} onClick={()=>{if(active!==index)move(index);}} data-active={active===index}><span/></button>)}</div>}
  </div>;
}
