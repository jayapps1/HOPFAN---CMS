"use client";
import {Button,Input} from '@/components/ui/primitives';
import type {ServiceTime} from '@/features/public/server';
const days=['SUNDAY','MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY'];
export function ServiceTimesEditor({value,change}:{value:ServiceTime[];change:(value:ServiceTime[])=>void}){
  function update(index:number,changes:Partial<ServiceTime>){change(value.map((service,i)=>i===index?{...service,...changes}:service));}
  function move(index:number,delta:number){const list=[...value],target=index+delta;if(target<0||target>=list.length)return;[list[index],list[target]]=[list[target],list[index]];change(list.map((service,i)=>({...service,display_order:i})));}
  return<fieldset className='cms-service-times'><legend>Weekly services</legend><p className='muted'>Times are local to the church timezone. Save the draft, then publish settings to update the public website.</p>
    {value.map((service,index)=><fieldset className='cms-service-row' key={service.id||index}><legend>{service.name||'New service'}</legend>
      <div className='form-grid'><label>Service name {index+1}<Input required value={service.name} maxLength={100} onChange={event=>update(index,{name:event.target.value})}/></label><label>Weekday {index+1}<select aria-label={'Weekday '+(index+1)} value={service.day_of_week||''} required={!service.schedule} onChange={event=>update(index,{day_of_week:event.target.value||null})}><option value=''>Legacy schedule</option>{days.map(day=><option key={day} value={day}>{day[0]+day.slice(1).toLowerCase()}</option>)}</select></label>
      <label>Start time {index+1}<Input type='time' value={service.start_time?.slice(0,5)||''} required={!!service.day_of_week} onChange={event=>update(index,{start_time:event.target.value||null})}/></label><label>End time {index+1}<Input type='time' value={service.end_time?.slice(0,5)||''} required={!!service.day_of_week} onChange={event=>update(index,{end_time:event.target.value||null})}/></label>
      <label>Public location {index+1}<Input value={service.location} maxLength={500} onChange={event=>update(index,{location:event.target.value})}/></label><label>Display order {index+1}<Input type='number' min={0} max={100000} value={service.display_order} onChange={event=>update(index,{display_order:Number(event.target.value)})}/></label></div>
      <label>Public description {index+1}<textarea rows={2} maxLength={1000} value={service.description} onChange={event=>update(index,{description:event.target.value})}/></label>
      {!service.day_of_week&&<label>Existing schedule {index+1}<Input required value={service.schedule} onChange={event=>update(index,{schedule:event.target.value})}/></label>}
      <div className='live-actions'><label className='checkbox-label'><input type='checkbox' checked={service.active} onChange={event=>update(index,{active:event.target.checked})}/>Active service {index+1}</label><label className='checkbox-label'><input type='checkbox' checked={service.featured} onChange={event=>update(index,{featured:event.target.checked})}/>Featured on Home {index+1}</label></div>
      <div className='live-actions'><Button type='button' variant='secondary' disabled={index===0} onClick={()=>move(index,-1)} aria-label={'Move service '+(index+1)+' earlier'}>Move earlier</Button><Button type='button' variant='secondary' disabled={index===value.length-1} onClick={()=>move(index,1)} aria-label={'Move service '+(index+1)+' later'}>Move later</Button><Button type='button' variant='ghost' onClick={()=>change(value.filter((_,i)=>i!==index))}>Remove service {index+1}</Button></div>
    </fieldset>)}
    <Button type='button' variant='secondary' disabled={value.length>=20} onClick={()=>change([...value,{id:crypto.randomUUID(),name:'',schedule:'',day_of_week:'SUNDAY',start_time:'09:00',end_time:'10:00',description:'',location:'',display_order:value.length,active:true,featured:true,created_at:null,updated_at:null}])}>Add service</Button>
  </fieldset>;
}
