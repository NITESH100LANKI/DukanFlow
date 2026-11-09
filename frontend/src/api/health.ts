import apiClient from './client';

export interface HealthResponse {
  status: 'ok' | 'degraded';
  db: 'connected' | 'unreachable';
  version: string;
  app: string;
}

export const fetchHealth = async (): Promise<HealthResponse> => {
  const response = await apiClient.get<HealthResponse>('/health');
  return response.data;
};

