import apiClient from './client';

export interface DraftProduct {
  id: string;
  sku: string;
  name: string;
  pack_size: string;
  case_qty: number;
  dealer_price_per_pack: number | string;
  dealer_price_per_case: number | string;
  stock_cases: number;
  stock_status: 'in_stock' | 'out_of_stock';
  category?: string;
}

export interface DraftLine {
  id: string;
  draft_id: string;
  raw_fragment: string;
  product_mention: string;
  quantity_value: number | null;
  unit_text: string | null;
  normalized_unit: 'case' | 'piece' | 'unknown';
  matched_product_id: string | null;
  matched_product: DraftProduct | null;
  match_status: 'confirmed' | 'ambiguous' | 'unmatched';
  confidence: 'high' | 'medium' | 'low' | null;
  clarification_reason: string | null;
  alternatives: DraftProduct[];
  warning: string | null;
  resolved_product_id: string | null;
  resolved_product: DraftProduct | null;
  resolved_qty_cases: number | null;
  is_confirmed: boolean;
  created_at: string;
}

export interface OrderDraft {
  id: string;
  retailer_id: string;
  original_message: string;
  status: 'DRAFT' | 'CONFIRMED' | 'DISCARDED';
  parser_used: 'gemini' | 'fallback';
  confirmed_at: string | null;
  lines: DraftLine[];
  metadata_json: Record<string, any> | null;
  all_resolved: boolean;
  ready_to_confirm: boolean;
  created_at: string;
  updated_at: string;
}

export interface DraftConfirmResponse {
  draft_id: string;
  status: string;
  confirmed_items_count: number;
  cart_total_cases: number;
  cart_net_total: number | string;
  message: string;
}

export interface DraftListResponse {
  items: OrderDraft[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export const createOrderDraftApi = async (raw_text: string): Promise<OrderDraft> => {
  const response = await apiClient.post<OrderDraft>('/ai/order-drafts', { raw_text });
  return response.data;
};

export const listOrderDraftsApi = async (page = 1, pageSize = 20): Promise<DraftListResponse> => {
  const response = await apiClient.get<DraftListResponse>('/ai/order-drafts', {
    params: { page, page_size: pageSize },
  });
  return response.data;
};

export const getOrderDraftApi = async (draftId: string): Promise<OrderDraft> => {
  const response = await apiClient.get<OrderDraft>(`/ai/order-drafts/${draftId}`);
  return response.data;
};

export const updateDraftLineApi = async (
  draftId: string,
  lineId: string,
  data: {
    resolved_product_id?: string;
    resolved_qty_cases?: number;
    normalized_unit?: 'case' | 'piece' | 'unknown';
  }
): Promise<OrderDraft> => {
  const response = await apiClient.patch<OrderDraft>(
    `/ai/order-drafts/${draftId}/lines/${lineId}`,
    data
  );
  return response.data;
};

export const deleteDraftLineApi = async (
  draftId: string,
  lineId: string
): Promise<OrderDraft> => {
  const response = await apiClient.delete<OrderDraft>(
    `/ai/order-drafts/${draftId}/lines/${lineId}`
  );
  return response.data;
};

export const confirmDraftToCartApi = async (
  draftId: string
): Promise<DraftConfirmResponse> => {
  const response = await apiClient.post<DraftConfirmResponse>(
    `/ai/order-drafts/${draftId}/confirm`
  );
  return response.data;
};

