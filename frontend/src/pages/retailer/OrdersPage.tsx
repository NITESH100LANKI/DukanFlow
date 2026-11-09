import React, { useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { getOrdersApi, OrderListItem } from '../../api/orders';
import { Language } from '../../components/LanguageToggle';

export const OrdersPage: React.FC = () => {
  const context = useOutletContext<{ language: Language }>();
  const language = context?.language || 'en';

  const [orders, setOrders] = useState<OrderListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchOrders = async (pageNum = 1) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getOrdersApi(pageNum, 10);
      setOrders(data.items);
      setTotal(data.total);
      setPage(data.page);
      setTotalPages(data.total_pages);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load orders');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders(page);
  }, [page]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'APPROVED':
        return (
          <span className="px-2.5 py-1 text-xs font-bold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
            {language === 'hi' ? 'मंज़ूर (Approved)' : 'Approved'}
          </span>
        );
      case 'REJECTED':
        return (
          <span className="px-2.5 py-1 text-xs font-bold rounded-full bg-rose-100 text-rose-800 border border-rose-300">
            {language === 'hi' ? 'अस्वीकृत (Rejected)' : 'Rejected'}
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-1 text-xs font-bold rounded-full bg-amber-100 text-amber-800 border border-amber-300">
            {language === 'hi' ? 'समीक्षाधीन (Under Review)' : 'Submitted'}
          </span>
        );
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-black text-gray-900">
            {language === 'hi' ? 'मेरे ऑर्डर्स (Order History)' : 'My Orders'}
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            {language === 'hi'
              ? 'आपके द्वारा सबमिट किए गए सभी थोक ऑर्डर्स एवं उनकी स्थिति।'
              : 'Track all wholesale orders submitted to the distributor.'}
          </p>
        </div>
        <Link
          to="/catalogue"
          className="inline-flex items-center text-xs font-bold text-primary-600 hover:text-primary-700 bg-primary-50 hover:bg-primary-100 px-3.5 py-2 rounded-xl transition-colors border border-primary-200 self-start sm:self-auto"
        >
          {language === 'hi' ? '← कैटलॉग पर जाएं' : '← Browse Catalogue'}
        </Link>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="text-center py-16 bg-white rounded-2xl border border-gray-100 shadow-sm">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
          <p className="text-xs text-gray-500 mt-3">
            {language === 'hi' ? 'ऑर्डर्स लोड हो रहे हैं...' : 'Loading orders...'}
          </p>
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-2xl text-xs flex justify-between items-center">
          <span>{error}</span>
          <button
            onClick={() => fetchOrders(page)}
            className="text-xs font-bold underline hover:text-red-800"
          >
            {language === 'hi' ? 'पुनः प्रयास करें' : 'Retry'}
          </button>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && orders.length === 0 && (
        <div className="text-center py-16 bg-white rounded-2xl border border-gray-100 shadow-sm space-y-4">
          <div className="text-4xl">📦</div>
          <h2 className="text-base font-bold text-gray-800">
            {language === 'hi' ? 'अभी तक कोई ऑर्डर नहीं है' : 'No orders found'}
          </h2>
          <p className="text-xs text-gray-500 max-w-sm mx-auto">
            {language === 'hi'
              ? 'आपने अभी तक कोई थोक ऑर्डर नहीं दिया है। कैटलॉग से उत्पाद कार्ट में जोड़ें और ऑर्डर सबमिट करें।'
              : 'You have not placed any orders yet. Add products from the catalogue and submit your cart.'}
          </p>
          <Link
            to="/catalogue"
            className="inline-block bg-primary-600 hover:bg-primary-700 text-white font-bold text-xs px-5 py-2.5 rounded-xl shadow transition-colors"
          >
            {language === 'hi' ? 'ऑर्डर शुरू करें' : 'Start Ordering'}
          </Link>
        </div>
      )}

      {/* Orders List */}
      {!loading && !error && orders.length > 0 && (
        <div className="space-y-4">
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="divide-y divide-gray-100">
              {orders.map((order) => (
                <div
                  key={order.id}
                  className="p-5 hover:bg-gray-50 transition-colors flex flex-col md:flex-row justify-between items-start md:items-center gap-4"
                >
                  <div className="space-y-1.5 flex-1">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-sm font-bold text-gray-900">
                        {order.order_number}
                      </span>
                      {getStatusBadge(order.status)}
                    </div>
                    <div className="text-xs text-gray-500 flex flex-wrap gap-x-4 gap-y-1">
                      <span>
                        📅 {new Date(order.created_at).toLocaleDateString()} {new Date(order.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                      <span>
                        📦 {order.total_cases} {language === 'hi' ? 'पेटी' : 'cases'}
                        {order.total_free_cases > 0 && (
                          <span className="text-emerald-700 font-semibold ml-1">
                            (+{order.total_free_cases} free)
                          </span>
                        )}
                      </span>
                      <span>
                        🛒 {order.line_count} {language === 'hi' ? 'आइटम' : 'item(s)'}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between w-full md:w-auto md:justify-end gap-5">
                    <div className="text-left md:text-right">
                      <div className="text-[11px] text-gray-400 font-semibold uppercase">
                        {language === 'hi' ? 'कुल देय राशि' : 'Net Total'}
                      </div>
                      <div className="text-base font-black text-emerald-800">
                        ₹{Number(order.net_total).toFixed(2)}
                      </div>
                    </div>

                    <Link
                      to={`/orders/${order.id}`}
                      className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white font-bold text-xs rounded-xl shadow-sm hover:shadow transition-all whitespace-nowrap"
                    >
                      {language === 'hi' ? 'विवरण देखें →' : 'View Details →'}
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex justify-between items-center text-xs text-gray-500 px-2">
              <span>
                {language === 'hi'
                  ? `कुल ${total} ऑर्डर्स (पेज ${page} / ${totalPages})`
                  : `Showing ${orders.length} of ${total} orders (Page ${page} of ${totalPages})`}
              </span>
              <div className="flex gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="px-3 py-1.5 border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50"
                >
                  {language === 'hi' ? 'पिछला' : 'Previous'}
                </button>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="px-3 py-1.5 border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50"
                >
                  {language === 'hi' ? 'अगला' : 'Next'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default OrdersPage;
