import { describe,it,expect,vi } from "vitest";
import { ApiClient } from "@/lib/api/client";
import { parseRosterRow,parseStats,parseStudent,storageDate,STATUS_CODES } from "@/lib/api/operations";
const row={id:"member",member_no:"TEST-1",full_name:"Synthetic Member",photo_url:null,record_id:null,status:null,updated_at:null,marked_at:null,marked_by:"",can_mark:true,can_correct:false};
describe("operational contracts and saves",()=>{
  it("uses one status vocabulary and rejects unknown statuses",()=>{
    expect(STATUS_CODES).toEqual(["PRESENT","LATE","EXCUSED","ABSENT"]);
    expect(()=>parseRosterRow({...row,status:"DONE"})).toThrow();
    expect(parseRosterRow({...row,photo_path:"PRIVATE-SENTINEL",notes:"PRIVATE-SENTINEL"})).not.toHaveProperty("photo_path");
  });
  it("keeps server-calculated rates including unavailable denominators",()=>{
    expect(parseStats({eligible:3,present:1,late:0,excused:2,absent:0,unmarked:0,rate:100}).rate).toBe(100);
    expect(parseStats({eligible:0,present:0,late:0,excused:0,absent:0,unmarked:0,rate:null}).rate).toBeNull();
  });
  it("projects safe student identity and leaves ungranted guardians absent",()=>{
    const value=parseStudent({id:"member",member_id:"member",full_name:"Synthetic Child",member_no:"TEST-1",age:8,status:"ACTIVE",class_id:"class",class_name:"Primary",date_of_birth:"PRIVATE-SENTINEL",household:"PRIVATE-SENTINEL",special_notes:"PRIVATE-SENTINEL"});
    expect(value.guardians).toBeUndefined();expect(JSON.stringify(value)).not.toContain("PRIVATE-SENTINEL");
  });
  it("validates DD/MM/YYYY without accepting rollover dates",()=>{
    expect(storageDate("06/10/2026")).toBe("2026-10-06");expect(()=>storageDate("31/02/2026")).toThrow();expect(()=>storageDate("2026-10-06")).toThrow();
  });
  it("sends CSRF on writes and retains a version conflict as a failed save",async()=>{
    const fetcher=vi.fn<typeof fetch>().mockResolvedValueOnce(new Response(JSON.stringify({csrf_token:"a".repeat(64),authenticated:true})))
      .mockResolvedValueOnce(new Response(JSON.stringify({error:{code:"OPERATION_CONFLICT",message:"PRIVATE-SENTINEL"}}),{status:409}));
    const client=new ApiClient("http://localhost:8000",fetcher);
    await expect(client.mutate("/api/v1/attendance/records/record/correct",{status:"LATE",reason:"Verified",expected_updated_at:"2026-10-06T12:00:00Z"},parseRosterRow)).rejects.toMatchObject({status:409});
    expect(fetcher.mock.calls[1][1]).toMatchObject({method:"POST",credentials:"include",cache:"no-store",headers:{"X-CSRF-Token":"a".repeat(64)}});
  });
  it("uses PATCH with CSRF for lesson edits",async()=>{
    const fetcher=vi.fn<typeof fetch>().mockResolvedValueOnce(new Response(JSON.stringify({csrf_token:"b".repeat(64),authenticated:true}))).mockResolvedValueOnce(new Response(JSON.stringify(row)));
    const client=new ApiClient("http://localhost:8000",fetcher);
    await client.mutate("/api/v1/sunday-school/lessons/lesson",{},parseRosterRow,"PATCH");
    expect(fetcher.mock.calls[1][1]?.method).toBe("PATCH");
  });
});
