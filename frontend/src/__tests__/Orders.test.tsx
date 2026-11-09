import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import CartPage from '../pages/CartPage';
import OrdersPage from '../pages/retailer/OrdersPage';
import OrderDetailPage from '../pages/retailer/OrderDetailPage';
import DeskOrderQueuePage from '../pages/desk/DeskOrderQueuePage';
import DeskOrderDetailPage from '../pages/desk/DeskOrderDetailPage';
import CartContext from '../context/CartContext';
import * as orderApi from '../api/orders';
import { Order, OrderListResponse } from '../api/orders';

const mockOrder: Order = {
  id: 'order-uuid-1',
  order_number: 'ORD-20261109-0001',
  retailer_id: 'retailer-uuid-1',
  reviewed_by: null,
  order_source: 'manual',
  status: 'SUBMITTED',
  gross_total: 7776.0,
  scheme_total: 777.6,
  net_total: 7776.0,
  total_cases: 10,
  total_free_cases: 1,
  total_fulfilment_cases: 11,
  remarks: 'Deliver before 10 AM',
  rejection_reason: null,
  idempotency_key: 'idem-1',
  created_at: '2026-11-09T10:00:00Z',
  updated_at: '2026-11-09T10:00:00Z',
  retailer: {
    id: 'retailer-uuid-1',
    name: 'Gupta Kirana Store',
    mobile: '9876543210',
    address: 'Lordganj, Jabalpur',
  },
  lines: [
    {
      id: 'line-1',
      product_id: 'prod-biscuit',
      sku_snapshot: 'SKU-BS-075',
      name_snapshot: 'Glucose biscuit 75 g',
      pack_size_snapshot: '75g',
      case_qty_snapshot: 96,
      price_per_pack_snapshot: 8.1,
      price_per_case_snapshot: 777.6,
      scheme_type_snapshot: 'BUY_N_GET_M_FREE',
      min_qty_snapshot: 10,
      free_qty_snapshot: 1,
      discount_pct_snapshot: null,
      description_snapshot: 'Buy 10 Get 1 Free',
      qty_cases: 10,
      free_cases: 1,
      fulfilment_qty_cases: 11,
      unit_price: 777.6,
      gross_amount: 7776.0,
      discount_amount: 0.0,
      net_amount: 7776.0,
    },
  ],
  audit_logs: [
    {
      id: 'log-1',
      order_id: 'order-uuid-1',
      actor_type: 'retailer',
      actor_id: 'retailer-uuid-1',
      action: 'SUBMITTED',
      from_status: null,
      to_status: 'SUBMITTED',
      note: 'Order submitted with 1 line item(s)',
      created_at: '2026-11-09T10:00:00Z',
    },
  ],
};

const mockOrderQueue: OrderListResponse = {
  items: [
    {
      id: 'order-uuid-1',
      order_number: 'ORD-20261109-0001',
      retailer_id: 'retailer-uuid-1',
      retailer_name: 'Gupta Kirana Store',
      order_source: 'manual',
      status: 'SUBMITTED',
      gross_total: 7776.0,
      scheme_total: 777.6,
      net_total: 7776.0,
      total_cases: 10,
      total_free_cases: 1,
      total_fulfilment_cases: 11,
      line_count: 1,
      created_at: '2026-11-09T10:00:00Z',
    },
  ],
  total: 1,
  page: 1,
  page_size: 15,
  total_pages: 1,
};

