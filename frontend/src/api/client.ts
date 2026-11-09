import axios from 'axios';

// API base URL: defaults to /api/v1 (proxied by Vite in dev or rewritten by Vercel)
const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const apiClient = axios.create({
  baseURL,
  withCredentials: true, // Send HttpOnly refresh cookies
  headers: {
    'Content-Type': 'application/json',
  },
});

export default apiClient;

