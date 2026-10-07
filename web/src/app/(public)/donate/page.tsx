import {getPublic,publicMetadata} from "@/features/public/server";
import {DonationForm} from "@/features/public/donation-form";
import type {DonationOptions} from "@/features/public/donation-contracts";
import {HeartHandshake} from "lucide-react";
export const metadata=publicMetadata('Donate','Support HOPFAN ministry, outreach, welfare, missions and church development.','/donate');
export default async function Page(){const options=await getPublic<DonationOptions>('donations/options');
  return<section className="public-section public-page-section"><p className="public-eyebrow">Give with purpose</p><h1>Support the Ministry</h1>
    <p className="public-donation-intro">Your giving supports HOPFAN’s ministry activities, outreach, welfare, missions, programs and church development. Thank you for helping us serve our community.</p>
    <div className="public-donation-layout"><DonationForm options={options}/><aside className="public-giving-aside"><HeartHandshake size={34} aria-hidden="true"/><h2>Every gift has a purpose.</h2><p>Choose the area you would like to support. Your generosity helps the church care for people and carry its mission forward.</p><p>We appreciate every contribution.</p></aside></div>
  </section>;
}
