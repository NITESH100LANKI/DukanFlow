import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import ProductCataloguePage from '../pages/ProductCataloguePage';
import StockStatusBadge from '../components/catalogue/StockStatusBadge';
import SchemeBadge from '../components/catalogue/SchemeBadge';
import * as catalogueApi from '../api/catalogue';
import { Product } from '../api/catalogue';

const mockProducts: Product[] = [
  {
    id: 'prod-1',
    sku: 'SKU-BS-075',
    name: 'Glucose biscuit 75 g',
    description: 'Everyday energy glucose biscuit',
    pack_size: '75g',
    case_qty: 96,
    dealer_price_per_pack: 8.1,
    price_unit: 'per_pack',
    dealer_price_per_case: 777.6,
    stock_cases: 340,
    stock_status: 'in_stock',
    category: 'Biscuits',
    is_active: true,
    active_scheme: {
      id: 'scheme-1',
      scheme_type: 'BUY_N_GET_M_FREE',
      min_qty: 10,
      free_qty: 1,
      discount_pct: null,
      valid_from: '2026-01-01',
      valid_to: '2026-12-31',
      is_active: true,
      description: 'Buy 10 cases Get 1 Free',
    },
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'prod-2',
    sku: 'SKU-DT-1KG',
    name: 'Detergent powder 1 kg',
    description: 'High-foaming active stain-removal detergent',
    pack_size: '1kg',
    case_qty: 20,
    dealer_price_per_pack: 101.5,
    price_unit: 'per_pack',
    dealer_price_per_case: 2030.0,
    stock_cases: 85,
    stock_status: 'in_stock',
    category: 'Detergents',
    is_active: true,
    active_scheme: {
      id: 'scheme-2',
      scheme_type: 'DISCOUNT_ON_MIN_QTY',
      min_qty: 5,
      free_qty: null,
      discount_pct: 3.0,
      valid_from: '2026-01-01',
      valid_to: '2026-12-31',
      is_active: true,
      description: '3% discount on 5 or more cases',
    },
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'prod-3',
    sku: 'SKU-TE-250',
    name: 'Tea leaf 250 g',
    description: 'Premium CTC black tea',
    pack_size: '250g',
    case_qty: 40,
    dealer_price_per_pack: 118.0,
    price_unit: 'per_pack',
    dealer_price_per_case: 4720.0,
    stock_cases: 0,
    stock_status: 'out_of_stock',
    category: 'Beverages',
    is_active: true,
    active_scheme: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

vi.mock('../api/catalogue', () => ({
  getProducts: vi.fn(),
  getProductBySku: vi.fn(),
  getCategories: vi.fn(),
}));

describe('Product Catalogue Frontend Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(catalogueApi.getCategories).mockResolvedValue(['Biscuits', 'Detergents', 'Beverages']);
    vi.mocked(catalogueApi.getProducts).mockResolvedValue({
      items: mockProducts,
      total: 3,
      page: 1,
      page_size: 12,
      total_pages: 1,
    });
  });

  it('renders all three seeded products with correct SKU, name, and pricing', async () => {
    render(
      <MemoryRouter>
        <ProductCataloguePage />
      </MemoryRouter>
    );

    // Should fetch products
    await waitFor(() => {
      expect(screen.getByText('Glucose biscuit 75 g')).toBeInTheDocument();
    });

    expect(screen.getByText('SKU-BS-075')).toBeInTheDocument();
    expect(screen.getByText('₹777.60')).toBeInTheDocument(); // Case rate
    expect(screen.getByText('₹8.10 / pack')).toBeInTheDocument();

    expect(screen.getByText('Detergent powder 1 kg')).toBeInTheDocument();
    expect(screen.getByText('SKU-DT-1KG')).toBeInTheDocument();
    expect(screen.getByText('₹2030.00')).toBeInTheDocument();

    expect(screen.getByText('Tea leaf 250 g')).toBeInTheDocument();
    expect(screen.getByText('SKU-TE-250')).toBeInTheDocument();
    expect(screen.getByText('₹4720.00')).toBeInTheDocument();
  });

  it('renders stock status badges accurately for in-stock and out-of-stock items', () => {
    const { rerender } = render(
      <StockStatusBadge status="in_stock" stockCases={340} />
    );
    expect(screen.getByText(/In Stock \(340 cases\)/i)).toBeInTheDocument();

    rerender(<StockStatusBadge status="out_of_stock" stockCases={0} />);
    expect(screen.getByText(/Out of Stock \(0 cases\)/i)).toBeInTheDocument();

    rerender(<StockStatusBadge status="low_stock" stockCases={5} />);
    expect(screen.getByText(/Low Stock \(5 cases left\)/i)).toBeInTheDocument();
  });

  it('renders promotional scheme badges accurately', () => {
    const buyNGetMScheme = mockProducts[0].active_scheme!;
    const discountScheme = mockProducts[1].active_scheme!;

    const { rerender } = render(<SchemeBadge scheme={buyNGetMScheme} />);
    expect(screen.getByText(/Scheme: Buy 10 Cases Get 1 Free/i)).toBeInTheDocument();

    rerender(<SchemeBadge scheme={discountScheme} />);
    expect(screen.getByText(/Scheme: 3% discount on 5\+ cases/i)).toBeInTheDocument();
  });

  it('disables order button for out-of-stock tea leaf', async () => {
    render(
      <MemoryRouter>
        <ProductCataloguePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Tea leaf 250 g')).toBeInTheDocument();
    });

    // The tea card should have a disabled Out of Stock button
    const teaCard = screen.getByTestId('product-card-SKU-TE-250');
    const orderBtn = teaCard.querySelector('button[disabled]');
    expect(orderBtn).not.toBeNull();
    expect(orderBtn).toHaveTextContent('Out of Stock');
  });

  it('renders order soon state for in-stock products until cart phase', async () => {
    render(
      <MemoryRouter>
        <ProductCataloguePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Glucose biscuit 75 g')).toBeInTheDocument();
    });

    const biscuitCard = screen.getByTestId('product-card-SKU-BS-075');
    const orderBtn = biscuitCard.querySelector('button[disabled]');
    expect(orderBtn).not.toBeNull();
    expect(orderBtn).toHaveTextContent(/Order Soon \(Phase 5\)/i);
  });

  it('opens product detail modal when clicking View Details', async () => {
    render(
      <MemoryRouter>
        <ProductCataloguePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Glucose biscuit 75 g')).toBeInTheDocument();
    });

    const biscuitCard = screen.getByTestId('product-card-SKU-BS-075');
    const viewDetailsBtn = biscuitCard.querySelectorAll('button')[0];
    fireEvent.click(viewDetailsBtn);

    // Modal should appear
    expect(screen.getByTestId('product-detail-modal')).toBeInTheDocument();
    expect(screen.getByText('Pricing & Packaging Specifications')).toBeInTheDocument();
    expect(screen.getByText('96 packs')).toBeInTheDocument();
    expect(screen.getByText(/Active Promotional Scheme/i)).toBeInTheDocument();

    // Close modal
    fireEvent.click(screen.getByTestId('modal-close-btn'));
    await waitFor(() => {
      expect(screen.queryByTestId('product-detail-modal')).not.toBeInTheDocument();
    });
  });

  it('triggers search filter when typing into SearchBar', async () => {
    render(
      <MemoryRouter>
        <ProductCataloguePage />
      </MemoryRouter>
    );

    const searchInput = screen.getByPlaceholderText(/Search products or SKU/i);
    fireEvent.change(searchInput, { target: { value: 'biscuit' } });

    await waitFor(() => {
      expect(catalogueApi.getProducts).toHaveBeenCalledWith(
        expect.objectContaining({ q: 'biscuit' })
      );
    });
  });

  it('renders empty state when search returns zero products', async () => {
    vi.mocked(catalogueApi.getProducts).mockResolvedValueOnce({
      items: [],
      total: 0,
      page: 1,
      page_size: 12,
      total_pages: 1,
    });

    render(
      <MemoryRouter>
        <ProductCataloguePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('catalogue-empty')).toBeInTheDocument();
      expect(screen.getByText('No Products Found')).toBeInTheDocument();
    });
  });

  it('renders error state and retries on failure', async () => {
    vi.mocked(catalogueApi.getProducts).mockRejectedValueOnce(
      new Error('Network error')
    );

    render(
      <MemoryRouter>
        <ProductCataloguePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Failed to load product catalogue/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
    });
  });
});
