import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { DeskExportOrdersPage } from '../pages/desk/DeskExportOrdersPage';
import { AuthContext } from '../context/AuthContext';
import * as exportApi from '../api/exports';
import { ExportableOrderItem, ExportProfile, ExportBatchListItem } from '../api/exports';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useOutletContext: () => ({ language: 'en' }),
  };
});

const mockDeskUser = {
  id: 'desk-uuid-1',
  role: 'order_desk' as const,
  name: 'Rajesh Sharma',
  identifier: 'desk@dukaanflow.in',
};

const mockAuthValue: any = {
  user: mockDeskUser,
  token: 'mock-desk-token',
  isAuthenticated: true,
  isLoading: false,
  login: vi.fn(),
  logout: vi.fn(),
};

const mockProfiles: ExportProfile[] = [
  {
    key: 'generic',
    display_name: 'Generic Accounting CSV (Pre-Tally)',
    description: 'Standard multi-line accounting format. Format is unconfirmed for direct Tally import.',
    is_preliminary: true,
  },
];

const mockOrders: ExportableOrderItem[] = [
  {
    id: 'ord-uuid-1',
    order_number: 'ORD-20261109-0001',
    created_at: '2026-11-09T10:00:00Z',
    status: 'APPROVED',
    retailer_id: 'ret-uuid-1',
    retailer_name: 'Gupta Kirana Store',
    retailer_mobile: '9876543210',
    tally_ledger_name: 'Gupta Kirana Ledger',
    total_cases: 10,
    total_free_cases: 1,
    total_fulfilment_cases: 11,
    gross_total: 7776.0,
    discount_total: 0.0,
    benefit_total: 777.6,
    net_total: 7776.0,
    export_count: 0,
    last_exported_at: null,
    lines_count: 1,
  },
  {
    id: 'ord-uuid-2',
    order_number: 'ORD-20261109-0002',
    created_at: '2026-11-09T11:00:00Z',
    status: 'APPROVED',
    retailer_id: 'ret-uuid-2',
    retailer_name: 'Agrawal Supermarket',
    retailer_mobile: '9826112233',
    tally_ledger_name: null,
    total_cases: 5,
    total_free_cases: 0,
    total_fulfilment_cases: 5,
    gross_total: 5000.0,
    discount_total: 150.0,
    benefit_total: 150.0,
    net_total: 4850.0,
    export_count: 1,
    last_exported_at: '2026-11-09T12:00:00Z',
    lines_count: 1,
  },
];

const mockBatches: ExportBatchListItem[] = [
  {
    id: 'batch-uuid-1',
    batch_number: 'EXP-20261109-ABC123',
    export_profile: 'generic',
    generated_by: 'desk-uuid-1',
    generator_name: 'Rajesh Sharma',
    generated_at: '2026-11-09T12:00:00Z',
    order_count: 1,
    record_count: 1,
    total_gross: 5000.0,
    total_discount: 150.0,
    total_benefit: 150.0,
    total_net: 4850.0,
    total_fulfilment_cases: 5,
    csv_filename: 'dukaanflow_generic_EXP-20261109-ABC123.csv',
    file_checksum: 'abcdef1234567890abcdef1234567890',
  },
];

