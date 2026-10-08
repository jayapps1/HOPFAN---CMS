import {describe,it,expect} from 'vitest';
import {duration,fileSize} from '@/features/sermons/types';
import {parseSermon,emptyMetadata} from '@/features/sermons/contracts';
describe('sermon presentation and private contract',()=>{
  it('formats duration and visible download sizes',()=>{expect(duration(3671)).toBe('1:01:11');expect(duration(90)).toBe('1:30');expect(fileSize(24*1024**2)).toBe('24.0 MB');});
  it('strips credentials and storage keys from CMS records',()=>{const row=parseSermon({id:'id',title:'Title',slug:'title',status:'DRAFT',metadata:{...emptyMetadata,secret_key:'UNRELATED_SECRET_MARKER'},updated_at:'now',published_at:null,has_unpublished_changes:true,assets:[],metrics:{VIDEO_PLAY:3,secret:44},scheduled_publish_at:null,storage_key:'UNRELATED_SECRET_MARKER'});expect(JSON.stringify(row)).not.toContain('UNRELATED_SECRET_MARKER');expect(row.metrics).toEqual({VIDEO_PLAY:3});});
});
