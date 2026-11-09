import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { AICapturePage } from '../pages/retailer/AICapturePage';
import { CartProvider } from '../context/CartContext';
import { AuthContext } from '../context/AuthContext';
import * as aiApi from '../api/ai';
import * as cartApi from '../api/cart';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const mockRetailerUser = {
  id: 'retailer-uuid-1',
  role: 'retailer' as const,
  name: 'Gupta Kirana Store',
  identifier: '9876543210',
};

const mockAuthValue: any = {
  user: mockRetailerUser,
  token: 'mock-token',
  isAuthenticated: true,
  isLoading: false,
  login: vi.fn(),
  logout: vi.fn(),
};

const mockCart: cartApi.Cart = {
  id: 'cart-1',
  retailer_id: 'retailer-uuid-1',
  lines: [],
  summary: {
    total_cases_paid: 0,
    total_cases_free: 0,
    total_cases_fulfilment: 0,
    gross_total: 0,
    total_discount: 0,
    total_benefit_value: 0,
    net_total: 0,
    item_count: 0,
  },
  created_at: '2026-11-09T00:00:00Z',
  updated_at: '2026-11-09T00:00:00Z',
};

const mockDraftConfirmed: any = {
  id: 'draft-uuid-1',
  retailer_id: 'retailer-uuid-1',
  original_message: '5 peti biscuit, 2 case detergent',
  status: 'DRAFT',
  parser_used: 'gemini',
  lines: [
    {
      id: 'line-1',
      raw_fragment: '5 peti biscuit',
      product_mention: 'biscuit',
      quantity_value: 5,
      unit_text: 'peti',
      normalized_unit: 'case',
      unit_unclear: false,
      resolved_qty_cases: 5,
      matched_product_id: 'prod-biscuit',
      matched_product: {
        id: 'prod-biscuit',
        sku: 'SKU-BS-075',
        name: 'Glucose biscuit 75 g',
        pack_size: '75g',
        case_qty: 96,
        dealer_price_per_pack: 8.1,
        dealer_price_per_case: 777.6,
        stock_cases: 50,
        is_active: true,
      },
      match_status: 'confirmed',
      confidence: 'high',
      alternatives: [],
      warning: null,
      is_confirmed: true,
    },
    {
      id: 'line-2',
      raw_fragment: '2 case detergent',
      product_mention: 'detergent',
      quantity_value: 2,
      unit_text: 'case',
      normalized_unit: 'case',
      unit_unclear: false,
      resolved_qty_cases: 2,
      matched_product_id: 'prod-detergent',
      matched_product: {
        id: 'prod-detergent',
        sku: 'SKU-DT-1KG',
        name: 'Detergent powder 1 kg',
        pack_size: '1kg',
        case_qty: 20,
        dealer_price_per_pack: 101.5,
        dealer_price_per_case: 2030.0,
        stock_cases: 30,
        is_active: true,
      },
      match_status: 'confirmed',
      confidence: 'high',
      alternatives: [],
      warning: null,
      is_confirmed: true,
    },
  ],
  created_at: '2026-11-09T00:00:00Z',
  updated_at: '2026-11-09T00:00:00Z',
};

const mockDraftAmbiguous: any = {
  id: 'draft-uuid-2',
  retailer_id: 'retailer-uuid-1',
  original_message: '50 packet biscuit',
  status: 'DRAFT',
  parser_used: 'fallback',
  lines: [
    {
      id: 'line-ambiguous-1',
      raw_fragment: '50 packet biscuit',
      product_mention: 'biscuit',
      quantity_value: 50,
      unit_text: 'packet',
      normalized_unit: 'piece',
      unit_unclear: true,
      resolved_qty_cases: null,
      matched_product_id: null,
      matched_product: null,
      match_status: 'ambiguous',
      confidence: 'low',
      clarification_reason: 'Multiple products matched',
      alternatives: [
        {
          id: 'prod-biscuit-1',
          sku: 'SKU-BS-075',
          name: 'Glucose biscuit 75 g',
          pack_size: '75g',
          case_qty: 96,
          dealer_price_per_pack: 8.1,
          dealer_price_per_case: 777.6,
          stock_cases: 50,
          is_active: true,
        },
        {
          id: 'prod-biscuit-2',
          sku: 'SKU-BS-150',
          name: 'Marie biscuit 150 g',
          pack_size: '150g',
          case_qty: 48,
          dealer_price_per_pack: 15.0,
          dealer_price_per_case: 720.0,
          stock_cases: 25,
          is_active: true,
        },
      ],
      warning: 'UNIT_UNCLEAR',
      is_confirmed: false,
    },
  ],
  created_at: '2026-11-09T00:00:00Z',
  updated_at: '2026-11-09T00:00:00Z',
};

