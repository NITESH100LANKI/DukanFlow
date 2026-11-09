import React, { useEffect, useState } from 'react';
import { useParams, Link, useOutletContext } from 'react-router-dom';
import { getOrderDetailApi, Order } from '../../api/orders';
import { Language } from '../../components/LanguageToggle';

export const OrderDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const context = useOutletContext<{ language: Language }>();
  const language = context?.language || 'en';

  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    const fetchOrder = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getOrderDetailApi(id);
        setOrder(data);
      } catch (err: any) {
        setError(err.response?.data?.detail || err.message || 'Failed to load order');
      } finally {
        setLoading(false);
      }
    };
    fetchOrder();
  }, [id]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'APPROVED':
        return (
          <span className="px-3 py-1 text-xs font-bold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
            ✓ {language === 'hi' ? 'मंज़ूर (Approved)' : 'Approved'}
          </span>
        );
      case 'REJECTED':
        return (
          <span className="px-3 py-1 text-xs font-bold rounded-full bg-rose-100 text-rose-800 border border-rose-300">
            ✕ {language === 'hi' ? 'अस्वीकृत (Rejected)' : 'Rejected'}
          </span>
        );
      default:
        return (
          <span className="px-3 py-1 text-xs font-bold rounded-full bg-amber-100 text-amber-800 border border-amber-300 animate-pulse">
            ⏳ {language === 'hi' ? 'समीक्षाधीन (Under Review)' : 'Submitted — Pending Review'}
          </span>
        );
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
        <p className="text-xs text-gray-500 mt-3">
          {language === 'hi' ? 'ऑर्डर विवरण लोड हो रहा है...' : 'Loading order details...'}
        </p>
      </div>
    );
  }

  if (error || !order) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12 space-y-4">
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-2xl text-xs">
          {error || 'Order not found'}
        </div>
        <Link
          to="/orders"
          className="inline-block text-xs font-bold text-primary-600 hover:text-primary-700"
        >
          {language === 'hi' ? '← ऑर्डर्स सूची पर वापस जाएं' : '← Back to Orders'}
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      {/* Top Bar Navigation */}
      <div className="flex justify-between items-center">
        <Link
          to="/orders"
          className="text-xs font-bold text-gray-500 hover:text-gray-800 transition-colors flex items-center gap-1"
        >
          ← {language === 'hi' ? 'सभी ऑर्डर्स' : 'All Orders'}
        </Link>
        {getStatusBadge(order.status)}
      </div>

      {/* Order Header Card */}
      <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row justify-between sm:items-baseline gap-2">
          <div>
            <div className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">
              {language === 'hi' ? 'ऑर्डर क्रमांक' : 'Order Number'}
            </div>
            <div className="text-xl font-black font-mono text-gray-900">
              {order.order_number}
            </div>
          </div>
          <div className="text-xs text-gray-500">
            {language === 'hi' ? 'सबमिशन तिथि:' : 'Submitted on:'}{' '}
            <span className="font-semibold text-gray-700">
              {new Date(order.created_at).toLocaleString()}
            </span>
          </div>
        </div>

        {/* Rejection Notice if rejected */}
        {order.status === 'REJECTED' && order.rejection_reason && (
          <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl space-y-1">
            <div className="text-xs font-bold text-rose-900">
              {language === 'hi' ? 'अस्वीकृति का कारण (Rejection Reason):' : 'Rejection Reason:'}
            </div>
            <p className="text-xs text-rose-700">{order.rejection_reason}</p>
          </div>
        )}

        {/* Remarks if provided */}
        {order.remarks && (
          <div className="p-3 bg-gray-50 border border-gray-200 rounded-xl text-xs text-gray-600">
            <span className="font-semibold text-gray-800">
              {language === 'hi' ? 'डिलीवरी रिमार्क्स: ' : 'Delivery Remarks: '}
            </span>
            {order.remarks}
          </div>
        )}
      </div>

      {/* Line Items Table */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="p-4 bg-gray-50 border-b border-gray-100 text-xs font-bold text-gray-700 uppercase tracking-wider">
          {language === 'hi' ? 'ऑर्डर किए गए उत्पाद (Ordered Items)' : 'Ordered Items'}
        </div>

        <div className="divide-y divide-gray-100">
          {order.lines.map((line) => (
            <div key={line.id} className="p-4 flex flex-col sm:flex-row justify-between sm:items-center gap-3">
              <div className="space-y-1 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[11px] font-bold text-gray-400 bg-gray-100 px-2 py-0.5 rounded">
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
                  <span>₹{Number(line.price_per_case_snapshot).toFixed(2)} / case</span>
                </div>

                {line.description_snapshot && (
                  <div className="inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-primary-50 text-primary-700 border border-primary-200">
                    🏷️ {line.description_snapshot}
                  </div>
                )}
              </div>

              {/* Quantities & Net Line Total */}
              <div className="flex items-center justify-between sm:justify-end gap-6 text-right">
                <div className="text-left sm:text-right">
                  <div className="text-xs font-bold text-gray-800">
                    {line.qty_cases} {language === 'hi' ? 'पेटी' : 'cases'}
                  </div>
                  {line.free_cases > 0 && (
                    <div className="text-[11px] font-semibold text-emerald-700">
                      +{line.free_cases} free bonus
                    </div>
                  )}
                  <div className="text-[10px] text-gray-400">
                    {language === 'hi' ? 'डिलीवरी:' : 'Fulfilment:'} {line.fulfilment_qty_cases} cases
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-sm font-black text-gray-900">
                    ₹{Number(line.net_amount).toFixed(2)}
                  </div>
                  {Number(line.discount_amount) > 0 && (
                    <div className="text-[10px] text-emerald-600">
                      -₹{Number(line.discount_amount).toFixed(2)} discount
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Financial Summary */}
      <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm space-y-3">
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
          {language === 'hi' ? 'वित्तीय सारांश (Financial Summary)' : 'Financial Summary'}
        </h3>

        <div className="flex justify-between text-xs text-gray-600">
          <span>{language === 'hi' ? 'सकल राशि (Gross Total):' : 'Gross Total:'}</span>
          <span className="font-semibold text-gray-800">₹{Number(order.gross_total).toFixed(2)}</span>
        </div>

        {Number(order.scheme_total) > 0 && (
          <div className="flex justify-between text-xs text-emerald-700 font-semibold">
            <span>{language === 'hi' ? 'कुल स्कीम लाभ (Savings):' : 'Total Scheme Benefits:'}</span>
            <span>-₹{Number(order.scheme_total).toFixed(2)}</span>
          </div>
        )}

        <div className="pt-2 border-t border-gray-100 flex justify-between items-baseline">
          <span className="text-sm font-bold text-gray-900">
            {language === 'hi' ? 'कुल देय राशि (Net Payable):' : 'Net Payable Amount:'}
          </span>
          <span className="text-2xl font-black text-emerald-800">
            ₹{Number(order.net_total).toFixed(2)}
          </span>
        </div>

        <div className="text-[11px] text-gray-400 pt-1">
          {language === 'hi'
            ? `कुल भौतिक पेटी: ${order.total_fulfilment_cases} (खरीदी गई: ${order.total_cases}, मुफ़्त: ${order.total_free_cases})`
            : `Total physical cases to be delivered: ${order.total_fulfilment_cases} (${order.total_cases} paid + ${order.total_free_cases} free)`}
        </div>
      </div>
    </div>
  );
};

export default OrderDetailPage;
