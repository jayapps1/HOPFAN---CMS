import type {PublicEvent} from './server';
export const homeSectionOrder=['services','events','welcome','ministries','leadership','sermons','sunday-school','announcements','gallery','donate','prayer','visit','contact'];
export function localClock(value:string|null){if(!value)return '';const [hour,minute]=value.split(':').map(Number);return `${hour%12||12}:${String(minute).padStart(2,'0')} ${hour<12?'AM':'PM'}`;}
export function eventFacts(event:PublicEvent,timeZone:string){const date=new Date(event.start_datetime);const end=event.end_datetime?new Date(event.end_datetime):null;
  const format=(options:Intl.DateTimeFormatOptions,dateValue=date)=>new Intl.DateTimeFormat('en-GB',{...options,timeZone}).format(dateValue);
  const sameDay=!end||format({year:'numeric',month:'numeric',day:'numeric'})===format({year:'numeric',month:'numeric',day:'numeric'},end);
  return {month:format({month:'short'}),day:format({day:'2-digit'}),weekday:format({weekday:'long'}),time:format({hour:'numeric',minute:'2-digit',hour12:true}),range:end&&!sameDay?format({day:'numeric',month:'short'})+' – '+format({day:'numeric',month:'short'},end):''};
}