describe('AICapturePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(cartApi, 'getCart').mockResolvedValue(mockCart);
  });

  const renderComponent = () =>
    render(
      <MemoryRouter>
        <AuthContext.Provider value={mockAuthValue}>
          <CartProvider>
            <AICapturePage />
          </CartProvider>
        </AuthContext.Provider>
      </MemoryRouter>
    );

  it('renders input area, header, sample prompt chips, and disabled extract button initially', () => {
    renderComponent();

    expect(screen.getByText(/AI Order Capture/i)).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/उदाहरण: 5 peti Parle-G/i)
    ).toBeInTheDocument();

    const extractBtn = screen.getByRole('button', { name: /Generate Draft/i });
    expect(extractBtn).toBeDisabled();

    expect(screen.getByText('5 peti biscuit, 2 case detergent')).toBeInTheDocument();
  });

  it('clicking a sample prompt populates the textarea and triggers extraction', async () => {
    vi.spyOn(aiApi, 'createOrderDraftApi').mockResolvedValue(mockDraftConfirmed);

    renderComponent();

    const sampleBtn = screen.getByText('5 peti biscuit, 2 case detergent');
    fireEvent.click(sampleBtn);

    await waitFor(() => {
      expect(aiApi.createOrderDraftApi).toHaveBeenCalledWith('5 peti biscuit, 2 case detergent');
      expect(screen.getByText('Status: DRAFT')).toBeInTheDocument();
      expect(screen.getByText('Glucose biscuit 75 g')).toBeInTheDocument();
      expect(screen.getByText('Detergent powder 1 kg')).toBeInTheDocument();
    });
  });

  it('shows ambiguous draft with unit clarification prompt and disables confirm button', async () => {
    vi.spyOn(aiApi, 'createOrderDraftApi').mockResolvedValue(mockDraftAmbiguous);

    renderComponent();

    const textarea = screen.getByPlaceholderText(/उदाहरण: 5 peti Parle-G/i);
    fireEvent.change(textarea, { target: { value: '50 packet biscuit' } });

    const extractBtn = screen.getByRole('button', { name: /Generate Draft/i });
    expect(extractBtn).not.toBeDisabled();
    fireEvent.click(extractBtn);

    await waitFor(() => {
      expect(screen.getByText(/Unit was stated as/i)).toBeInTheDocument();
      expect(screen.getByText(/Confirm 50 as Cases/i)).toBeInTheDocument();
      expect(screen.getByText(/Offline Rule-Based Parser Used/i)).toBeInTheDocument();
    });

    const confirmBtn = screen.getByRole('button', { name: /Resolve Issues to Confirm/i });
    expect(confirmBtn).toBeDisabled();
  });

  it('allows resolving unit to case and selecting an alternative product', async () => {
    vi.spyOn(aiApi, 'createOrderDraftApi').mockResolvedValue(mockDraftAmbiguous);
    const mockUpdated = {
      ...mockDraftAmbiguous,
      lines: [
        {
          ...mockDraftAmbiguous.lines[0],
          normalized_unit: 'case',
          unit_unclear: false,
          matched_product_id: 'prod-biscuit-1',
          matched_product: mockDraftAmbiguous.lines[0].alternatives[0],
          is_confirmed: true,
          warning: null,
          resolved_qty_cases: 5,
        },
      ],
    };
    vi.spyOn(aiApi, 'updateDraftLineApi').mockResolvedValue(mockUpdated as any);

    renderComponent();

    const textarea = screen.getByPlaceholderText(/उदाहरण: 5 peti Parle-G/i);
    fireEvent.change(textarea, { target: { value: '50 packet biscuit' } });
    fireEvent.click(screen.getByRole('button', { name: /Generate Draft/i }));

    await waitFor(() => {
      expect(screen.getByText(/Confirm 50 as Cases/i)).toBeInTheDocument();
    });

    // Click Confirm 50 as Cases
    fireEvent.click(screen.getByText(/Confirm 50 as Cases/i));

    await waitFor(() => {
      expect(aiApi.updateDraftLineApi).toHaveBeenCalledWith(
        'draft-uuid-2',
        'line-ambiguous-1',
        { normalized_unit: 'case' }
      );
    });
  });

  it('allows removing a draft line item', async () => {
    vi.spyOn(aiApi, 'createOrderDraftApi').mockResolvedValue(mockDraftConfirmed);
    const mockAfterDelete = {
      ...mockDraftConfirmed,
      lines: [mockDraftConfirmed.lines[1]],
    };
    vi.spyOn(aiApi, 'deleteDraftLineApi').mockResolvedValue(mockAfterDelete);

    renderComponent();

    const sampleBtn = screen.getByText('5 peti biscuit, 2 case detergent');
    fireEvent.click(sampleBtn);

    await waitFor(() => {
      expect(screen.getByText('Glucose biscuit 75 g')).toBeInTheDocument();
    });

    const removeButtons = screen.getAllByTitle('Discard item');
    fireEvent.click(removeButtons[0]);

    await waitFor(() => {
      expect(aiApi.deleteDraftLineApi).toHaveBeenCalledWith('draft-uuid-1', 'line-1');
    });
  });

  it('successfully confirms draft to cart when all items are valid', async () => {
    vi.spyOn(aiApi, 'createOrderDraftApi').mockResolvedValue(mockDraftConfirmed);
    vi.spyOn(aiApi, 'confirmDraftToCartApi').mockResolvedValue({
      draft_id: 'draft-uuid-1',
      status: 'CONFIRMED',
      confirmed_items_count: 2,
      cart_total_cases: 7,
      cart_net_total: 7949.0,
      message: 'Successfully added 2 item(s) to your cart',
    });

    renderComponent();

    const sampleBtn = screen.getByText('5 peti biscuit, 2 case detergent');
    fireEvent.click(sampleBtn);

    await waitFor(() => {
      expect(screen.getByText('Status: DRAFT')).toBeInTheDocument();
    });

    const confirmBtn = screen.getByRole('button', { name: /Send to Cart/i });
    expect(confirmBtn).not.toBeDisabled();
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(aiApi.confirmDraftToCartApi).toHaveBeenCalledWith('draft-uuid-1');
      expect(screen.getByText(/Successfully added 2 item\(s\) to your cart/i)).toBeInTheDocument();
    });
  });
});
