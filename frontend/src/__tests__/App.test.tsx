import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import App from '../App';

// Mock API calls so unit test runs deterministically
vi.mock('../api/health', () => ({
  fetchHealth: vi.fn().mockResolvedValue({
    status: 'ok',
    db: 'connected',
    version: '0.1.0',
    app: 'DukaanFlow',
  }),
}));

vi.mock('../api/auth', () => ({
  refreshToken: vi.fn().mockRejectedValue(new Error('No token')),
  getMe: vi.fn().mockRejectedValue(new Error('No token')),
  requestOtp: vi.fn(),
  verifyOtp: vi.fn(),
  deskLogin: vi.fn(),
  logoutApi: vi.fn(),
}));

vi.mock('../api/cart', () => ({
  getCart: vi.fn().mockRejectedValue(new Error('No cart')),
  addCartLine: vi.fn(),
  updateCartLineQty: vi.fn(),
  deleteCartLine: vi.fn(),
  clearCartApi: vi.fn(),
}));

describe('App Component', () => {
  it('renders the DukaanFlow brand in header', async () => {
    await act(async () => {
      render(<App />);
    });
    expect(screen.getByText('DukaanFlow')).toBeInTheDocument();
  });

  it('renders the language toggle with English and Hindi buttons', async () => {
    await act(async () => {
      render(<App />);
    });
    expect(screen.getByRole('button', { name: 'English' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'हिंदी' })).toBeInTheDocument();
  });

  it('renders Phase 2 status badge and hero content', async () => {
    await act(async () => {
      render(<App />);
    });
    expect(screen.getByText('Phase 2 Initialized')).toBeInTheDocument();
    expect(screen.getByText('Welcome to DukaanFlow')).toBeInTheDocument();
  });
});
