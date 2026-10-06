"use client";
export default function ErrorPage({reset}:{reset:()=>void}){return <section className="public-section public-page-section"><p className="public-eyebrow">HOPFAN</p><h1>We couldn’t load this page.</h1><p>Please try again shortly.</p><button className="public-button" onClick={reset}>Try again</button></section>;}
