import { describe, expect, it } from 'vitest';
import { product } from '../test/fixtures';
import { clampQuantity, isOptionAvailable, resolveVariant, validQuantity } from './variants';

describe('variant resolution', () => {
  it('distinguishes all four states', () => {
    expect(resolveVariant(product, {})).toEqual({ kind: 'incomplete' });
    expect(resolveVariant(product, { colour: 'blue' })).toEqual({ kind: 'incomplete' });
    expect(resolveVariant(product, { colour: 'sand', size: 'L' })).toEqual({ kind: 'unavailable' });
    expect(resolveVariant(product, { colour: 'blue', size: 'M' })).toMatchObject({ kind: 'out-of-stock', sku: { stock: 0 } });
    expect(resolveVariant(product, { colour: 'blue', size: 'S' })).toMatchObject({ kind: 'in-stock', sku: { sku_id: 'tee-blue-s' } });
  });

  it('matches other selected dimensions but does not exclude sold-out SKUs', () => {
    expect(isOptionAvailable(product, {}, 'size', 'L')).toBe(true);
    expect(isOptionAvailable(product, { colour: 'sand' }, 'size', 'L')).toBe(false);
    expect(isOptionAvailable(product, { size: 'L' }, 'colour', 'sand')).toBe(false);
    expect(isOptionAvailable(product, { colour: 'blue' }, 'size', 'M')).toBe(true);
    expect(isOptionAvailable(product, { colour: 'sand', size: 'M' }, 'colour', 'blue')).toBe(true);
  });
});

describe('quantities', () => {
  it.each([0, -1, 1.5, NaN, Infinity, 6])('rejects invalid quantity %s', (quantity) => {
    expect(validQuantity(quantity, 5)).toBe(false);
  });
  it('accepts exact stock and clamps when switching to lower stock', () => {
    expect(validQuantity(5, 5)).toBe(true);
    expect(validQuantity(1, 0)).toBe(false);
    expect(clampQuantity(5, 2)).toBe(2);
    expect(clampQuantity(NaN, 2)).toBe(1);
  });
});
