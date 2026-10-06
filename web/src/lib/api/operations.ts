import { obj,str,num,bool,nullable,array,parseOptions,parsePage,type Summary } from "./workspace";
import { api } from "./client";
export const STATUS_CODES = ["PRESENT","LATE","EXCUSED","ABSENT"] as const;
export type AttendanceStatus = typeof STATUS_CODES[number];
export function statusLabel(code: string) { return code.toLowerCase().replaceAll("_"," ").replace(/^./,value=>value.toUpperCase()); }
export interface Stats { eligible:number; present:number; late:number; excused:number; absent:number; unmarked:number; rate:number|null }
export interface Session { id:string; title:string; session_date:string; sessionState:string; updated_at:string; context_id:string|null; context_name:string; session_type:string; stats:Stats|null; actions:Record<string,boolean> }
export interface RosterRow { id:string; member_no:string; full_name:string; photo_url:string|null; record_id:string|null; status:AttendanceStatus|null; updated_at:string|null; marked_at:string|null; marked_by:string; can_mark:boolean; can_correct:boolean }
export interface MarkResult { row:RosterRow; summary:Stats }
export interface AttendanceOptions { can_create:boolean; can_create_global:boolean; ministries:Summary[]; create_ministries:Summary[]; session_types:string[]; statuses:string[] }
export interface SchoolClass { id:string; name:string; code:string; description:string; minimum_age:number|null; maximum_age:number|null; room_location:string; capacity:number|null; status:string; students:number|null; teachers:number|null }
export interface Guardian { full_name:string; relationship:string; phone:string; can_receive_sms:boolean }
export interface Student { id:string; member_id:string; full_name:string; member_no:string; age:number|null; status:string; class_id:string|null; class_name:string; guardians?:Guardian[]; attendance_rate?:number|null; history?:{class_name:string; start_date:string; end_date:string|null; is_current:boolean}[] }
export interface Teacher { id:string; member_id:string; full_name:string; member_no:string; class_id:string; class_name:string; role_label:string; start_date:string; end_date:string|null }
export interface Lesson { id:string; title:string; lesson_date:string; topic:string; scripture_reference:string; objective:string; lesson_summary:string; teacher_notes:string; status:string; applies_to_all:boolean; classes:Summary[]; updated_at:string; can_edit:boolean }
export interface SchoolDashboard { classes:number; active_classes:number; students:number|null; teachers:number|null; present_last_sunday:number|null; rate:number|null }
export interface ReportRow { id:string; label:string; member_no:string|null; eligible:number; present:number; late:number; excused:number; absent:number; rate:number|null }
export function parseStats(value:unknown):Stats {const o=obj(value);return {eligible:num(o.eligible),present:num(o.present),late:num(o.late),excused:num(o.excused),absent:num(o.absent),unmarked:num(o.unmarked),rate:nullable(o.rate,num)};}
function actions(value:unknown):Record<string,boolean> {if(value==null)return {};const o=obj(value);return Object.fromEntries(["open","close","reopen","lock","unlock"].filter(key=>key in o).map(key=>[key,bool(o[key])]))}
export function parseSession(value:unknown):Session {const o=obj(value);return {id:str(o.id),title:str(o.title),session_date:str(o.session_date),sessionState:str(o.state),updated_at:str(o.updated_at),context_id:nullable(o.ministry_id,str),context_name:str(o.ministry_name),session_type:str(o.session_type),stats:nullable(o.stats,parseStats),actions:actions(o.actions)};}
export function parseSchoolSession(value:unknown):Session {const o=obj(value);return {id:str(o.id),title:str(o.title),session_date:str(o.session_date),sessionState:str(o.state),updated_at:str(o.updated_at),context_id:str(o.class_id),context_name:str(o.class_name),session_type:"Sunday School",stats:nullable(o.stats,parseStats),actions:actions(o.actions)};}
function parseStatus(value:unknown):AttendanceStatus {const code=str(value);if(!STATUS_CODES.some(status=>status===code))throw new Error();return code as AttendanceStatus;}
export function parseRosterRow(value:unknown):RosterRow {const o=obj(value);return {id:str(o.id),member_no:str(o.member_no),full_name:str(o.full_name),photo_url:nullable(o.photo_url,str),record_id:nullable(o.record_id,str),status:nullable(o.status,parseStatus),updated_at:nullable(o.updated_at,str),marked_at:nullable(o.marked_at,str),marked_by:str(o.marked_by),can_mark:bool(o.can_mark),can_correct:bool(o.can_correct)};}
export function parseMark(value:unknown):MarkResult {const o=obj(value);return {row:parseRosterRow(o.row),summary:parseStats(o.summary)};}
export function parseAttendanceOptions(value:unknown):AttendanceOptions {const o=obj(value);return {can_create:bool(o.can_create),can_create_global:bool(o.can_create_global),ministries:parseOptions(o.ministries),create_ministries:parseOptions(o.create_ministries),session_types:array(o.session_types,str),statuses:array(o.statuses,str)};}
export function parseClass(value:unknown):SchoolClass {const o=obj(value);return {id:str(o.id),name:str(o.name),code:str(o.code),description:str(o.description),minimum_age:nullable(o.minimum_age,num),maximum_age:nullable(o.maximum_age,num),room_location:str(o.room_location),capacity:nullable(o.capacity,num),status:str(o.status),students:nullable(o.students,num),teachers:nullable(o.teachers,num)};}
export function parseStudent(value:unknown):Student {const o=obj(value);const result:Student={id:str(o.id),member_id:str(o.member_id),full_name:str(o.full_name),member_no:str(o.member_no),age:nullable(o.age,num),status:str(o.status),class_id:nullable(o.class_id,str),class_name:str(o.class_name)};
if(o.guardians!=null)result.guardians=array(o.guardians,value=>{const g=obj(value);return {full_name:str(g.full_name),relationship:str(g.relationship),phone:str(g.phone),can_receive_sms:bool(g.can_receive_sms)}});
if("attendance_rate" in o)result.attendance_rate=nullable(o.attendance_rate,num);
if(o.history!=null)result.history=array(o.history,value=>{const h=obj(value);return {class_name:str(h.class_name),start_date:str(h.start_date),end_date:nullable(h.end_date,str),is_current:bool(h.is_current)}});return result;}
export function parseTeacher(value:unknown):Teacher {const o=obj(value);return {id:str(o.id),member_id:str(o.member_id),full_name:str(o.full_name),member_no:str(o.member_no),class_id:str(o.class_id),class_name:str(o.class_name),role_label:str(o.role_label),start_date:str(o.start_date),end_date:nullable(o.end_date,str)};}
export function parseLesson(value:unknown):Lesson {const o=obj(value);return {id:str(o.id),title:str(o.title),lesson_date:str(o.lesson_date),topic:str(o.topic),scripture_reference:str(o.scripture_reference),objective:str(o.objective),lesson_summary:str(o.lesson_summary),teacher_notes:str(o.teacher_notes),status:str(o.status),applies_to_all:bool(o.applies_to_all),classes:parseOptions(o.classes),updated_at:str(o.updated_at),can_edit:bool(o.can_edit)};}
export function parseSchoolDashboard(value:unknown):SchoolDashboard {const o=obj(value);return {classes:num(o.classes),active_classes:num(o.active_classes),students:nullable(o.students,num),teachers:nullable(o.teachers,num),present_last_sunday:nullable(o.present_last_sunday,num),rate:nullable(o.rate,num)};}
export function parseReport(value:unknown):ReportRow {const o=obj(value);return {id:str(o.id),label:str(o.label),member_no:nullable(o.member_no,str),eligible:num(o.eligible),present:num(o.present),late:num(o.late),excused:num(o.excused),absent:num(o.absent),rate:nullable(o.rate,num)};}
export const parseSessions=parsePage(parseSession),parseSchoolSessions=parsePage(parseSchoolSession),parseRoster=parsePage(parseRosterRow),
parseClasses=parsePage(parseClass),parseStudents=parsePage(parseStudent),parseTeachers=parsePage(parseTeacher),parseLessons=parsePage(parseLesson),parseReports=parsePage(parseReport),parseClassOptions=parsePage(value=>{const o=obj(value);return {id:str(o.id),name:str(o.name)};});
export function displayDate(value:string) {const [year,month,day]=value.slice(0,10).split("-");return day && month && year ? `${day}/${month}/${year}` : value;}
export function storageDate(value:string) {if(!/^\d{2}\/\d{2}\/\d{4}$/.test(value))throw new Error("Enter a date as DD/MM/YYYY.");const [day,month,year]=value.split("/");const date=new Date(`${year}-${month}-${day}T12:00:00Z`);if(Number.isNaN(date.getTime())||date.getUTCDate()!==Number(day)||date.getUTCMonth()+1!==Number(month))throw new Error("Choose a valid date.");return `${year}-${month}-${day}`;}
export async function loadClassOptions(path:string,signal:AbortSignal) {
  const first=await api.get(path+"?page_size=100",parseClassOptions,signal);
  const items=[...first.items];
  for(let page=2;page<=first.pages;page++){
    if(signal.aborted)throw new Error("Request cancelled");
    const result=await api.get(path+"?page_size=100&page="+page,parseClassOptions,signal);
    items.push(...result.items);
  }
  return {...first,items};
}
