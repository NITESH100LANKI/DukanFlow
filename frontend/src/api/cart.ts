import apiClient from './client';

export interface CartLineSchemeInfo {
  scheme_type: string;
  free_qty: number;
  discount_amount: number | string;
  benefit_value: number | string;
  description: string;
}

export interface CartLine {
  id: string;
  product_id: string;
  sku: string;
  name: string;
  pack_size?: string | null;
  case_qty: number;
  price_per_pack: number | string;
  price_per_case: number | string;
  qty_cases: number; // paid cases
  qty_free: number; // free cases
  qty_fulfilment: number; // total cases = paid + free
  gross_line_total: number | string;
  discount_amount: number | string;
  benefit_value: number | string;
  net_line_total: number | string;
  scheme_applied?: CartLineSchemeInfo | null;
  created_at: string;
  updated_at: string;
}

export interface CartSummary {
  total_cases_paid: number;
  total_cases_free: number;
  total_cases_fulfilment: number;
  gross_total: number | string;
  total_discount: number | string;
  total_benefit_value: number | string;
  net_total: number | string;
  item_count: number;
}

export interface Cart {
  id: string;
  retailer_id: string;
  lines: CartLine[];
  summary: CartSummary;
  created_at: string;
  updated_at: string;
}

export const getCart = async (): Promise<Cart> => {
  const response = await apiClient.get<Cart>('/cart');
  return response.data;
};

export const addCartLine = async (productId: string, qtyCases: number): Promise<Cart> => {
  const response = await apiClient.post<Cart>('/cart/lines', {
    product_id: productId,
    qty_cases: qtyCases,
  });
  return response.data;
};

export const updateCartLineQty = async (lineId: string, qtyCases: number): Promise<Cart> => {
  const response = await apiClient.patch<Cart>(`/cart/lines/${lineId}`, {
    qty_cases: qtyCases,
  });
  return response.data;
};

export const deleteCartLine = async (lineId: string): Promise<Cart> => {
  const response = await apiClient.delete<Cart>(`/cart/lines/${lineId}`);
  return response.data;
};

export const clearCartApi = async (): Promise<Cart> => {
  const response = await apiClient.delete<Cart>('/cart');
  return response.data;
};
