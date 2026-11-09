import apiClient from './client';

export interface Scheme {
  id: string;
  scheme_type: 'BUY_N_GET_M_FREE' | 'DISCOUNT_ON_MIN_QTY' | string;
  min_qty: number;
  free_qty?: number | null;
  discount_pct?: number | string | null;
  valid_from: string;
  valid_to: string;
  is_active: boolean;
  description: string;
}

export interface Product {
  id: string;
  sku: string;
  name: string;
  description?: string | null;
  pack_size?: string | null;
  case_qty: number;
  dealer_price_per_pack: number | string;
  price_unit: string;
  dealer_price_per_case: number | string;
  gst_rate_pct?: number | string | null;
  stock_cases: number;
  stock_status: 'in_stock' | 'low_stock' | 'out_of_stock';
  category?: string | null;
  is_active: boolean;
  active_scheme?: Scheme | null;
  created_at: string;
  updated_at: string;
}

export interface ProductListResponse {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ProductFilterParams {
  q?: string;
  category?: string;
  in_stock?: boolean;
  page?: number;
  page_size?: number;
}

export const getProducts = async (params: ProductFilterParams = {}): Promise<ProductListResponse> => {
  const queryParams: Record<string, any> = {};
  if (params.q?.trim()) queryParams.q = params.q.trim();
  if (params.category && params.category !== 'all') queryParams.category = params.category;
  if (params.in_stock) queryParams.in_stock = true;
  if (params.page) queryParams.page = params.page;
  if (params.page_size) queryParams.page_size = params.page_size;

  const response = await apiClient.get<ProductListResponse>('/catalogue/products', {
    params: queryParams,
  });
  return response.data;
};

export const getProductBySku = async (sku: string): Promise<Product> => {
  const response = await apiClient.get<Product>(`/catalogue/products/${encodeURIComponent(sku)}`);
  return response.data;
};

export const getCategories = async (): Promise<string[]> => {
  const response = await apiClient.get<string[]>('/catalogue/categories');
  return response.data;
};

