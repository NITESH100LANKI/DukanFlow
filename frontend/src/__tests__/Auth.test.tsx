import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from '../context/AuthContext';
import LoginPage from '../pages/LoginPage';
import ProtectedRoute from '../components/ProtectedRoute';
import * as authApi from '../api/auth';

vi.mock('../api/auth', () => ({
  requestOtp: vi.fn(),
  verifyOtp: vi.fn(),
  deskLogin: vi.fn(),
  refreshToken: vi.fn().mockRejectedValue(new Error('No refresh token')),
  logoutApi: vi.fn(),
  getMe: vi.fn().mockRejectedValue(new Error('Unauthenticated')),
}));

describe('Authentication Flow Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders login tabs for Retailer and Order Desk', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    );

    expect(screen.getByText('Login to DukaanFlow')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Retailer/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Order Desk/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('9876543210')).toBeInTheDocument();
  });

  it('switches between Retailer and Order Desk login tabs', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    );

    const deskTab = screen.getByRole('button', { name: /Order Desk/i });
    fireEvent.click(deskTab);

    expect(screen.getByPlaceholderText('desk@dukaanflow.in')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('••••••••')).toBeInTheDocument();
  });

  it('handles retailer mobile OTP request and verification flow', async () => {
    vi.mocked(authApi.requestOtp).mockResolvedValueOnce({
      message: 'OTP sent',
      expires_in_seconds: 600,
    });
    vi.mocked(authApi.verifyOtp).mockResolvedValueOnce({
      access_token: 'fake_jwt_token',
      token_type: 'bearer',
      expires_in: 900,
      retailer: {
        id: '123e4567-e89b-12d3-a456-426614174000',
        name: 'Sharma General Store',
        mobile: '9876543210',
      },
    });

    render(
      <MemoryRouter initialEntries={['/login']}>
        <AuthProvider>
          <LoginPage />
        </AuthProvider>
      </MemoryRouter>
    );

    const mobileInput = screen.getByPlaceholderText('9876543210');
    fireEvent.change(mobileInput, { target: { value: '9876543210' } });

    const sendOtpButton = screen.getByRole('button', { name: /Send OTP/i });
    fireEvent.click(sendOtpButton);

    await waitFor(() => {
      expect(authApi.requestOtp).toHaveBeenCalledWith('9876543210');
      expect(screen.getByPlaceholderText('123456')).toBeInTheDocument();
    });

    const otpInput = screen.getByPlaceholderText('123456');
    fireEvent.change(otpInput, { target: { value: '123456' } });

    const verifyButton = screen.getByRole('button', { name: /Verify & Login/i });
    fireEvent.click(verifyButton);

    await waitFor(() => {
      expect(authApi.verifyOtp).toHaveBeenCalledWith('9876543210', '123456');
    });
  });

  it('redirects unauthenticated users from protected routes to login', async () => {
    render(
      <MemoryRouter initialEntries={['/protected']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<div>Login Page Redirected</div>} />
            <Route
              path="/protected"
              element={
                <ProtectedRoute>
                  <div>Secret Protected Content</div>
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Login Page Redirected')).toBeInTheDocument();
    });
    expect(screen.queryByText('Secret Protected Content')).not.toBeInTheDocument();
  });

  it('enforces role restrictions on protected routes', async () => {
    // Mock user authenticated as retailer
    vi.mocked(authApi.refreshToken).mockResolvedValueOnce({
      access_token: 'fake_retailer_jwt',
      token_type: 'bearer',
      expires_in: 900,
    });
    vi.mocked(authApi.getMe).mockResolvedValueOnce({
      id: 'retailer-123',
      role: 'retailer',
      name: 'Sharma General Store',
      identifier: '9876543210',
    });

    render(
      <MemoryRouter initialEntries={['/desk-only']}>
        <AuthProvider>
          <Routes>
            <Route path="/" element={<div>Home Page (Access Denied)</div>} />
            <Route
              path="/desk-only"
              element={
                <ProtectedRoute allowedRoles={['order_desk']}>
                  <div>Order Desk Secret Area</div>
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    );

    // Retailer should be bounced back to /
    await waitFor(() => {
      expect(screen.getByText('Home Page (Access Denied)')).toBeInTheDocument();
    });
    expect(screen.queryByText('Order Desk Secret Area')).not.toBeInTheDocument();
  });
});
