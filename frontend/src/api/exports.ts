import apiClient from './client';

export interface ExportProfile {
  key: string;
  display_name: string;
  description: string;
  is_preliminary: boolean;
}

export interface ExportableOrderItem {
  id: string;
  order_number: string;
  created_at: string;
  status: string;
  retailer_id: string;
  retailer_name: string;
  retailer_mobile: string;
  tally_ledger_name?: string | null;
  total_cases: number;
  total_free_cases: number;
  total_fulfilment_cases: number;
  gross_total: number | string;
  discount_total: number | string;
  benefit_total: number | string;
  net_total: number | string;
  export_count: number;
  last_exported_at?: string | null;
  lines_count: number;
}

export interface ExportableOrderListResponse {
  items: ExportableOrderItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ExportBatchListItem {
  id: string;
  batch_number: string;
  export_profile: string;
  generated_by: string;
  generator_name?: string;
  generated_at: string;
  order_count: number;
  record_count: number;
  total_gross: number | string;
  total_discount: number | string;
  total_benefit: number | string;
  total_net: number | string;
  total_fulfilment_cases: number;
  csv_filename: string;
  file_checksum: string;
}

export interface ExportBatchListResponse {
  items: ExportBatchListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface CreateExportBatchRequest {
  order_ids: string[];
  profile?: string;
}

export interface ExportBatchRead extends ExportBatchListItem {
  batch_lines?: Array<{
    id: string;
    order_id: string;
    order_number_snapshot: string;
    order_net_total: number | string;
    created_at: string;
  }>;
}

export const getExportProfiles = async (token?: string): Promise<ExportProfile[]> => {
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await apiClient.get<ExportProfile[]>('/desk/exports/profiles', { headers });
  return res.data;
};

export const getExportableOrders = async (
  params?: {
    page?: number;
    page_size?: number;
    search?: string;
    date_from?: string;
    date_to?: string;
  },
  token?: string
): Promise<ExportableOrderListResponse> => {
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await apiClient.get<ExportableOrderListResponse>('/desk/exports/orders', {
    params,
    headers,
  });
  return res.data;
};

export const createExportBatch = async (
  data: CreateExportBatchRequest,
  token?: string
): Promise<ExportBatchRead> => {
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await apiClient.post<ExportBatchRead>('/desk/exports', data, { headers });
  return res.data;
};

export const getExportBatches = async (
  params?: { page?: number; page_size?: number },
  token?: string
): Promise<ExportBatchListResponse> => {
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await apiClient.get<ExportBatchListResponse>('/desk/exports', {
    params,
    headers,
  });
  return res.data;
};

export const downloadExportBatch = async (
  batchId: string,
  filename: string,
  token?: string
): Promise<void> => {
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const res = await apiClient.get(`/desk/exports/${batchId}/download`, {
    headers,
    responseType: 'blob',
  });

  // Trigger browser download
  const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8;' });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

