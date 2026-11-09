import React, { useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { getDeskOrderQueueApi, OrderListItem } from '../../api/orders';
import { Language } from '../../components/LanguageToggle';

export const DeskOrderQueuePage: React.FC = () => {
  const context = useOutletContext<{ language: Language }>();
  const language = context?.language || 'en';

  const [orders, setOrders] = useState<OrderListItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('SUBMITTED');
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchQueue = async (status = statusFilter, pageNum = 1) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDeskOrderQueueApi(status, pageNum, 15);
      setOrders(data.items);
      setTotal(data.total);
      setPage(data.page);
      setTotalPages(data.total_pages);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load order queue');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue(statusFilter, page);
  }, [statusFilter, page]);

  const handleFilterChange = (newStatus: string) => {
    setStatusFilter(newStatus);
    setPage(1);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'APPROVED':
        return (
          <span className="px-2.5 py-1 text-xs font-bold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
            Approved
          </span>
        );
      case 'REJECTED':
        return (
          <span className="px-2.5 py-1 text-xs font-bold rounded-full bg-rose-100 text-rose-800 border border-rose-300">
            Rejected
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-1 text-xs font-bold rounded-full bg-amber-100 text-amber-800 border border-amber-300">
            Pending Review
          </span>
        );
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
      {/* Page Title */}
      <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-black text-gray-900">
            {language === 'hi' ? 'ऑर्डर डेस्क समीक्षा कतार' : 'Order Desk Review Queue'}
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            {language === 'hi'
              ? 'आने वाले थोक ऑर्डर्स की समीक्षा करें, मात्रा सुधारें एवं स्टॉक मंज़ूर करें।'
              : 'Review submitted orders, make case adjustments, and approve inventory dispatch.'}
          </p>
        </div>

        {/* Status Filter Tabs */}
        <div className="flex bg-gray-100 p-1 rounded-xl text-xs font-bold self-start sm:self-auto">
          {[
            { id: 'SUBMITTED', label: language === 'hi' ? 'समीक्षाधीन' : 'Submitted' },
            { id: 'APPROVED', label: language === 'hi' ? 'मंज़ूर' : 'Approved' },
            { id: 'REJECTED', label: language === 'hi' ? 'अस्वीकृत' : 'Rejected' },
            { id: 'ALL', label: language === 'hi' ? 'सभी' : 'All' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => handleFilterChange(tab.id)}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                statusFilter === tab.id
                  ? 'bg-white text-primary-700 shadow-sm'
                  : 'text-gray-500 hover:text-gray-900'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="text-center py-16 bg-white rounded-2xl border border-gray-100 shadow-sm">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
          <p className="text-xs text-gray-500 mt-3">Loading order queue...</p>
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-2xl text-xs flex justify-between items-center">
          <span>{error}</span>
          <button
            onClick={() => fetchQueue()}
            className="text-xs font-bold underline hover:text-red-800"
          >
            Retry
          </button>
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && orders.length === 0 && (
        <div className="text-center py-16 bg-white rounded-2xl border border-gray-100 shadow-sm space-y-2">
          <div className="text-3xl">📋</div>
          <h3 className="text-sm font-bold text-gray-700">No orders in this status</h3>
          <p className="text-xs text-gray-400">
            There are currently no orders matching filter "{statusFilter}".
          </p>
        </div>
      )}

      {/* Orders Table */}
      {!loading && !error && orders.length > 0 && (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50 text-gray-400 font-bold uppercase tracking-wider border-b border-gray-100">
                  <tr>
                    <th className="py-3.5 px-4">Order #</th>
                    <th className="py-3.5 px-4">Retailer</th>
                    <th className="py-3.5 px-4">Date & Time</th>
                    <th className="py-3.5 px-4">Cases</th>
                    <th className="py-3.5 px-4">Net Total</th>
                    <th className="py-3.5 px-4">Status</th>
                    <th className="py-3.5 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {orders.map((order) => (
                    <tr key={order.id} className="hover:bg-gray-50 transition-colors">
                      <td className="py-3.5 px-4 font-mono font-bold text-gray-900">
                        {order.order_number}
                      </td>
                      <td className="py-3.5 px-4 font-semibold text-gray-800">
                        {order.retailer_name || 'Retailer'}
                      </td>
                      <td className="py-3.5 px-4 text-gray-500 whitespace-nowrap">
                        {new Date(order.created_at).toLocaleDateString()} {new Date(order.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </td>
                      <td className="py-3.5 px-4 text-gray-700">
                        <span className="font-bold">{order.total_cases}</span>
                        {order.total_free_cases > 0 && (
                          <span className="text-emerald-700 font-semibold ml-1">
                            (+{order.total_free_cases})
                          </span>
                        )}
                        <span className="text-[10px] text-gray-400 block">
                          Total: {order.total_fulfilment_cases} cases
                        </span>
                      </td>
                      <td className="py-3.5 px-4 font-black text-gray-900">
                        ₹{Number(order.net_total).toFixed(2)}
                      </td>
                      <td className="py-3.5 px-4">
                        {getStatusBadge(order.status)}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <Link
                          to={`/desk/orders/${order.id}`}
                          className={`inline-block px-3.5 py-1.5 rounded-xl font-bold text-xs shadow-sm transition-all ${
                            order.status === 'SUBMITTED'
                              ? 'bg-primary-600 hover:bg-primary-700 text-white'
                              : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
                          }`}
                        >
                          {order.status === 'SUBMITTED' ? 'Review & Approve →' : 'View Details →'}
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex justify-between items-center text-xs text-gray-500 px-2">
              <span>
                Showing {orders.length} of {total} orders (Page {page} of {totalPages})
              </span>
              <div className="flex gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="px-3 py-1.5 border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50"
                >
                  Previous
                </button>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="px-3 py-1.5 border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DeskOrderQueuePage;
