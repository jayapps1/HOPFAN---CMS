export interface DonationOptions {enabled:boolean;mode:"test";currency:string;categories:{id:string;name:string}[]}
export interface DonationReceipt {reference:string;amount:string;currency:string;purpose:string;status:string;paid_at:string|null}
export interface DonationRecord extends DonationReceipt {id:string;donor_name:string;email:string;phone:string;note:string;provider:string;provider_reference:string;created_at:string}
export const referencePattern=/^HOPFAN-DON-[a-f0-9]{32}$/;
function record(value:unknown):Record<string,unknown>{if(!value||typeof value!=="object"||Array.isArray(value))throw new Error("Invalid response");return value as Record<string,unknown>;}
function text(value:unknown){if(typeof value!=="string")throw new Error("Invalid response");return value;}
export function parseInitialized(value:unknown){const row=record(value);const reference=text(row.reference),receipt_token=text(row.receipt_token),authorization_url=text(row.authorization_url);
  if(!referencePattern.test(reference)||!/^[0-9a-f]{64}$/.test(receipt_token)||!/^https:\/\/checkout\.paystack\.com\/[A-Za-z0-9_-]+$/.test(authorization_url))throw new Error("Invalid checkout response");
  return {reference,receipt_token,authorization_url};
}
export function parseReceipt(value:unknown):DonationReceipt{const row=record(value);const reference=text(row.reference),amount=text(row.amount),currency=text(row.currency),status=text(row.status);
  if(!referencePattern.test(reference)||!/^\d+(?:\.\d{1,2})?$/.test(amount)||!['GHS','NGN','KES','ZAR','USD'].includes(currency)||!['INITIALIZING','PENDING','SUCCESS','FAILED','CANCELLED','INITIALIZATION_FAILED'].includes(status))throw new Error('Invalid receipt');
  return {reference,amount,currency,purpose:text(row.purpose),status,paid_at:row.paid_at===null?null:text(row.paid_at)};
}
export function parseDonationPage(value:unknown){const row=record(value);if(!Array.isArray(row.items)||!Number.isInteger(row.page)||!Number.isInteger(row.pages))throw new Error('Invalid response');
  return {page:row.page as number,pages:row.pages as number,items:row.items.map(value=>{const item=record(value);return {...parseReceipt(item),id:text(item.id),donor_name:text(item.donor_name),email:text(item.email),phone:text(item.phone),note:text(item.note),provider:text(item.provider),provider_reference:text(item.provider_reference),created_at:text(item.created_at)} satisfies DonationRecord;})};
}
export function donationMoney(amount:string,currency:string){return new Intl.NumberFormat('en-GH',{style:'currency',currency}).format(Number(amount));}
