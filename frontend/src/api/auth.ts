import apiClient from './client';

export interface RetailerInfo {
  id: string;
  name: string;
  mobile: string;
  address?: string;
}

export interface DeskUserInfo {
  id: string;
  full_name: string;
  email: string;
  role: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  retailer?: RetailerInfo;
  user?: DeskUserInfo;
}

export interface CurrentUser {
  id: string;
  role: 'retailer' | 'order_desk';
  name: string;
  identifier: string;
}

export const requestOtp = async (mobile: string): Promise<{ message: string; expires_in_seconds: number }> => {
  const response = await apiClient.post('/auth/retailer/request-otp', { mobile });
  return response.data;
};

export const verifyOtp = async (mobile: string, otp: string): Promise<TokenResponse> => {
  const response = await apiClient.post<TokenResponse>('/auth/retailer/verify-otp', { mobile, otp });
  return response.data;
};

export const deskLogin = async (email: string, password: string): Promise<TokenResponse> => {
  const response = await apiClient.post<TokenResponse>('/auth/desk/login', { email, password });
  return response.data;
};

export const refreshToken = async (): Promise<TokenResponse> => {
  const response = await apiClient.post<TokenResponse>('/auth/refresh');
  return response.data;
};

export const logoutApi = async (): Promise<void> => {
  await apiClient.post('/auth/logout');
};

export const getMe = async (): Promise<CurrentUser> => {
  const response = await apiClient.get<CurrentUser>('/auth/me');
  return response.data;
};

