import { describe, expect, it } from 'vitest';
import { cardStrings, dinnerItems, itemId } from './card-utils.js';

describe('Lovelace card data helpers', () => {
  it('accepts both integration stock and dinner item identifiers', () => {
    expect(itemId({ item_id: 12 })).toBe(12);
    expect(itemId({ id: 8 })).toBe(8);
    expect(itemId(null)).toBeUndefined();
  });

  it('returns an empty list for an absent dinner', () => {
    expect(dinnerItems(undefined)).toEqual([]);
    expect(dinnerItems({ items: [{ id: 1 }] })).toEqual([{ id: 1 }]);
  });

  it('normalizes the supported English and Dutch locales', () => {
    expect(cardStrings('nl-NL')).toBe('nl');
    expect(cardStrings('en-GB')).toBe('en');
    expect(cardStrings('fr')).toBe('en');
  });
});
