import apiClient from './client';

export interface OrderAuditLog {
  id: string;
  order_id: string;
  actor_type: 'retailer' | 'order_desk';
  actor_id: string;
  action: 'SUBMITTED' | 'LINE_CORRECTED' | 'APPROVED' | 'REJECTED';
  from_status?: string | null;
  to_status?: string | null;
  note?: string | null;
  details?: Record<string, any> | null;
  created_at: string;
}

export interface OrderLine {
  id: string;
  product_id: string;
  sku_snapshot: string;
  name_snapshot: string;
  pack_size_snapshot: string;
  case_qty_snapshot: number;
  price_per_pack_snapshot: number | string;
  price_per_case_snapshot: number | string;

  scheme_type_snapshot?: string | null;
  min_qty_snapshot?: number | null;
  free_qty_snapshot?: number | null;
  discount_pct_snapshot?: number | string | null;
  description_snapshot?: string | null;

  qty_cases: number;
  free_cases: number;
  fulfilment_qty_cases: number;

  unit_price: number | string;
  gross_amount: number | string;
  discount_amount: number | string;
  net_amount: number | string;
  raw_fragment?: string | null;
}

export interface OrderRetailerInfo {
  id: string;
  name: string;
  mobile: string;
  address?: string | null;
}

export interface Order {
  id: string;
  order_number: string;
  retailer_id: string;
  reviewed_by?: string | null;
  order_source: string;
  status: 'SUBMITTED' | 'APPROVED' | 'REJECTED';

  gross_total: number | string;
  scheme_total: number | string;
  net_total: number | string;

  total_cases: number;
  total_free_cases: number;
  total_fulfilment_cases: number;

  remarks?: string | null;
  rejection_reason?: string | null;
  idempotency_key?: string | null;

  created_at: string;
  updated_at: string;

  lines: OrderLine[];
  audit_logs: OrderAuditLog[];
  retailer?: OrderRetailerInfo | null;
}

export interface OrderListItem {
  id: string;
  order_number: string;
  retailer_id: string;
  retailer_name?: string | null;
  order_source: string;
  status: 'SUBMITTED' | 'APPROVED' | 'REJECTED';
  gross_total: number | string;
  scheme_total: number | string;
  net_total: number | string;
  total_cases: number;
  total_free_cases: number;
  total_fulfilment_cases: number;
  line_count: number;
  created_at: string;
}

export interface OrderListResponse {
  items: OrderListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ----------------------------------------------------------------------
// Retailer Endpoints
// ----------------------------------------------------------------------

export const placeOrderApi = async (
  remarks?: string,
  idempotencyKey?: string
): Promise<Order> => {
  const headers: Record<string, string> = {};
  if (idempotencyKey) {
    headers['Idempotency-Key'] = idempotencyKey;
  }
  const response = await apiClient.post<Order>(
    '/orders',
    { remarks },
    { headers }
  );
  return response.data;
};

export const getOrdersApi = async (
  page = 1,
  pageSize = 20
): Promise<OrderListResponse> => {
  const response = await apiClient.get<OrderListResponse>('/orders', {
    params: { page, page_size: pageSize },
  });
  return response.data;
};

export const getOrderDetailApi = async (orderId: string): Promise<Order> => {
  const response = await apiClient.get<Order>(`/orders/${orderId}`);
  return response.data;
};

// ----------------------------------------------------------------------
// Order Desk Endpoints
// ----------------------------------------------------------------------

export const getDeskOrderQueueApi = async (
  status?: string,
  page = 1,
  pageSize = 20
): Promise<OrderListResponse> => {
  const params: Record<string, any> = { page, page_size: pageSize };
  if (status && status !== 'ALL') {
    params.status = status;
  }
  const response = await apiClient.get<OrderListResponse>('/desk/orders', {
    params,
  });
  return response.data;
};

export const getDeskOrderDetailApi = async (orderId: string): Promise<Order> => {
  const response = await apiClient.get<Order>(`/desk/orders/${orderId}`);
  return response.data;
};

export const correctDeskLineApi = async (
  orderId: string,
  lineId: string,
  qtyCases: number,
  reason: string
): Promise<Order> => {
  const response = await apiClient.patch<Order>(
    `/desk/orders/${orderId}/lines/${lineId}`,
    { qty_cases: qtyCases, reason }
  );
  return response.data;
};

export const approveDeskOrderApi = async (
  orderId: string,
  note?: string
): Promise<Order> => {
  const response = await apiClient.post<Order>(
    `/desk/orders/${orderId}/approve`,
    { note }
  );
  return response.data;
};

export const rejectDeskOrderApi = async (
  orderId: string,
  reason: string
): Promise<Order> => {
  const response = await apiClient.post<Order>(
    `/desk/orders/${orderId}/reject`,
    { reason }
  );
  return response.data;
};
