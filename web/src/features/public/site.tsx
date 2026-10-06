import Link from "next/link";
import Image from "next/image";
import {ArrowRight,MapPin,Mail,Phone,Heart,CalendarDays} from "lucide-react";
import {getSite,getPublic,publicImageUrl,fallbackConfiguration,canonicalOrigin,jsonLd,type PublicContent,type PublicEvent,type Configuration,type PublicPage} from "./server";
import {PublicIntakeForm} from "./intake-form";
import {PublicGalleryGrid} from "./gallery";
import {notFound} from "next/navigation";

export function PublicFooter({config}:{config:Configuration}){
  return<footer className="public-footer"><div className="public-footer-grid"><div><Link href="/" className="public-brand"><Image src="/brand/hopfan-logo.png" alt="" width={42} height={45}/><span>{config.church_name}<small>{config.full_name}</small></span></Link><p>{config.footer_text||config.tagline}</p></div>
    <div><h2>Explore</h2><Link href="/about">About HOPFAN</Link><Link href="/leadership">Leadership</Link><Link href="/ministries">Ministries</Link><Link href="/announcements">Announcements</Link><Link href="/give">Giving</Link></div>
    <div><h2>Gather with us</h2>{config.service_times.length?config.service_times.map(time=><p key={time.name}><strong>{time.name}</strong><br/>{time.schedule}</p>):<Link href="/new-here">Plan your visit</Link>}</div>
    <div><h2>Connect</h2>{config.address&&<p>{config.address}</p>}{config.public_phone&&<a href={"tel:"+config.public_phone}>{config.public_phone}</a>}{config.public_email&&<a href={"mailto:"+config.public_email}>{config.public_email}</a>}{config.social_links.map(link=><a href={link.url} key={link.label} rel="noopener noreferrer">{link.label}</a>)}<Link href="/contact">Contact the church</Link></div></div>
    <div className="public-footer-bottom"><span>© {new Date().getUTCFullYear()} {config.church_name}</span><Link href="/login">Staff and leaders portal</Link></div>
  </footer>;
}
function SectionTitle({eyebrow,title,href,label="Explore"}:{eyebrow:string;title:string;href?:string;label?:string}){
  return<div className="public-section-heading"><div><p className="public-eyebrow">{eyebrow}</p><h2>{title}</h2></div>{href&&<Link href={href} className="public-text-link">{label}<ArrowRight size={18} aria-hidden="true"/></Link>}</div>;
}
export function ContentCard({item,section}:{item:PublicContent;section:string}){
  return<Link href={"/"+section+"/"+item.slug} className="public-content-card">{item.image?<img src={publicImageUrl(item.image)} alt={item.image.alt_text} width={item.image.width} height={item.image.height} loading="lazy"/>:<div className="public-card-pattern" aria-hidden="true"><span/></div>}
    <div><p className="public-eyebrow">{item.series||item.public_title||section.replace("-"," ")}</p><h2>{item.public_name||item.title}</h2>{item.speaker&&<p>{item.speaker} · {item.sermon_date}</p>}<p>{item.summary}</p><span className="public-text-link">Learn more<ArrowRight size={16} aria-hidden="true"/></span></div></Link>;
}
function EventCard({item}:{item:PublicEvent}){return<Link href={"/events/"+item.slug} className="public-event-card"><div className="public-event-date"><CalendarDays size={21}/><time dateTime={item.start_datetime}>{new Intl.DateTimeFormat("en-GB",{day:"numeric",month:"short",timeZone:"UTC"}).format(new Date(item.start_datetime))}</time></div><div><h2>{item.title}</h2><p>{item.location||"Details to be confirmed"}</p></div><ArrowRight size={19} aria-hidden="true"/></Link>;}
export async function PublicHome(){
  const site=await getSite();const config=site?.configuration??fallbackConfiguration;
  const hero=site?.hero??{headline:"Welcome to HOPFAN.",text:"",primary_label:"Plan your visit",primary_href:"/new-here",secondary_label:"Explore ministries",secondary_href:"/ministries",image:null};
  const sections=site?.section_order??["visit","prayer","contact"];
  return<><script type="application/ld+json" dangerouslySetInnerHTML={{__html:jsonLd({"@context":"https://schema.org","@type":"Organization",name:config.full_name||config.church_name,url:canonicalOrigin()??undefined,telephone:config.public_phone||undefined,email:config.public_email||undefined})}}/><section className={"public-hero "+(hero.image?"public-hero-with-image":"")} style={hero.image?{backgroundImage:`linear-gradient(90deg,#071f34e8,#071f342a),url("${publicImageUrl(hero.image)}")`}:undefined}>
    <div className="public-hero-copy"><p className="public-eyebrow">{config.full_name}</p><h1>{hero.headline}</h1>{hero.text&&<p className="public-hero-description">{hero.text}</p>}<div className="public-hero-actions"><Link className="public-button" href={hero.primary_href}>{hero.primary_label}<ArrowRight size={18}/></Link><Link className="public-button public-button-outline" href={hero.secondary_href}>{hero.secondary_label}</Link></div></div>
    {!hero.image&&<div className="public-hero-art" aria-hidden="true"><div/><div/><span>HOPFAN</span></div>}
  </section>
  {!site&&<p className="public-service-notice" role="status">Published church information is temporarily unavailable. Please try again shortly.</p>}
  {sections.map(section=>{
    if(section==="welcome"&&site?.welcome)return<section className="public-section public-welcome" key={section}><p className="public-eyebrow">A warm welcome</p><h2>{site.welcome.title}</h2><p>{site.welcome.summary||site.welcome.body}</p><Link className="public-text-link" href="/about">Meet HOPFAN<ArrowRight size={18}/></Link></section>;
    if(section==="services"&&config.service_times.length)return<section className="public-section public-service-times" key={section}><SectionTitle eyebrow="Come as you are" title="Gather with us"/><div>{config.service_times.map(time=><article key={time.name}><h3>{time.name}</h3><p>{time.schedule}</p></article>)}</div></section>;
    if(section==="events"&&site?.events.length)return<section className="public-section" key={section}><SectionTitle eyebrow="Life together" title="Upcoming events" href="/events" label="All events"/><div className="public-events-list">{site.events.map(item=><EventCard item={item} key={item.slug}/>)}</div></section>;
    if(["ministries","sermons","gallery"].includes(section)){
      const items=section==="ministries"?site?.ministries:section==="sermons"?site?.sermons:site?.galleries;
      if(!items?.length)return null;return<section className="public-section" key={section}><SectionTitle eyebrow={section==="sermons"?"Grow in faith":section==="gallery"?"Shared moments":"Find your community"} title={section==="sermons"?"The latest messages":section==="gallery"?"Church life in pictures":"Our ministries"} href={"/"+section}/><div className="public-card-grid">{items.slice(0,3).map(item=><ContentCard key={item.slug} item={item} section={section}/>)}</div></section>;
    }
    if(section==="announcements"&&site?.announcements.length)return<section className="public-section public-notices" key={section}><SectionTitle eyebrow="Stay connected" title="Church announcements" href="/announcements"/>{site.announcements.slice(0,3).map(item=><article key={item.slug}><h3>{item.title}</h3><p>{item.body}</p></article>)}</section>;
    if(section==="prayer"&&config.prayer_form_enabled)return<section className="public-section public-prayer-banner" key={section}><Heart size={30}/><div><p className="public-eyebrow">You can reach out</p><h2>Share a prayer request.</h2><p>Your request goes privately to the church’s authorized prayer team.</p></div><Link className="public-button" href="/prayer-request">Request prayer<ArrowRight size={18}/></Link></section>;
    if(section==="visit")return<section className="public-section public-visit-banner" key={section}><p className="public-eyebrow">Your first visit</p><h2>Let’s help you feel at home.</h2><Link className="public-text-link" href="/new-here">Plan your visit<ArrowRight size={18}/></Link></section>;
    if(section==="contact"&&(config.address||config.public_phone||config.public_email))return<section className="public-section" key={section}><SectionTitle eyebrow="Find us" title="Connect with HOPFAN"/><ContactDetails config={config}/></section>;
    return null;
  })}</>;
}
const collectionMap:Record<string,{api:string;title:string;eyebrow:string;kind?:string}>={ministries:{api:"ministries",title:"Our ministries",eyebrow:"Connect and serve"},leadership:{api:"leadership",title:"Our leadership",eyebrow:"Serving the church"},sermons:{api:"sermons",title:"Sermons",eyebrow:"Grow in faith"},gallery:{api:"gallery",title:"Church gallery",eyebrow:"Shared moments"},events:{api:"events",title:"Events",eyebrow:"Life together"},announcements:{api:"announcements",title:"Announcements",eyebrow:"Stay connected"},testimonies:{api:"testimonies",title:"Testimonies",eyebrow:"Stories of faith"}};
export async function PublicCollection({section,searchParams}:{section:string;searchParams:Promise<Record<string,string|undefined>>}){
  const meta=collectionMap[section];if(!meta)notFound();const query=await searchParams;const params=new URLSearchParams({page_number:query.page??"1",search:query.search??""});
  if(section==="events"&&query.past==="true")params.set("past","true");if(section==="sermons"){if(query.series)params.set("series",query.series);if(query.speaker)params.set("speaker",query.speaker);}
  const data=await getPublic<PublicPage<PublicContent&PublicEvent&{body:string}>>(meta.api+"?"+params);
  return<section className="public-section public-page-section"><p className="public-eyebrow">{meta.eyebrow}</p><h1>{meta.title}</h1>
    {section==="sermons"&&<form className="public-search"><label>Search sermons<input name="search" defaultValue={query.search} placeholder="Title or message"/></label><label>Series<input name="series" defaultValue={query.series}/></label><label>Speaker<input name="speaker" defaultValue={query.speaker}/></label><button className="public-button" type="submit">Search</button></form>}
    {section==="events"&&<nav className="public-filter-links" aria-label="Event period"><Link href="/events">Upcoming</Link><Link href="/events?past=true">Past events</Link></nav>}
    {!data?<div className="public-empty"><h2>We couldn’t load this content.</h2><p>Please try again shortly.</p></div>:!data.items.length?<div className="public-empty"><h2>No {section} are currently published.</h2><p>Please check back for updates from the church.</p></div>:section==="events"?<div className="public-events-list">{data.items.map(item=><EventCard key={item.slug} item={item}/>)}</div>:section==="announcements"?<div className="public-notices">{data.items.map(item=><article key={item.slug}><h2>{item.title}</h2><p>{item.body}</p></article>)}</div>:<div className="public-card-grid">{data.items.map(item=><ContentCard key={item.slug} item={item} section={section}/>)}</div>}
    {data&&data.pages>1&&<nav className="public-pagination" aria-label="Public pagination">{data.page>1&&<Link href={"?"+new URLSearchParams({...query,page:String(data.page-1)} as Record<string,string>)}>Previous</Link>}<span>Page {data.page} of {data.pages}</span>{data.page<data.pages&&<Link href={"?"+new URLSearchParams({...query,page:String(data.page+1)} as Record<string,string>)}>Next</Link>}</nav>}
  </section>;
}
export async function PublicDetail({section,slug}:{section:string;slug:string}){
  const item=await getPublic<PublicContent&PublicEvent>(section+"/"+encodeURIComponent(slug));if(!item)notFound();
  return<article className="public-section public-article"><Link className="public-text-link" href={"/"+section}>Back to {section}<ArrowRight size={16}/></Link><p className="public-eyebrow">{item.public_title||item.series||section}</p><h1>{item.public_name||item.title}</h1>
    {item.image&&<img className="public-article-image" src={publicImageUrl(item.image)} alt={item.image.alt_text} width={item.image.width} height={item.image.height}/>}
    {section==="events"&&<div className="public-event-facts"><time dateTime={item.start_datetime}>{new Intl.DateTimeFormat("en-GB",{dateStyle:"long",timeStyle:"short",timeZone:"UTC"}).format(new Date(item.start_datetime))} UTC</time><p>{item.location}</p></div>}
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