describe('Phase 8: Order Desk Accounting & Tally Export Frontend Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.spyOn(exportApi, 'getExportProfiles').mockResolvedValue(mockProfiles);
    vi.spyOn(exportApi, 'getExportableOrders').mockResolvedValue({
      items: mockOrders,
      total: 2,
      page: 1,
      page_size: 20,
      total_pages: 1,
    });
    vi.spyOn(exportApi, 'getExportBatches').mockResolvedValue({
      items: mockBatches,
      total: 1,
      page: 1,
      page_size: 50,
      total_pages: 1,
    });
    vi.spyOn(exportApi, 'createExportBatch').mockResolvedValue({
      ...mockBatches[0],
      batch_lines: [],
    });
    vi.spyOn(exportApi, 'downloadExportBatch').mockResolvedValue();
  });

  const renderComponent = () =>
    render(
      <MemoryRouter>
        <AuthContext.Provider value={mockAuthValue}>
          <DeskExportOrdersPage />
        </AuthContext.Provider>
      </MemoryRouter>
    );

  it('renders page header, preliminary Tally disclaimer banner, and profile selector', async () => {
    renderComponent();

    expect(screen.getByText('Accounting Export & Tally Integration')).toBeInTheDocument();
    expect(
      screen.getByText('Notice: Client Tally Import Format Pending Confirmation')
    ).toBeInTheDocument();
    expect(screen.getByText(/zero invented GST/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('ORD-20261109-0001')).toBeInTheDocument();
      expect(screen.getByText('ORD-20261109-0002')).toBeInTheDocument();
    });
  });

  it('renders approved orders with retailer details, fulfilment cases, and export statuses', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Gupta Kirana Store')).toBeInTheDocument();
      expect(screen.getByText('Tally: Gupta Kirana Ledger')).toBeInTheDocument();
      expect(screen.getByText('Agrawal Supermarket')).toBeInTheDocument();
      expect(screen.getByText('Not Exported')).toBeInTheDocument();
      expect(screen.getByText('Exported 1x')).toBeInTheDocument();
    });
  });

  it('selects individual order and updates selection metrics dynamically', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('ORD-20261109-0001')).toBeInTheDocument();
    });

    const checkboxes = screen.getAllByRole('checkbox');
    // First checkbox is select-all, second is ord-1, third is ord-2
    expect(checkboxes.length).toBe(3);

    // Select first order
    fireEvent.click(checkboxes[1]);

    // Summary should show 1 order, 11 cases, and ₹7,776.00
    await waitFor(() => {
      expect(screen.getByTestId('selected-count')).toHaveTextContent('1');
      expect(screen.getByTestId('selected-cases')).toHaveTextContent('11');
      expect(screen.getByTestId('selected-net')).toHaveTextContent('₹7,776.00');
    });
  });

  it('selects all orders on page when clicking Select All checkbox', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('ORD-20261109-0001')).toBeInTheDocument();
    });

    const selectAllCheckbox = screen.getByLabelText('Select All on Page');
    fireEvent.click(selectAllCheckbox);

    // Both orders selected: count = 2, fulfilment cases = 16 (11 + 5), net = ₹12,626.00
    await waitFor(() => {
      expect(screen.getByTestId('selected-count')).toHaveTextContent('2');
      expect(screen.getByTestId('selected-cases')).toHaveTextContent('16');
      expect(screen.getByTestId('selected-net')).toHaveTextContent('₹12,626.00');
    });
  });

  it('disables export CTA when zero orders selected, and enables when orders selected', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('ORD-20261109-0001')).toBeInTheDocument();
    });

    const exportBtn = screen.getByRole('button', { name: /generate & download csv/i });
    expect(exportBtn).toBeDisabled();

    // Select order 1
    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[1]);

    expect(exportBtn).not.toBeDisabled();
  });

  it('triggers createExportBatch API and downloadExportBatch when clicking export CTA', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('ORD-20261109-0001')).toBeInTheDocument();
    });

    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[1]);

    const exportBtn = screen.getByRole('button', { name: /generate & download csv/i });
    fireEvent.click(exportBtn);

    await waitFor(() => {
      expect(exportApi.createExportBatch).toHaveBeenCalledWith({
        order_ids: ['ord-uuid-1'],
        profile: 'generic',
      });
      expect(exportApi.downloadExportBatch).toHaveBeenCalled();
    });
  });

  it('switches to Export History tab and displays previous batches with download button', async () => {
    renderComponent();

    const historyTab = screen.getByRole('button', { name: /export history/i });
    fireEvent.click(historyTab);

    await waitFor(() => {
      expect(screen.getByText('EXP-20261109-ABC123')).toBeInTheDocument();
      expect(screen.getByText('SHA: abcdef1234...')).toBeInTheDocument();
      expect(screen.getByText('₹4850.00')).toBeInTheDocument();
    });

    const downloadBtn = screen.getByRole('button', { name: /download csv/i });
    fireEvent.click(downloadBtn);

    await waitFor(() => {
      expect(exportApi.downloadExportBatch).toHaveBeenCalledWith(
        'batch-uuid-1',
        'dukaanflow_generic_EXP-20261109-ABC123.csv'
      );
    });
  });

  it('renders empty state when no approved orders match filters', async () => {
    vi.spyOn(exportApi, 'getExportableOrders').mockResolvedValueOnce({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
      total_pages: 1,
    });

    renderComponent();

    await waitFor(() => {
      expect(
        screen.getByText('No approved orders found matching your filters.')
      ).toBeInTheDocument();
    });
  });

  it('renders error banner when exportable orders API fails', async () => {
    vi.spyOn(exportApi, 'getExportableOrders').mockRejectedValueOnce({
      response: { data: { detail: 'Database connection failed' } },
    });

    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Database connection failed')).toBeInTheDocument();
    });
  });
});
