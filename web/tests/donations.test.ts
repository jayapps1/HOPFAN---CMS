import {describe,it,expect} from 'vitest';
import {ApiClient} from '../src/lib/api/client';
import {parseInitialized,parseReceipt} from '../src/features/public/donation-contracts';
const reference='HOPFAN-DON-'+'a'.repeat(32);
const token='b'.repeat(64);
describe('public giving contracts',()=>{
  it('strips private provider and donor details from public receipts',()=>{
    const receipt=parseReceipt({reference,amount:'12.50',currency:'GHS',purpose:'Offering',status:'SUCCESS',paid_at:null,email:'private@example.invalid',authorization:{secret:'hidden'}});
    expect(Object.keys(receipt)).toEqual(['reference','amount','currency','purpose','status','paid_at']);
  });
  it('rejects an unsafe checkout host',()=>{
    expect(()=>parseInitialized({reference,receipt_token:token,authorization_url:'https://checkout.paystack.com.evil.invalid/x'})).toThrow();
  });
  it('rejects forged receipt statuses and invalid money',()=>{
    expect(()=>parseReceipt({reference,amount:'NaN',currency:'GHS',purpose:'Offering',status:'SUCCESS',paid_at:null})).toThrow();
    expect(()=>parseReceipt({reference,amount:'12.50',currency:'GHS',purpose:'Offering',status:'FAKE',paid_at:null})).toThrow();
  });
  it('reuses the API client without staff cookies or auth bootstrap',async()=>{
    const calls:{path:string;options:RequestInit}[]=[];
    const client=new ApiClient('http://localhost:8000',async(path,options)=>{calls.push({path:String(path),options:options!});return new Response(JSON.stringify({reference,receipt_token:token,authorization_url:'https://checkout.paystack.com/test'}),{status:201});});
    await client.publicMutation('/api/v1/public/donations',{},parseInitialized);
    expect(calls).toHaveLength(1);expect(calls[0].options.credentials).toBe('omit');expect(calls[0].options.cache).toBe('no-store');expect(calls[0].options.headers).not.toHaveProperty('X-CSRF-Token');
  });
});
