import {describe,it,expect} from "vitest";
import {parseSettings,parseMedia,parseInquiry} from "@/lib/api/content";
import {jsonLd,canonicalOrigin} from "@/features/public/server";
describe("published content boundaries",()=>{
  it("strips storage references from the media contract",()=>{
    const data=parseMedia({id:"asset",alt_text:"Approved image",caption:"",status:"DRAFT",width:320,height:180,contains_children:false,consent_attested:false,consent_reference:"",updated_at:"2026-10-06T12:00:00Z",preview_url:"/api/v1/website/media/asset/preview",storage_key:"PRIVATE-SENTINEL"});
    expect(JSON.stringify(data)).not.toContain("PRIVATE-SENTINEL");
  });
  it("keeps inquiry details inside an explicit private response",()=>{
    const data=parseInquiry({id:"inquiry",kind:"PRAYER",first_name:"",last_name:"",phone:"",email:"",message:"Private request",private_notes:"",status:"NEW",contact_permission:false,preferred_contact:"NONE",visit_date:null,assigned_to:null,converted_member_id:null,updated_at:"now",created_at:"now",password_hash:"PRIVATE-SENTINEL"});
    expect(JSON.stringify(data)).not.toContain("PRIVATE-SENTINEL");expect(data.message).toBe("Private request");
  });
  it("escapes script-closing characters in structured metadata",()=>{
    expect(jsonLd({name:"</script><script>alert(1)</script>"})).not.toContain("<");
  });
  it("does not fabricate a canonical deployment domain",()=>{
    expect(canonicalOrigin()).toBeNull();
  });
  it("accepts empty editable service/contact configuration",()=>{
    expect(parseSettings({updated_at:null,published_at:null,data:{church_name:"HOPFAN",full_name:"House of Prayer for All Nations",tagline:"",address:"",public_phone:"",public_email:"",service_times:[],social_links:[],map_url:"",footer_text:"",contact_form_enabled:true,visitor_form_enabled:true,prayer_form_enabled:true}}).data.service_times).toEqual([]);
  });
});
