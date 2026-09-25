import type { Cart, Product } from '../models';

export const product: Product = {
  id: 'everyday-tee', name: 'Everyday Cotton Tee', description: 'A soft cotton T-shirt.', currency: 'USD',
  options: { colour: ['blue', 'black', 'sand'], size: ['S', 'M', 'L'] },
  skus: [
    ['blue', 'S', 2500, 5], ['blue', 'M', 2500, 0], ['blue', 'L', 2700, 3],
    ['black', 'S', 2600, 2], ['black', 'M', 2600, 8], ['black', 'L', 2800, 1],
    ['sand', 'S', 2500, 4], ['sand', 'M', 2500, 6],
  ].map(([colour, size, price, stock]) => ({
    sku_id: `tee-${colour}-${String(size).toLowerCase()}`,
    price_cents: Number(price), stock: Number(stock), image: `/static/tee-${colour}.svg`,
    option_values: { colour: String(colour), size: String(size) },
  })),
};

export const emptyCart: Cart = { items: [], total_item_count: 0, total_price_cents: 0, currency: 'USD' };
export const addedCart: Cart = {
  items: [{ sku_id: 'tee-blue-s', quantity: 1, unit_price_cents: 2500, line_total_cents: 2500,
    stock: 4, image: '/static/tee-blue.svg', option_values: { colour: 'blue', size: 'S' } }],
  total_item_count: 1, total_price_cents: 2500, currency: 'USD',
};
