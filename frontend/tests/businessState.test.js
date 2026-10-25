import { describe, it, expect } from 'vitest';
import { migrateBusinessId } from '../src/utils/businessState';

const makeState = () => ({
  businesses: [
    { id: 'biz-1', name: 'Old', hasData: true, synced: false },
    { id: 'u2', name: 'Other', synced: true },
  ],
  selected: 'biz-1',
  profiles: { 'biz-1': { description: 'd' }, u2: { description: 'x' } },
  uploads: { 'biz-1': { file: 'a.csv' } },
  recs: { 'biz-1': [0, 2], u2: ['r1'] },
  user: { name: 'A' },
});
const newBusiness = { id: 'uuid-9', name: 'Old', hasData: true, synced: true };

describe('migrateBusinessId', () => {
  it('replaces the business in place and keeps the order', () => {
    const result = migrateBusinessId(makeState(), 'biz-1', newBusiness);
    expect(result.businesses.map((b) => b.id)).toEqual(['uuid-9', 'u2']);
  });

  it('moves the selection, profile and upload to the new id', () => {
    const result = migrateBusinessId(makeState(), 'biz-1', newBusiness);
    expect(result.selected).toBe('uuid-9');
    expect(result.profiles).toEqual({ u2: { description: 'x' }, 'uuid-9': { description: 'd' } });
    expect(result.uploads).toEqual({ 'uuid-9': { file: 'a.csv' } });
  });

  it('drops the old demo recommendation ticks but keeps other businesses', () => {
    const result = migrateBusinessId(makeState(), 'biz-1', newBusiness);
    expect(result.recs).toEqual({ u2: ['r1'] });
  });

  it('leaves unrelated state alone and does not change its input', () => {
    const state = makeState();
    const result = migrateBusinessId(state, 'biz-1', newBusiness);
    expect(result.user).toEqual({ name: 'A' });
    expect(state.businesses[0].id).toBe('biz-1');
    expect(state.profiles['biz-1']).toEqual({ description: 'd' });
  });

  it('copes with missing maps', () => {
    const result = migrateBusinessId({ businesses: [{ id: 'b' }], selected: 'zzz' }, 'b', { id: 'n' });
    expect(result.selected).toBe('zzz');
    expect(result.profiles).toBe(undefined);
    expect(result.uploads).toBe(undefined);
    expect(result.recs).toEqual({});
  });
});
