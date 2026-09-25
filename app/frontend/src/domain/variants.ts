import type { OptionDimension, Product, Selection, SKU } from '../models';

export const dimensions: OptionDimension[] = ['colour', 'size'];

export type VariantResolution =
  | { kind: 'incomplete' }
  | { kind: 'unavailable' }
  | { kind: 'in-stock'; sku: SKU }
  | { kind: 'out-of-stock'; sku: SKU };

export function resolveVariant(product: Product, selection: Selection): VariantResolution {
  if (dimensions.some((dimension) => !selection[dimension])) return { kind: 'incomplete' };
  const sku = product.skus.find((candidate) => dimensions.every(
    (dimension) => candidate.option_values[dimension] === selection[dimension],
  ));
  if (!sku) return { kind: 'unavailable' };
  return { kind: sku.stock > 0 ? 'in-stock' : 'out-of-stock', sku };
}

export function isOptionAvailable(
  product: Product, selection: Selection, dimension: OptionDimension, value: string,
): boolean {
  // Availability means existence, not stock. Sold-out variants stay selectable.
  return product.skus.some((sku) => sku.option_values[dimension] === value
    && dimensions.every((other) => other === dimension || !selection[other]
      || sku.option_values[other] === selection[other]));
}

export function validQuantity(quantity: number, stock: number): boolean {
  return Number.isSafeInteger(quantity) && quantity >= 1 && quantity <= stock;
}

export function clampQuantity(quantity: number, stock: number): number {
  if (!Number.isSafeInteger(quantity) || quantity < 1) return 1;
  return Math.max(1, Math.min(quantity, stock));
}

export function formatPrice(cents: number, currency: string): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(cents / 100);
}
