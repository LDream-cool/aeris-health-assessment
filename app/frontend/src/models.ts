export type OptionDimension = 'colour' | 'size';
export type OptionDimensions = Record<OptionDimension, string[]>;
export type OptionValues = Record<OptionDimension, string>;
export type Selection = Partial<OptionValues>;

export interface SKU {
  sku_id: string;
  price_cents: number;
  stock: number;
  image: string;
  option_values: OptionValues;
}

export interface Product {
  id: string;
  name: string;
  description: string;
  currency: string;
  options: OptionDimensions;
  skus: SKU[];
}

export interface CartItem {
  sku_id: string;
  quantity: number;
  unit_price_cents: number;
  line_total_cents: number;
  stock: number;
  image: string;
  option_values: OptionValues;
}

export interface Cart {
  items: CartItem[];
  total_item_count: number;
  total_price_cents: number;
  currency: string;
}

export interface AddCartItemRequest {
  sku_id: string;
  quantity: number;
}

export type ProductResponse = Product;
export type CartResponse = Cart;
export type AddCartItemResponse = Cart;

export interface APIErrorDetail {
  field: (string | number)[];
  message: string;
}

export interface APIErrorResponse {
  error: {
    code: string;
    message: string;
    details?: APIErrorDetail[];
  };
}
