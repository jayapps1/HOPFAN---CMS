import Link from "next/link";
import Image from "next/image";
import {ArrowRight,MapPin,Mail,Phone,CalendarDays} from "lucide-react";
import {getSite,getPublic,publicImageUrl,fallbackConfiguration,type PublicContent,type PublicEvent,type Configuration,type PublicPage} from "./server";
import {PublicIntakeForm} from "./intake-form";
import {PublicGalleryGrid} from "./gallery";
import {LeadershipCard} from "./leadership-card";
import {notFound} from "next/navigation";

export function PublicFooter({config}:{config:Configuration}){
  return<footer className="public-footer"><div className="public-footer-grid"><div><Link href="/" className="public-brand"><Image src="/brand/hopfan-logo.png" alt="" width={42} height={45}/><span>{config.church_name}<small>{config.full_name}</small></span></Link><p>{config.footer_text||config.tagline}</p></div>
    <div><h2>Explore</h2><Link href="/about">About HOPFAN</Link><Link href="/leadership">Leadership</Link><Link href="/ministries">Ministries</Link><Link href="/announcements">Announcements</Link><Link href="/donate">Donate</Link></div>
    <div><h2>Gather with us</h2>{config.service_times.length?config.service_times.map(time=><p key={time.name}><strong>{time.name}</strong><br/>{time.schedule}</p>):<Link href="/new-here">Plan your visit</Link>}</div>
    <div><h2>Connect</h2>{config.address&&<p>{config.address}</p>}{config.public_phone&&<a href={"tel:"+config.public_phone}>{config.public_phone}</a>}{config.public_email&&<a href={"mailto:"+config.public_email}>{config.public_email}</a>}{config.social_links.map(link=><a href={link.url} key={link.label} rel="noopener noreferrer">{link.label}</a>)}<Link href="/contact">Contact the church</Link></div></div>
    <div className="public-footer-bottom"><span>© {new Date().getUTCFullYear()} {config.church_name}</span><Link href="/login">Staff and leaders portal</Link></div>
  </footer>;
}
export function ContentCard({item,section}:{item:PublicContent;section:string}){
  return<Link href={"/"+section+"/"+item.slug} className="public-content-card">{item.image?<img src={publicImageUrl(item.image)} alt={item.image.alt_text} width={item.image.width} height={item.image.height} loading="lazy"/>:<div className="public-card-pattern" aria-hidden="true"><span/></div>}
    <div><p className="public-eyebrow">{item.series||item.public_title||section.replace("-"," ")}</p><h2>{item.public_name||item.title}</h2>{item.speaker&&<p>{item.speaker} · {item.sermon_date}</p>}<p>{item.summary}</p><span className="public-text-link">Learn more<ArrowRight size={16} aria-hidden="true"/></span></div></Link>;
}
function EventCard({item,timeZone}:{item:PublicEvent;timeZone:string}){return<Link href={"/events/"+item.slug} className="public-event-card"><div className="public-event-date"><CalendarDays size={21}/><time dateTime={item.start_datetime}>{new Intl.DateTimeFormat("en-GB",{day:"numeric",month:"short",timeZone}).format(new Date(item.start_datetime))}</time></div><div><h2>{item.title}</h2><p>{item.location||"Details to be confirmed"}</p></div><ArrowRight size={19} aria-hidden="true"/></Link>;}
export {PublicHome} from './home';
const collectionMap:Record<string,{api:string;title:string;eyebrow:string;kind?:string}>={ministries:{api:"ministries",title:"Our ministries",eyebrow:"Connect and serve"},leadership:{api:"leadership",title:"Our leadership",eyebrow:"Serving the church"},sermons:{api:"sermons",title:"Sermons",eyebrow:"Grow in faith"},gallery:{api:"gallery",title:"Church gallery",eyebrow:"Shared moments"},events:{api:"events",title:"Events",eyebrow:"Life together"},announcements:{api:"announcements",title:"Announcements",eyebrow:"Stay connected"},testimonies:{api:"testimonies",title:"Testimonies",eyebrow:"Stories of faith"}};
export async function PublicCollection({section,searchParams}:{section:string;searchParams:Promise<Record<string,string|undefined>>}){
  const meta=collectionMap[section];if(!meta)notFound();const query=await searchParams;const params=new URLSearchParams({page_number:query.page??"1",search:query.search??""});
  if(section==="events"&&query.past==="true")params.set("past","true");if(section==="sermons"){if(query.series)params.set("series",query.series);if(query.speaker)params.set("speaker",query.speaker);}
  const timeZone=section==="events"?(await getSite())?.configuration.timezone??"UTC":"UTC";
  const data=await getPublic<PublicPage<PublicContent&PublicEvent&{body:string}>>(meta.api+"?"+params);
  return<section className="public-section public-page-section"><p className="public-eyebrow">{meta.eyebrow}</p><h1>{meta.title}</h1>
    {section==="sermons"&&<form className="public-search"><label>Search sermons<input name="search" defaultValue={query.search} placeholder="Title or message"/></label><label>Series<input name="series" defaultValue={query.series}/></label><label>Speaker<input name="speaker" defaultValue={query.speaker}/></label><button className="public-button" type="submit">Search</button></form>}
    {section==="events"&&<nav className="public-filter-links" aria-label="Event period"><Link href="/events">Upcoming</Link><Link href="/events?past=true">Past events</Link></nav>}
    {!data?<div className="public-empty"><h2>We couldn’t load this content.</h2><p>Please try again shortly.</p></div>:!data.items.length?<div className="public-empty"><h2>No {section} are currently published.</h2><p>Please check back for updates from the church.</p></div>:section==='leadership'?<div className="public-leadership-grid">{data.items.map(item=><LeadershipCard key={item.slug} slug={item.slug} name={item.public_name||item.title} role={item.public_title||''} summary={item.summary} image={item.image?{src:publicImageUrl(item.image),alt:item.image.alt_text}:null} headingLevel={2}/>)}</div>:section==="events"?<div className="public-events-list">{data.items.map(item=><EventCard key={item.slug} item={item} timeZone={timeZone}/>)}</div>:section==="announcements"?<div className="public-notices">{data.items.map(item=><article key={item.slug} id={item.slug}><h2>{item.title}</h2><p>{item.body}</p></article>)}</div>:<div className="public-card-grid">{data.items.map(item=><ContentCard key={item.slug} item={item} section={section}/>)}</div>}
    {data&&data.pages>1&&<nav className="public-pagination" aria-label="Public pagination">{data.page>1&&<Link href={"?"+new URLSearchParams({...query,page:String(data.page-1)} as Record<string,string>)}>Previous</Link>}<span>Page {data.page} of {data.pages}</span>{data.page<data.pages&&<Link href={"?"+new URLSearchParams({...query,page:String(data.page+1)} as Record<string,string>)}>Next</Link>}</nav>}
  </section>;
}
export async function PublicDetail({section,slug}:{section:string;slug:string}){
  const item=await getPublic<PublicContent&PublicEvent>(section+"/"+encodeURIComponent(slug));if(!item)notFound();
  const timeZone=section==="events"?(await getSite())?.configuration.timezone??"UTC":"UTC";
  return<article className="public-section public-article"><Link className="public-text-link" href={"/"+section}>Back to {section}<ArrowRight size={16}/></Link><p className="public-eyebrow">{item.public_title||item.series||section}</p><h1>{item.public_name||item.title}</h1>
    {item.image&&<img className="public-article-image" src={publicImageUrl(item.image)} alt={item.image.alt_text} width={item.image.width} height={item.image.height}/>}
    {section==="events"&&<div className="public-event-facts"><time dateTime={item.start_datetime}>{new Intl.DateTimeFormat("en-GB",{dateStyle:"long",timeStyle:"short",timeZone}).format(new Date(item.start_datetime))} {timeZone}</time><p>{item.location}</p></div>}
    {section==="sermons"&&<><p>{item.speaker} · {item.sermon_date} · {item.scripture_reference}</p>{item.video_embed_url&&<iframe className="public-video" src={item.video_embed_url} title={item.title} allow="fullscreen; picture-in-picture" allowFullScreen loading="lazy" referrerPolicy="no-referrer"/>}{item.audio_url&&<audio controls preload="none" src={item.audio_url}>Audio playback is unavailable.</audio>}</>}
    <p className="public-summary">{item.summary||item.description}</p><div className="public-prose">{item.body}</div>
    {item.meeting_information&&<section><h2>Gather with this ministry</h2><p>{item.meeting_information}</p></section>}{item.public_contact&&<p>{item.public_contact}</p>}
    {section==="gallery"&&item.images&&<PublicGalleryGrid images={item.images.map(image=>({...image,url:publicImageUrl(image)}))}/>}
  </article>;
}
function ContactDetails({config}:{config:Configuration}){
  return<div className="public-contact-details">{config.address&&<p><MapPin size={21}/>{config.address}</p>}{config.public_phone&&<a href={"tel:"+config.public_phone}><Phone size={21}/>{config.public_phone}</a>}{config.public_email&&<a href={"mailto:"+config.public_email}><Mail size={21}/>{config.public_email}</a>}{config.map_url&&<a className="public-text-link" href={config.map_url} rel="noopener noreferrer">Get directions<ArrowRight size={18}/></a>}</div>;
}
export async function PublicInformation({slug}:{slug:string}){
  const [site,page]=await Promise.all([getSite(),getPublic<PublicContent>("pages/"+slug)]);
  const config=site?.configuration??fallbackConfiguration;
  const titles:Record<string,string>={about:"About HOPFAN","sunday-school":"Sunday School","new-here":"Plan your visit",contact:"Contact HOPFAN",give:"Giving","prayer-request":"Share a prayer request"};
  return<section className="public-section public-page-section"><p className="public-eyebrow">{config.full_name}</p><h1>{page?.title||titles[slug]||"HOPFAN"}</h1>{page?.summary&&<p className="public-summary">{page.summary}</p>}{page?.image&&<img className="public-article-image" src={publicImageUrl(page.image)} alt={page.image.alt_text} width={page.image.width} height={page.image.height}/>}
    {page?.body&&<div className="public-prose">{page.body}</div>}
    {slug==="give"&&!page&&<div className="public-empty"><h2>Online giving will be available soon.</h2><p>Contact the church for approved giving information.</p></div>}
    {["about","sunday-school"].includes(slug)&&!page&&<div className="public-empty"><h2>Church information is being prepared.</h2><p>Please contact the church for details.</p><Link className="public-text-link" href="/contact">Contact HOPFAN<ArrowRight size={17}/></Link></div>}
    {["new-here","contact"].includes(slug)&&<><ContactDetails config={config}/>{config.service_times.length>0&&<div className="public-service-times">{config.service_times.map(time=><article key={time.name}><h2>{time.name}</h2><p>{time.schedule}</p></article>)}</div>}</>}
    {slug==="prayer-request"&&config.prayer_form_enabled&&<PublicIntakeForm kind="PRAYER"/>}
    {slug==="new-here"&&config.visitor_form_enabled&&<PublicIntakeForm kind="VISITOR"/>}
    {slug==="contact"&&config.contact_form_enabled&&<PublicIntakeForm kind="CONTACT"/>}
  </section>;
}
