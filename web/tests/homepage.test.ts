import {describe,it,expect} from 'vitest';
import {localClock,eventFacts,homeSectionOrder} from '@/features/public/home-format';
import type {PublicEvent} from '@/features/public/server';
describe('public Home times and composition',()=>{
  it('formats local service clock values without a browser timezone',()=>{expect(localClock('07:00:00')).toBe('7:00 AM');expect(localClock('18:30:00')).toBe('6:30 PM');expect(localClock('00:00')).toBe('12:00 AM');});
  it('uses the church timezone for an event date and hour',()=>{const event={start_datetime:'2026-10-08T01:00:00Z',end_datetime:null} as PublicEvent;const facts=eventFacts(event,'America/New_York');expect(facts.day).toBe('07');expect(facts.weekday).toBe('Wednesday');expect(facts.time.toUpperCase()).toContain('9:00');});
  it('shows a useful multi-day date range',()=>{const event={start_datetime:'2026-10-08T09:00:00Z',end_datetime:'2026-10-10T12:00:00Z'} as PublicEvent;expect(eventFacts(event,'UTC').range).toContain('10 Oct');});
  it('leads with service times and upcoming events',()=>{expect(homeSectionOrder.slice(0,4)).toEqual(['services','events','welcome','ministries']);});
});
