import React, { useState } from 'react';
import { Link, useOutletContext, useNavigate } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { Language } from '../components/LanguageToggle';
import { placeOrderApi } from '../api/orders';

export const CartPage: React.FC = () => {
  const context = useOutletContext<{ language: Language }>();
  const language = context?.language || 'en';
  const navigate = useNavigate();

  const { cart, loading, error, updateQty, removeLine, clearCart, refreshCart } = useCart();
  const [updatingLineId, setUpdatingLineId] = useState<string | null>(null);
  const [clearing, setClearing] = useState(false);
  const [placingOrder, setPlacingOrder] = useState(false);
  const [orderRemarks, setOrderRemarks] = useState('');
  const [orderError, setOrderError] = useState<string | null>(null);

  const handleQtyChange = async (lineId: string, newQty: number) => {
    if (newQty < 1) return;
    setUpdatingLineId(lineId);
    try {
      await updateQty(lineId, newQty);
    } catch (err) {
      console.error(err);
    } finally {
      setUpdatingLineId(null);
    }
  };

  const handleRemove = async (lineId: string) => {
    setUpdatingLineId(lineId);
    try {
      await removeLine(lineId);
    } catch (err) {
      console.error(err);
    } finally {
      setUpdatingLineId(null);
    }
  };

  const handlePlaceOrder = async () => {
    if (!cart || cart.lines.length === 0) return;
    setPlacingOrder(true);
    setOrderError(null);
    try {
      const idempotencyKey = `ord-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      const order = await placeOrderApi(orderRemarks.trim() || undefined, idempotencyKey);
      await refreshCart();
      navigate(`/orders/${order.id}`);
    } catch (err: any) {
      const msg = err.response?.data?.detail?.message || err.response?.data?.detail || err.message || 'Failed to place order';
      setOrderError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setPlacingOrder(false);
    }
  };

  const handleClear = async () => {
    if (!window.confirm(language === 'hi' ? 'क्या आप कार्ट खाली करना चाहते हैं?' : 'Are you sure you want to clear your cart?')) {
      return;
    }
    setClearing(true);
    try {
      await clearCart();
    } catch (err) {
      console.error(err);
    } finally {
      setClearing(false);
    }
  };

  const lines = cart?.lines || [];
  const summary = cart?.summary;
  const isEmpty = !loading && lines.length === 0;

  return (
    <div className="max-w-7xl mx-auto py-2">
      {/* Header */}
      <div className="mb-6 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-primary-700 bg-primary-100 px-2.5 py-0.5 rounded-full">
            {language === 'hi' ? 'थोक कार्ट' : 'Wholesale Kirana Cart'}
          </span>
          <h1 className="text-2xl sm:text-3xl font-black text-gray-900 mt-1">
            {language === 'hi' ? 'आपकी शॉपिंग कार्ट' : 'Your Shopping Cart'}
          </h1>
          <p className="text-xs sm:text-sm text-gray-500 font-medium mt-0.5">
            {language === 'hi'
              ? 'योजना छूट एवं मुफ्त पेटी लाभ के साथ सत्यापित पेटी दरें'
              : 'Verified case pricing with automated distributor schemes and free-goods calculations'}
          </p>
        </div>

        <Link
          to="/retailer/catalogue"
          className="inline-flex items-center gap-1.5 px-4 py-2 border border-gray-300 rounded-xl text-xs font-bold text-gray-700 hover:bg-gray-50 transition-colors"
        >
          &larr; {language === 'hi' ? 'कैटलॉग में वापस जाएं' : 'Continue Shopping'}
        </Link>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-2xl p-4 mb-6 flex justify-between items-center text-xs sm:text-sm font-semibold">
          <span>{error}</span>
          <button
            onClick={refreshCart}
            className="px-3 py-1 bg-red-600 text-white rounded-lg text-xs font-bold hover:bg-red-700"
          >
            {language === 'hi' ? 'पुनः प्रयास' : 'Retry'}
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && !cart && (
        <div className="bg-white border border-gray-200 rounded-3xl p-8 shadow-sm animate-pulse space-y-4" data-testid="cart-skeleton">
          <div className="h-6 bg-gray-200 rounded w-1/4"></div>
          <div className="h-16 bg-gray-100 rounded-xl"></div>
          <div className="h-16 bg-gray-100 rounded-xl"></div>
          <div className="h-24 bg-gray-100 rounded-xl"></div>
        </div>
      )}

      {/* Empty State */}
      {isEmpty && (
        <div className="bg-white border border-gray-200 rounded-3xl p-12 text-center my-6 max-w-lg mx-auto shadow-sm" data-testid="cart-empty">
          <div className="w-16 h-16 bg-primary-50 text-primary-600 rounded-full flex items-center justify-center mx-auto mb-4 text-3xl">
            🛒
          </div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">
            {language === 'hi' ? 'आपकी कार्ट खाली है' : 'Your Cart is Empty'}
          </h2>
          <p className="text-xs text-gray-500 mb-6 leading-relaxed">
            {language === 'hi'
              ? 'कैटलॉग में उपलब्ध उत्पादों की पेटी दरें एवं आकर्षक स्कीमें देखें और ऑर्डर तैयार करें।'
              : 'Explore the wholesale FMCG catalogue, benefit from Buy-N-Get-M-Free schemes, and start an order.'}
          </p>
          <Link
            to="/retailer/catalogue"
            className="inline-block px-6 py-3 bg-primary-600 hover:bg-primary-700 text-white rounded-xl text-xs font-bold transition-colors shadow-xs"
          >
            {language === 'hi' ? 'उत्पाद कैटलॉग देखें (Browse Catalogue)' : 'Browse Product Catalogue'} &rarr;
          </Link>
        </div>
      )}

      {/* Non-empty Cart Content */}
      {!isEmpty && cart && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start" data-testid="cart-content">
          {/* Left: Cart Line Items */}
          <div className="lg:col-span-2 space-y-4">
            <div className="bg-white border border-gray-200 rounded-3xl p-5 shadow-sm">
              <div className="flex justify-between items-center mb-4 pb-3 border-b border-gray-100">
                <span className="text-xs font-bold text-gray-700 uppercase tracking-wider">
                  {language === 'hi' ? 'कार्ट उत्पाद सूची' : 'Cart Items'} ({lines.length})
                </span>
                <button
                  type="button"
                  onClick={handleClear}
                  disabled={clearing}
                  className="text-xs font-semibold text-red-600 hover:text-red-700 hover:underline transition-colors disabled:opacity-50"
                >
                  {language === 'hi' ? 'पूरी कार्ट खाली करें' : 'Clear All'}
                </button>
              </div>

              <div className="divide-y divide-gray-100">
                {lines.map((line) => {
                  const isUpdating = updatingLineId === line.id;
                  const isFreeScheme = line.qty_free > 0;
                  const hasDiscount = Number(line.discount_amount) > 0;

                  return (
                    <div
                      key={line.id}
                      className="py-4 first:pt-0 last:pb-0 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4"
                      data-testid={`cart-line-${line.sku}`}
                    >
                      {/* Product Info */}
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-[11px] font-mono font-bold uppercase bg-gray-100 text-gray-700 px-2 py-0.5 rounded">
                            {line.sku}
                          </span>
                          <span className="text-xs text-gray-500">
                            {line.pack_size} ({line.case_qty} packs/case)
                          </span>
                        </div>
                        <h3 className="text-base font-bold text-gray-900 leading-snug">
                          {line.name}
                        </h3>
                        <p className="text-xs text-gray-600 mt-0.5">
                          ₹{Number(line.price_per_case).toFixed(2)} / case
                          <span className="text-gray-400 text-[11px] ml-1">
                            (₹{Number(line.price_per_pack).toFixed(2)}/pack)
                          </span>
                        </p>

                        {/* Scheme Badge on Line */}
                        {line.scheme_applied && (
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {isFreeScheme && (
                              <span className="inline-flex items-center gap-1 text-[11px] font-bold bg-primary-50 text-primary-800 border border-primary-200 px-2 py-0.5 rounded-md">
                                <span>🎁</span>
                                <span>
                                  {language === 'hi'
                                    ? `+${line.qty_free} पेटी मुफ्त (कुल डिलीवरी: ${line.qty_fulfilment} पेटी)`
                                    : `+${line.qty_free} Free Case (Fulfilment: ${line.qty_fulfilment} cases)`}
                                </span>
                              </span>
                            )}
                            {hasDiscount && (
                              <span className="inline-flex items-center gap-1 text-[11px] font-bold bg-amber-50 text-amber-800 border border-amber-200 px-2 py-0.5 rounded-md">
                                <span>🏷️</span>
                                <span>
                                  {language === 'hi'
                                    ? `छूट: -₹${Number(line.discount_amount).toFixed(2)}`
                                    : `Discount: -₹${Number(line.discount_amount).toFixed(2)}`}
                                </span>
                              </span>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Quantity Stepper & Subtotal */}
                      <div className="flex items-center justify-between sm:justify-end w-full sm:w-auto gap-4">
                        <div className="flex items-center gap-1.5 bg-gray-50 border border-gray-300 rounded-xl p-1">
                          <button
                            type="button"
                            disabled={isUpdating || line.qty_cases <= 1}
                            onClick={() => handleQtyChange(line.id, line.qty_cases - 1)}
                            className="w-7 h-7 rounded-lg bg-white border border-gray-200 font-bold text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center transition-colors"
                            title="Decrease quantity"
                          >
                            -
                          </button>
                          <span className="w-8 text-center font-bold text-xs text-gray-900">
                            {line.qty_cases}
                          </span>
                          <button
                            type="button"
                            disabled={isUpdating}
                            onClick={() => handleQtyChange(line.id, line.qty_cases + 1)}
                            className="w-7 h-7 rounded-lg bg-white border border-gray-200 font-bold text-sm text-gray-700 hover:bg-gray-100 disabled:opacity-30 flex items-center justify-center transition-colors"
                            title="Increase quantity"
                          >
                            +
                          </button>
                        </div>

                        {/* Line Totals */}
                        <div className="text-right min-w-[90px]">
                          <span className="text-sm font-black text-gray-900 block">
                            ₹{Number(line.net_line_total).toFixed(2)}
                          </span>
                          {hasDiscount && (
                            <span className="text-[11px] text-gray-400 line-through block">
                              ₹{Number(line.gross_line_total).toFixed(2)}
                            </span>
                          )}
                        </div>

                        {/* Remove Line Button */}
                        <button
                          type="button"
                          disabled={isUpdating}
                          onClick={() => handleRemove(line.id)}
                          className="p-1.5 text-gray-400 hover:text-red-600 rounded-lg hover:bg-gray-100 transition-colors"
                          title="Remove item"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Right: Order Summary Panel */}
          {summary && (
            <div className="bg-white border border-gray-200 rounded-3xl p-6 shadow-sm space-y-5 sticky top-24" data-testid="cart-summary">
              <h2 className="text-lg font-black text-gray-900 pb-3 border-b border-gray-100">
                {language === 'hi' ? 'ऑर्डर सारांश (Summary)' : 'Order Summary'}
              </h2>

              {/* Case Count Breakdown */}
              <div className="space-y-2 text-xs">
                <div className="flex justify-between text-gray-600">
                  <span>{language === 'hi' ? 'सशुल्क पेटी (Paid Cases):' : 'Paid Cases:'}</span>
                  <span className="font-bold text-gray-900">{summary.total_cases_paid}</span>
                </div>
                <div className="flex justify-between text-primary-700 font-semibold">
                  <span>{language === 'hi' ? 'मुफ्त पेटी (Free Scheme Cases):' : 'Free Scheme Cases:'}</span>
                  <span className="font-bold text-primary-700">+{summary.total_cases_free}</span>
                </div>
                <div className="flex justify-between text-gray-800 font-bold pt-1 border-t border-dashed border-gray-200">
                  <span>{language === 'hi' ? 'कुल डिलीवरी पेटी (Total Fulfilment):' : 'Total Dispatch Cases:'}</span>
                  <span className="text-gray-900 font-black">{summary.total_cases_fulfilment}</span>
                </div>
              </div>

              {/* Financial Totals Breakdown */}
              <div className="space-y-2 text-xs pt-3 border-t border-gray-100">
                <div className="flex justify-between text-gray-600">
                  <span>{language === 'hi' ? 'सकल मूल्य (Gross Amount):' : 'Gross Amount:'}</span>
                  <span className="font-semibold text-gray-900">₹{Number(summary.gross_total).toFixed(2)}</span>
                </div>

                {Number(summary.total_discount) > 0 && (
                  <div className="flex justify-between text-amber-700 font-semibold">
                    <span>{language === 'hi' ? 'योजना छूट (Scheme Discount):' : 'Scheme Discount:'}</span>
                    <span className="font-bold">-₹{Number(summary.total_discount).toFixed(2)}</span>
                  </div>
                )}

                {Number(summary.total_benefit_value) > 0 && (
                  <div className="flex justify-between text-primary-700 text-[11px] italic">
                    <span>{language === 'hi' ? 'कुल लाभ मूल्य (Free + Discount):' : 'Total Scheme Benefit:'}</span>
                    <span className="font-semibold">₹{Number(summary.total_benefit_value).toFixed(2)}</span>
                  </div>
                )}
              </div>

              {/* Net Payable Highlight */}
              <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-4">
                <div className="flex justify-between items-baseline">
                  <span className="text-xs font-bold text-emerald-900 uppercase tracking-wider">
                    {language === 'hi' ? 'कुल देय राशि (Net Payable):' : 'Net Payable Amount:'}
                  </span>
                  <span className="text-2xl font-black text-emerald-800">
                    ₹{Number(summary.net_total).toFixed(2)}
                  </span>
                </div>
                <p className="text-[10px] text-emerald-700 mt-1 italic">
                  *All prices derived from verified wholesale case rates. GST unspecified.
                </p>
              </div>

              {/* Order Remarks */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-700">
                  {language === 'hi' ? 'विशेष निर्देश / रिमार्क्स (वैकल्पिक):' : 'Delivery Remarks (Optional):'}
                </label>
                <input
                  type="text"
                  value={orderRemarks}
                  onChange={(e) => setOrderRemarks(e.target.value)}
                  placeholder={language === 'hi' ? 'उदा. सुबह 10 बजे से पहले डिलीवरी करें' : 'e.g. Deliver before 10 AM'}
                  className="w-full text-xs p-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:outline-none"
                />
              </div>

              {/* Order Error */}
              {orderError && (
                <div className="bg-red-50 border border-red-200 text-red-700 p-3 rounded-xl text-xs">
                  {orderError}
                </div>
              )}

              {/* Place Order CTA */}
              <div className="space-y-2 pt-2">
                <button
                  type="button"
                  onClick={handlePlaceOrder}
                  disabled={placingOrder || cart.lines.length === 0}
                  className="w-full py-3.5 px-4 rounded-xl text-sm font-bold bg-primary-600 hover:bg-primary-700 text-white shadow-md hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed select-none text-center"
                >
                  {placingOrder
                    ? (language === 'hi' ? 'ऑर्डर प्रोसेस हो रहा है...' : 'Submitting Order...')
                    : (language === 'hi' ? 'ऑर्डर सबमिट करें (Place Order)' : 'Place Order Now')}
                </button>
                <p className="text-[11px] text-gray-500 text-center">
                  {language === 'hi'
                    ? 'ऑर्डर सबमिट होने के बाद ऑर्डर डेस्क द्वारा समीक्षा की जाएगी।'
                    : 'Order will be sent to the Order Desk for stock review and dispatch approval.'}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default CartPage;