describe('Phase 6: Order Placement & Management Frontend Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders active Place Order button on CartPage and triggers order placement', async () => {
    const mockCart = {
      id: 'cart-1',
      retailer_id: 'retailer-1',
      lines: [
        {
          id: 'line-1',
          product_id: 'prod-1',
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
          created_at: '2026-11-09T00:00:00Z',
          updated_at: '2026-11-09T00:00:00Z',
        },
      ],
      summary: {
        total_cases_paid: 10,
        total_cases_free: 1,
        total_cases_fulfilment: 11,
        gross_total: 7776.0,
        total_discount: 0.0,
        total_benefit_value: 777.6,
        net_total: 7776.0,
        item_count: 1,
      },
      created_at: '2026-11-09T00:00:00Z',
      updated_at: '2026-11-09T00:00:00Z',
    };

    const placeOrderSpy = vi.spyOn(orderApi, 'placeOrderApi').mockResolvedValueOnce(mockOrder);
    const refreshCartMock = vi.fn().mockResolvedValue(undefined);

    render(
      <MemoryRouter initialEntries={['/cart']}>
        <CartContext.Provider
          value={{
            cart: mockCart,
            loading: false,
            error: null,
            totalCasesCount: 10,
            itemCount: 1,
            addToCart: vi.fn(),
            updateQty: vi.fn(),
            removeLine: vi.fn(),
            clearCart: vi.fn(),
            refreshCart: refreshCartMock,
          }}
        >
          <Routes>
            <Route path="/cart" element={<CartPage />} />
            <Route path="/orders/:id" element={<div>Order Confirmation Page</div>} />
          </Routes>
        </CartContext.Provider>
      </MemoryRouter>
    );

    const placeOrderBtn = screen.getByRole('button', { name: /Place Order Now/i });
    expect(placeOrderBtn).toBeInTheDocument();
    expect(placeOrderBtn).not.toBeDisabled();

    // Type optional remarks
    const remarksInput = screen.getByPlaceholderText(/e\.g\. Deliver before 10 AM/i);
    fireEvent.change(remarksInput, { target: { value: 'Call before delivery' } });

    fireEvent.click(placeOrderBtn);

    await waitFor(() => {
      expect(placeOrderSpy).toHaveBeenCalledWith('Call before delivery', expect.any(String));
      expect(refreshCartMock).toHaveBeenCalled();
      expect(screen.getByText('Order Confirmation Page')).toBeInTheDocument();
    });
  });

  it('renders retailer order history list with status badge and view details link', async () => {
    vi.spyOn(orderApi, 'getOrdersApi').mockResolvedValueOnce(mockOrderQueue);

    render(
      <MemoryRouter>
        <OrdersPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('ORD-20261109-0001')).toBeInTheDocument();
      expect(screen.getByText(/10 cases/i)).toBeInTheDocument();
      expect(screen.getByText('₹7776.00')).toBeInTheDocument();
      expect(screen.getByText(/View Details/i)).toBeInTheDocument();
    });
  });

  it('renders retailer order details with frozen snapshots and financial summary', async () => {
    vi.spyOn(orderApi, 'getOrderDetailApi').mockResolvedValueOnce(mockOrder);

    render(
      <MemoryRouter initialEntries={['/orders/order-uuid-1']}>
        <Routes>
          <Route path="/orders/:id" element={<OrderDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('ORD-20261109-0001')).toBeInTheDocument();
      expect(screen.getByText('SKU-BS-075')).toBeInTheDocument();
      expect(screen.getByText('Glucose biscuit 75 g')).toBeInTheDocument();
      expect(screen.getByText(/Deliver before 10 AM/i)).toBeInTheDocument();
      expect(screen.getByText(/Buy 10 Get 1 Free/i)).toBeInTheDocument();
      expect(screen.getByText('+1 free bonus')).toBeInTheDocument();
    });
  });

  it('renders Order Desk queue with status filters and review action', async () => {
    vi.spyOn(orderApi, 'getDeskOrderQueueApi').mockResolvedValueOnce(mockOrderQueue);

    render(
      <MemoryRouter>
        <DeskOrderQueuePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Order Desk Review Queue')).toBeInTheDocument();
      expect(screen.getByText('Gupta Kirana Store')).toBeInTheDocument();
      expect(screen.getByText('ORD-20261109-0001')).toBeInTheDocument();
      expect(screen.getByText(/Review & Approve/i)).toBeInTheDocument();
    });
  });

  it('allows Order Desk operator to approve order and triggers inventory deduction', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    vi.spyOn(orderApi, 'getDeskOrderDetailApi').mockResolvedValueOnce(mockOrder);
    const approveSpy = vi.spyOn(orderApi, 'approveDeskOrderApi').mockResolvedValueOnce({
      ...mockOrder,
      status: 'APPROVED',
    });

    render(
      <MemoryRouter initialEntries={['/desk/orders/order-uuid-1']}>
        <Routes>
          <Route path="/desk/orders/:id" element={<DeskOrderDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('ORD-20261109-0001')).toBeInTheDocument();
    });

    const approveBtn = screen.getByRole('button', { name: /Approve & Deduct Inventory/i });
    expect(approveBtn).toBeInTheDocument();

    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(approveSpy).toHaveBeenCalledWith('order-uuid-1', undefined);
      expect(screen.getByText(/Approved \(Dispatched\)/i)).toBeInTheDocument();
    });
  });

  it('opens quantity correction modal and submits correction with reason', async () => {
    vi.spyOn(orderApi, 'getDeskOrderDetailApi').mockResolvedValueOnce(mockOrder);
    const correctSpy = vi.spyOn(orderApi, 'correctDeskLineApi').mockResolvedValueOnce({
      ...mockOrder,
      total_cases: 20,
      total_free_cases: 2,
      total_fulfilment_cases: 22,
      lines: [
        {
          ...mockOrder.lines[0],
          qty_cases: 20,
          free_cases: 2,
          fulfilment_qty_cases: 22,
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/desk/orders/order-uuid-1']}>
        <Routes>
          <Route path="/desk/orders/:id" element={<DeskOrderDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Correct Cases/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Correct Cases/i }));

    // Modal opens
    expect(screen.getByText(/Correct Quantity: SKU-BS-075/i)).toBeInTheDocument();

    const qtyInput = screen.getByRole('spinbutton');
    fireEvent.change(qtyInput, { target: { value: '20' } });

    const reasonInput = screen.getByPlaceholderText(/Retailer called to increase order/i);
    fireEvent.change(reasonInput, { target: { value: 'Customer requested 20 cases over phone' } });

    fireEvent.click(screen.getByRole('button', { name: /Save & Recalculate/i }));

    await waitFor(() => {
      expect(correctSpy).toHaveBeenCalledWith(
        'order-uuid-1',
        'line-1',
        20,
        'Customer requested 20 cases over phone'
      );
      expect(screen.getByText(/20 cases paid/i)).toBeInTheDocument();
      expect(screen.getByText(/\+2 free bonus/i)).toBeInTheDocument();
    });
  });

  it('opens rejection modal and submits rejection with mandatory reason', async () => {
    vi.spyOn(orderApi, 'getDeskOrderDetailApi').mockResolvedValueOnce(mockOrder);
    const rejectSpy = vi.spyOn(orderApi, 'rejectDeskOrderApi').mockResolvedValueOnce({
      ...mockOrder,
      status: 'REJECTED',
      rejection_reason: 'Credit limit exceeded for this retailer',
    });

    render(
      <MemoryRouter initialEntries={['/desk/orders/order-uuid-1']}>
        <Routes>
          <Route path="/desk/orders/:id" element={<DeskOrderDetailPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Reject Order/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/Reject Order/i));

    expect(screen.getByText(/Reject Order: ORD-20261109-0001/i)).toBeInTheDocument();

    const reasonInput = screen.getByPlaceholderText(/Retailer credit limit exceeded/i);
    fireEvent.change(reasonInput, { target: { value: 'Credit limit exceeded for this retailer' } });

    fireEvent.click(screen.getByRole('button', { name: /Confirm Rejection/i }));

    await waitFor(() => {
      expect(rejectSpy).toHaveBeenCalledWith(
        'order-uuid-1',
        'Credit limit exceeded for this retailer'
      );
      expect(screen.getByText(/Credit limit exceeded for this retailer/i)).toBeInTheDocument();
    });
  });
});
