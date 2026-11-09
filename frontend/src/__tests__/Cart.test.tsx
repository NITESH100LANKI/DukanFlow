import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import CartPage from '../pages/CartPage';
import { CartProvider } from '../context/CartContext';
import { AuthContext } from '../context/AuthContext';
import ProductCard from '../components/catalogue/ProductCard';
import ProductDetailModal from '../components/catalogue/ProductDetailModal';
import * as cartApi from '../api/cart';
import { Cart, CartLine } from '../api/cart';
import { Product } from '../api/catalogue';

const mockRetailerUser = {
  id: 'retailer-uuid-1',
  role: 'retailer',
  name: 'Gupta Kirana Store',
  identifier: '9876543210',
};

const mockCartLines: CartLine[] = [
  {
    id: 'line-1',
    product_id: 'prod-biscuit',
    sku: 'SKU-BS-075',
    name: 'Glucose biscuit 75 g',
    pack_size: '75g',
    case_qty: 96,
    price_per_pack: 8.1,
    price_per_case: 777.6,
    qty_cases: 10,
    qty_free: 1,
    qty_fulfilment: 11,
    gross_line_total: 7776.0,
    discount_amount: 0.0,
    benefit_value: 777.6,
    net_line_total: 7776.0,
    scheme_applied: {
      scheme_type: 'BUY_N_GET_M_FREE',
      free_qty: 1,
      discount_amount: 0.0,
      benefit_value: 777.6,
      description: 'Buy 10 Get 1 Free',
    },
    created_at: '2026-11-09T00:00:00Z',
    updated_at: '2026-11-09T00:00:00Z',
  },
  {
    id: 'line-2',
    product_id: 'prod-detergent',
    sku: 'SKU-DT-1KG',
    name: 'Detergent powder 1 kg',
    pack_size: '1kg',
    case_qty: 20,
    price_per_pack: 101.5,
    price_per_case: 2030.0,
    qty_cases: 5,
    qty_free: 0,
    qty_fulfilment: 5,
    gross_line_total: 10150.0,
    discount_amount: 304.5,
    benefit_value: 304.5,
    net_line_total: 9845.5,
    scheme_applied: {
      scheme_type: 'DISCOUNT_ON_MIN_QTY',
      free_qty: 0,
      discount_amount: 304.5,
      benefit_value: 304.5,
      description: '3% discount on 5+ cases',
    },
    created_at: '2026-11-09T00:00:00Z',
    updated_at: '2026-11-09T00:00:00Z',
  },
];

const mockCart: Cart = {
  id: 'cart-uuid-1',
  retailer_id: 'retailer-uuid-1',
  lines: mockCartLines,
  summary: {
    total_cases_paid: 15,
    total_cases_free: 1,
    total_cases_fulfilment: 16,
    gross_total: 17926.0,
    total_discount: 304.5,
    total_benefit_value: 1082.1,
    net_total: 17621.5,
    item_count: 2,
  },
  created_at: '2026-11-09T00:00:00Z',
  updated_at: '2026-11-09T00:00:00Z',
};

const mockTeaProduct: Product = {
  id: 'prod-tea',
  sku: 'SKU-TE-250',
  name: 'Tea leaf 250 g',
  case_qty: 40,
  dealer_price_per_pack: 118.0,
  price_unit: 'per_pack',
  dealer_price_per_case: 4720.0,
  stock_cases: 0,
  stock_status: 'out_of_stock',
  is_active: true,
  created_at: '2026-11-09T00:00:00Z',
  updated_at: '2026-11-09T00:00:00Z',
};

const mockBiscuitProduct: Product = {
  id: 'prod-biscuit',
  sku: 'SKU-BS-075',
  name: 'Glucose biscuit 75 g',
  case_qty: 96,
  dealer_price_per_pack: 8.1,
  price_unit: 'per_pack',
  dealer_price_per_case: 777.6,
  stock_cases: 340,
  stock_status: 'in_stock',
  is_active: true,
  created_at: '2026-11-09T00:00:00Z',
  updated_at: '2026-11-09T00:00:00Z',
};

vi.mock('../api/cart', () => ({
  getCart: vi.fn(),
  addCartLine: vi.fn(),
  updateCartLineQty: vi.fn(),
  deleteCartLine: vi.fn(),
  clearCartApi: vi.fn(),
}));

const renderWithProviders = (ui: React.ReactNode) => {
  return render(
    <MemoryRouter>
      <AuthContext.Provider
        value={{
          user: mockRetailerUser as any,
          isAuthenticated: true,
          isLoading: false,
          loginWithOtp: vi.fn(),
          loginWithPassword: vi.fn(),
          logout: vi.fn(),
        }}
      >
        <CartProvider>{ui}</CartProvider>
      </AuthContext.Provider>
    </MemoryRouter>
  );
};

