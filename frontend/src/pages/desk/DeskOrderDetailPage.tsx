import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  getDeskOrderDetailApi,
  correctDeskLineApi,
  approveDeskOrderApi,
  rejectDeskOrderApi,
  Order,
  OrderLine,
} from '../../api/orders';

export const DeskOrderDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Line correction modal state
  const [editingLine, setEditingLine] = useState<OrderLine | null>(null);
  const [newQty, setNewQty] = useState<number>(1);
  const [correctionReason, setCorrectionReason] = useState<string>('');
  const [correctionLoading, setCorrectionLoading] = useState(false);
  const [correctionError, setCorrectionError] = useState<string | null>(null);

  // Approval state
  const [approving, setApproving] = useState(false);
  const [approvalNote, setApprovalNote] = useState('');
  const [approvalError, setApprovalError] = useState<string | null>(null);

  // Rejection modal state
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [rejecting, setRejecting] = useState(false);
  const [rejectionError, setRejectionError] = useState<string | null>(null);

  const fetchOrder = async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getDeskOrderDetailApi(id);
      setOrder(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load order');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrder();
  }, [id]);

  const handleOpenCorrection = (line: OrderLine) => {
    setEditingLine(line);
    setNewQty(line.qty_cases);
    setCorrectionReason('');
    setCorrectionError(null);
  };

  const handleSubmitCorrection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!order || !editingLine) return;
    if (newQty < 1) {
      setCorrectionError('Quantity must be at least 1 case');
      return;
    }
    if (!correctionReason.trim()) {
      setCorrectionError('Mandatory reason required for quantity correction');
      return;
    }

    setCorrectionLoading(true);
    setCorrectionError(null);
    try {
      const updated = await correctDeskLineApi(
        order.id,
        editingLine.id,
        newQty,
        correctionReason.trim()
      );
      setOrder(updated);
      setEditingLine(null);
    } catch (err: any) {
      setCorrectionError(err.response?.data?.detail || err.message || 'Failed to correct quantity');
    } finally {
      setCorrectionLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!order) return;
    if (!window.confirm(`Approve order ${order.order_number} and atomically deduct stock?`)) {
      return;
    }

    setApproving(true);
    setApprovalError(null);
    try {
      const updated = await approveDeskOrderApi(order.id, approvalNote.trim() || undefined);
      setOrder(updated);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (detail && typeof detail === 'object' && detail.insufficient_items) {
        const items = detail.insufficient_items
          .map((i: any) => `${i.sku} (${i.name}): required ${i.required_cases} cases, available ${i.available_cases}`)
          .join('\n');
        setApprovalError(`Insufficient Inventory:\n${items}`);
      } else {
        setApprovalError(typeof detail === 'string' ? detail : err.message || 'Approval failed');
      }
    } finally {
      setApproving(false);
    }
  };

  const handleReject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!order) return;
    if (!rejectionReason.trim()) {
      setRejectionError('Mandatory rejection reason required');
      return;
    }

    setRejecting(true);
    setRejectionError(null);
    try {
      const updated = await rejectDeskOrderApi(order.id, rejectionReason.trim());
      setOrder(updated);
      setRejectModalOpen(false);
    } catch (err: any) {
      setRejectionError(err.response?.data?.detail || err.message || 'Rejection failed');
    } finally {
      setRejecting(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'APPROVED':
        return (
          <span className="px-3 py-1 text-xs font-bold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
            ✓ Approved (Dispatched)
          </span>
        );
      case 'REJECTED':
        return (
          <span className="px-3 py-1 text-xs font-bold rounded-full bg-rose-100 text-rose-800 border border-rose-300">
            ✕ Rejected
          </span>
        );
      default:
        return (
          <span className="px-3 py-1 text-xs font-bold rounded-full bg-amber-100 text-amber-800 border border-amber-300 animate-pulse">
            ⏳ Pending Desk Approval
          </span>
        );
    }
  };

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
        <p className="text-xs text-gray-500 mt-3">Loading order details...</p>
      </div>
    );
  }

  if (error || !order) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-12 space-y-4">
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-2xl text-xs">
          {error || 'Order not found'}
        </div>
        <Link
          to="/desk/orders"
          className="inline-block text-xs font-bold text-primary-600 hover:text-primary-700"
        >
          ← Back to Order Queue
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      {/* Top Bar */}
      <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4">
        <Link
          to="/desk/orders"
          className="text-xs font-bold text-gray-500 hover:text-gray-800 transition-colors flex items-center gap-1"
        >
          ← Back to Queue
        </Link>
        <div className="flex items-center gap-3">
          {getStatusBadge(order.status)}
        </div>
      </div>

      {/* Main Order Card */}
      <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row justify-between sm:items-baseline gap-2 pb-3 border-b border-gray-100">
          <div>
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
              Order Desk Review
            </span>
            <h1 className="text-2xl font-black font-mono text-gray-900">
              {order.order_number}
            </h1>
          </div>
          <div className="text-xs text-gray-500">
            Placed:{' '}
            <span className="font-semibold text-gray-800">
              {new Date(order.created_at).toLocaleString()}
            </span>
          </div>
        </div>

        {/* Retailer Info */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-gray-50 rounded-xl text-xs">
          <div>
            <span className="text-[10px] font-bold text-gray-400 uppercase block">Retailer Name</span>
            <span className="font-bold text-gray-800 text-sm">
              {order.retailer?.name || 'Retailer Account'}
            </span>
          </div>
          <div>
            <span className="text-[10px] font-bold text-gray-400 uppercase block">Mobile Number</span>
            <span className="font-mono text-gray-700">{order.retailer?.mobile || 'N/A'}</span>
          </div>
          <div>
            <span className="text-[10px] font-bold text-gray-400 uppercase block">Delivery Address</span>
            <span className="text-gray-700">{order.retailer?.address || 'No address on file'}</span>
          </div>
        </div>

        {/* Remarks if present */}
        {order.remarks && (
          <div className="p-3 bg-blue-50 border border-blue-200 text-blue-900 rounded-xl text-xs">
            <span className="font-bold">Retailer Instructions: </span>
            {order.remarks}
          </div>
        )}

        {/* Rejection Notice if rejected */}
        {order.status === 'REJECTED' && (
          <div className="p-4 bg-rose-50 border border-rose-200 text-rose-900 rounded-xl text-xs space-y-1">
            <span className="font-bold block">Rejection Reason:</span>
            <p>{order.rejection_reason}</p>
          </div>
        )}

        {/* Approval Error Alert */}
        {approvalError && (
          <div className="p-4 bg-red-50 border border-red-200 text-red-700 rounded-xl text-xs whitespace-pre-wrap">
            <span className="font-bold block mb-1">Approval Blocked:</span>
            {approvalError}
          </div>
        )}

        {/* Action Buttons for SUBMITTED orders */}
        {order.status === 'SUBMITTED' && (
          <div className="pt-3 border-t border-gray-100 flex flex-col sm:flex-row justify-end items-center gap-3">
            <input
              type="text"
              value={approvalNote}
              onChange={(e) => setApprovalNote(e.target.value)}
              placeholder="Approval note (optional)"
              className="text-xs px-3 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:outline-none w-full sm:w-60"
            />
            <button
              type="button"
              onClick={() => setRejectModalOpen(true)}
              disabled={approving}
              className="px-4 py-2.5 rounded-xl border border-rose-300 text-rose-700 hover:bg-rose-50 font-bold text-xs transition-colors w-full sm:w-auto"
            >
              ✕ Reject Order
            </button>
            <button
              type="button"
              onClick={handleApprove}
              disabled={approving}
              className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow hover:shadow-md transition-all flex items-center justify-center gap-2 w-full sm:w-auto"
            >
              {approving ? (
                <>
                  <div className="animate-spin rounded-full h-3.5 w-3.5 border-b-2 border-white"></div>
                  Deducting Inventory...
                </>
              ) : (
                '✓ Approve & Deduct Inventory'
              )}
            </button>
          </div>
        )}
      </div>

      {/* Line Items Table */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="p-4 bg-gray-50 border-b border-gray-100 flex justify-between items-center text-xs font-bold text-gray-700 uppercase tracking-wider">
          <span>Order Line Items ({order.lines.length})</span>
          {order.status === 'SUBMITTED' && (
            <span className="text-[11px] font-normal text-gray-500 lowercase">
              (click 'correct cases' to adjust quantities before approval)
            </span>
          )}
        </div>

        <div className="divide-y divide-gray-100">
          {order.lines.map((line) => (
            <div key={line.id} className="p-4 flex flex-col md:flex-row justify-between md:items-center gap-4">
              <div className="space-y-1 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[11px] font-bold text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                    {line.sku_snapshot}
                  </span>
                  <span className="text-xs font-bold text-gray-900">
                    {line.name_snapshot}
                  </span>
                </div>
                <div className="text-[11px] text-gray-500 flex flex-wrap gap-x-3">
                  <span>{line.pack_size_snapshot}</span>
                  <span>•</span>
                  <span>{line.case_qty_snapshot} packs / case</span>
                  <span>•</span>
                  <span>Wholesale: ₹{Number(line.price_per_case_snapshot).toFixed(2)} / case</span>
                </div>

                {line.description_snapshot && (
                  <div className="inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-primary-50 text-primary-700 border border-primary-200">
                    🏷️ Scheme: {line.description_snapshot}
                  </div>
                )}
              </div>

              {/* Quantities & Fulfilment details */}
              <div className="flex items-center justify-between md:justify-end gap-6 text-right">
                <div className="text-left md:text-right">
                  <div className="text-xs font-bold text-gray-900">
                    {line.qty_cases} cases paid
                  </div>
                  {line.free_cases > 0 && (
                    <div className="text-[11px] font-semibold text-emerald-700">
                      +{line.free_cases} free bonus
                    </div>
                  )}
                  <div className="text-[10px] text-gray-400">
                    Fulfilment: {line.fulfilment_qty_cases} total cases
                  </div>
                </div>

                <div className="text-right min-w-[90px]">
                  <div className="text-sm font-black text-gray-900">
                    ₹{Number(line.net_amount).toFixed(2)}
                  </div>
                  {Number(line.discount_amount) > 0 && (
                    <div className="text-[10px] text-emerald-600">
                      -₹{Number(line.discount_amount).toFixed(2)}
                    </div>
                  )}
                </div>

                {/* Correction CTA if order is SUBMITTED */}
                {order.status === 'SUBMITTED' && (
                  <div>
                    <button
                      type="button"
                      onClick={() => handleOpenCorrection(line)}
                      className="px-3 py-1.5 rounded-lg border border-primary-300 text-primary-700 hover:bg-primary-50 text-xs font-bold transition-colors whitespace-nowrap"
                    >
                      ✏️ Correct Cases
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Financials & Volume Summary */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Volume */}
        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm space-y-2">
          <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">
            Fulfilment Volume Summary
          </h3>
          <div className="flex justify-between text-xs text-gray-600">
            <span>Ordered (Paid) Cases:</span>
            <span className="font-bold text-gray-900">{order.total_cases}</span>
          </div>
          <div className="flex justify-between text-xs text-emerald-700">
            <span>Free Scheme Bonus Cases:</span>
            <span className="font-bold">+{order.total_free_cases}</span>
          </div>
          <div className="pt-2 border-t border-gray-100 flex justify-between text-sm font-bold text-gray-900">
            <span>Total Dispatch Cases:</span>
            <span className="text-primary-700">{order.total_fulfilment_cases} cases</span>
          </div>
        </div>

        {/* Financials */}
        <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm space-y-2">
          <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">
            Financial Ledger Summary
          </h3>
          <div className="flex justify-between text-xs text-gray-600">
            <span>Gross Total:</span>
            <span className="font-bold">₹{Number(order.gross_total).toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-xs text-emerald-700">
            <span>Scheme Total Benefit:</span>
            <span className="font-bold">-₹{Number(order.scheme_total).toFixed(2)}</span>
          </div>
          <div className="pt-2 border-t border-gray-100 flex justify-between text-sm font-black text-emerald-800">
            <span>Net Payable:</span>
            <span className="text-xl">₹{Number(order.net_total).toFixed(2)}</span>
          </div>
        </div>
      </div>

      {/* Immutable Audit Trail */}
      <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm space-y-3">
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">
          Immutable Audit Log Timeline ({order.audit_logs.length})
        </h3>
        <div className="space-y-3 divide-y divide-gray-100">
          {order.audit_logs.map((log) => (
            <div key={log.id} className="pt-3 first:pt-0 text-xs flex justify-between items-start">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-gray-900">
                    {log.action}
                  </span>
                  <span className="text-[10px] uppercase font-bold text-gray-400 px-1.5 py-0.5 bg-gray-100 rounded">
                    by {log.actor_type}
                  </span>
                </div>
                {log.note && (
                  <p className="text-gray-600 text-[11px]">{log.note}</p>
                )}
                {log.details && (
                  <p className="text-[10px] font-mono text-gray-400">
                    {JSON.stringify(log.details)}
                  </p>
                )}
              </div>
              <span className="text-[10px] text-gray-400 whitespace-nowrap ml-4">
                {new Date(log.created_at).toLocaleString()}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Correction Modal */}
      {editingLine && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b pb-3">
              <h3 className="text-sm font-bold text-gray-900">
                Correct Quantity: {editingLine.sku_snapshot}
              </h3>
              <button
                type="button"
                onClick={() => setEditingLine(null)}
                className="text-gray-400 hover:text-gray-600 font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSubmitCorrection} className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-gray-700 block mb-1">
                  Product
                </label>
                <div className="text-xs text-gray-500 bg-gray-50 p-2.5 rounded-xl">
                  {editingLine.name_snapshot} ({editingLine.pack_size_snapshot})
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-gray-700 block mb-1">
                  Corrected Cases (must be ≥ 1)
                </label>
                <input
                  type="number"
                  min="1"
                  value={newQty}
                  onChange={(e) => setNewQty(parseInt(e.target.value) || 1)}
                  className="w-full text-xs p-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-gray-700 block mb-1">
                  Mandatory Correction Reason
                </label>
                <textarea
                  value={correctionReason}
                  onChange={(e) => setCorrectionReason(e.target.value)}
                  placeholder="e.g. Retailer called to increase order; partial stock available"
                  className="w-full text-xs p-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:outline-none h-20"
                  required
                />
              </div>

              {correctionError && (
                <div className="text-xs text-red-600 bg-red-50 p-2.5 rounded-xl border border-red-200">
                  {correctionError}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingLine(null)}
                  className="px-4 py-2 border rounded-xl text-xs font-bold text-gray-600 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={correctionLoading}
                  className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-xl text-xs font-bold transition-all shadow"
                >
                  {correctionLoading ? 'Recalculating...' : 'Save & Recalculate'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Rejection Modal */}
      {rejectModalOpen && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b pb-3">
              <h3 className="text-sm font-bold text-rose-700">
                Reject Order: {order.order_number}
              </h3>
              <button
                type="button"
                onClick={() => setRejectModalOpen(false)}
                className="text-gray-400 hover:text-gray-600 font-bold"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleReject} className="space-y-3">
              <p className="text-xs text-gray-600">
                Are you sure you want to reject this order? Inventory will not be deducted. A mandatory reason must be recorded.
              </p>

              <div>
                <label className="text-xs font-semibold text-gray-700 block mb-1">
                  Rejection Reason
                </label>
                <textarea
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  placeholder="e.g. Retailer credit limit exceeded; store temporarily closed"
                  className="w-full text-xs p-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-rose-500 focus:outline-none h-24"
                  required
                />
              </div>

              {rejectionError && (
                <div className="text-xs text-red-600 bg-red-50 p-2.5 rounded-xl border border-red-200">
                  {rejectionError}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setRejectModalOpen(false)}
                  className="px-4 py-2 border rounded-xl text-xs font-bold text-gray-600 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={rejecting}
                  className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold transition-all shadow"
                >
                  {rejecting ? 'Rejecting...' : 'Confirm Rejection'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default DeskOrderDetailPage;
