import {PublicHome} from '@/features/public/home';
import {getSite,publicMetadata,fallbackConfiguration} from '@/features/public/server';
export async function generateMetadata(){const site=await getSite(),config=site?.configuration??fallbackConfiguration;return publicMetadata(site?.seo_title||config.full_name,site?.seo_description||site?.hero.text||'Discover HOPFAN, our weekly services, ministry community and upcoming events.','/',site?.hero.image);}
export default function Page(){return <PublicHome/>;}