describe('Shopping Cart & Scheme Engine Frontend Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(cartApi.getCart).mockResolvedValue(mockCart);
  });

  // 1. Add to Cart works
  it('triggers addToCart API when clicking Add to Cart on in-stock ProductCard', async () => {
    vi.mocked(cartApi.addCartLine).mockResolvedValue(mockCart);

    renderWithProviders(<ProductCard product={mockBiscuitProduct} onSelect={vi.fn()} />);

    const addBtn = screen.getByRole('button', { name: /Add to Cart \+/i });
    expect(addBtn).toBeEnabled();
    fireEvent.click(addBtn);

    await waitFor(() => {
      expect(cartApi.addCartLine).toHaveBeenCalledWith('prod-biscuit', 1);
    });
  });

  // 2. Cart item count and line renders
  it('renders cart line items and correct case quantities', async () => {
    renderWithProviders(<CartPage />);

    await waitFor(() => {
      expect(screen.getByText('Glucose biscuit 75 g')).toBeInTheDocument();
      expect(screen.getByText('Detergent powder 1 kg')).toBeInTheDocument();
    });

    expect(screen.getByText('SKU-BS-075')).toBeInTheDocument();
    expect(screen.getByText('SKU-DT-1KG')).toBeInTheDocument();
  });

  // 3. Quantity controls work
  it('calls updateQty when clicking + or - in CartPage', async () => {
    vi.mocked(cartApi.updateCartLineQty).mockResolvedValue(mockCart);

    renderWithProviders(<CartPage />);

    await waitFor(() => {
      expect(screen.getByText('Glucose biscuit 75 g')).toBeInTheDocument();
    });

    const biscuitLine = screen.getByTestId('cart-line-SKU-BS-075');
    const plusBtn = biscuitLine.querySelector('button[title="Increase quantity"]')!;
    fireEvent.click(plusBtn);

    await waitFor(() => {
      expect(cartApi.updateCartLineQty).toHaveBeenCalledWith('line-1', 11);
    });
  });

  // 4. Remove item works
  it('calls deleteCartLine when clicking remove button', async () => {
    vi.mocked(cartApi.deleteCartLine).mockResolvedValue({
      ...mockCart,
      lines: [mockCart.lines[1]],
    });

    renderWithProviders(<CartPage />);

    await waitFor(() => {
      expect(screen.getByText('Glucose biscuit 75 g')).toBeInTheDocument();
    });

    const biscuitLine = screen.getByTestId('cart-line-SKU-BS-075');
    const removeBtn = biscuitLine.querySelector('button[title="Remove item"]')!;
    fireEvent.click(removeBtn);

    await waitFor(() => {
      expect(cartApi.deleteCartLine).toHaveBeenCalledWith('line-1');
    });
  });

  // 5. Scheme benefits display correctly
  it('displays free goods badges and discount savings on line items', async () => {
    renderWithProviders(<CartPage />);

    await waitFor(() => {
      expect(screen.getByText(/\+1 Free Case \(Fulfilment: 11 cases\)/i)).toBeInTheDocument();
      expect(screen.getByText(/Discount: -₹304.50/i)).toBeInTheDocument();
    });
  });

  // 6. Gross and payable totals match backend response
  it('displays accurate gross total, scheme savings, and net payable in summary', async () => {
    renderWithProviders(<CartPage />);

    await waitFor(() => {
      expect(screen.getByTestId('cart-summary')).toBeInTheDocument();
    });

    const summary = screen.getByTestId('cart-summary');
    expect(summary).toHaveTextContent('₹17926.00'); // Gross
    expect(summary).toHaveTextContent('-₹304.50'); // Discount
    expect(summary).toHaveTextContent('₹17621.50'); // Net payable
    expect(summary).toHaveTextContent('15'); // Paid cases
    expect(summary).toHaveTextContent('+1'); // Free cases
    expect(summary).toHaveTextContent('16'); // Fulfilment cases
  });

  // 7. Empty cart state
  it('renders empty cart state and browse catalogue link when cart has 0 items', async () => {
    vi.mocked(cartApi.getCart).mockResolvedValueOnce({
      ...mockCart,
      lines: [],
      summary: {
        total_cases_paid: 0,
        total_cases_free: 0,
        total_cases_fulfilment: 0,
        gross_total: '0.00',
        total_discount: '0.00',
        total_benefit_value: '0.00',
        net_total: '0.00',
        item_count: 0,
      },
    });

    renderWithProviders(<CartPage />);

    await waitFor(() => {
      expect(screen.getByTestId('cart-empty')).toBeInTheDocument();
      expect(screen.getByText(/Your Cart is Empty/i)).toBeInTheDocument();
    });
  });

  // 8. Loading state
  it('renders skeleton loader while fetching cart', () => {
    vi.mocked(cartApi.getCart).mockReturnValue(new Promise(() => {})); // Never resolves

    renderWithProviders(<CartPage />);

    expect(screen.getByTestId('cart-skeleton')).toBeInTheDocument();
  });

  // 9. API error state
  it('renders error banner with retry option on API failure', async () => {
    vi.mocked(cartApi.getCart).mockRejectedValueOnce({
      response: { data: { detail: 'Database connection failed' } },
    });

    renderWithProviders(<CartPage />);

    await waitFor(() => {
      expect(screen.getByText('Database connection failed')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
    });
  });

  // 10. Out-of-stock products cannot be added
  it('keeps Add to Cart disabled for out-of-stock tea product', () => {
    renderWithProviders(<ProductCard product={mockTeaProduct} onSelect={vi.fn()} />);

    const teaBtn = screen.getByRole('button', { name: /Out of Stock/i });
    expect(teaBtn).toBeDisabled();
  });

  // Bonus: ProductDetailModal quantity selector adds specified cases
  it('adds custom quantity from ProductDetailModal', async () => {
    vi.mocked(cartApi.addCartLine).mockResolvedValue(mockCart);
    const onClose = vi.fn();

    renderWithProviders(<ProductDetailModal product={mockBiscuitProduct} onClose={onClose} />);

    // Increment quantity to 3
    const plusBtn = screen.getByTitle('Increase quantity');
    fireEvent.click(plusBtn);
    fireEvent.click(plusBtn);

    const addBtn = screen.getByRole('button', { name: /Add to Cart \(3 Cases\)/i });
    fireEvent.click(addBtn);

    await waitFor(() => {
      expect(cartApi.addCartLine).toHaveBeenCalledWith('prod-biscuit', 3);
    });
  });
});
