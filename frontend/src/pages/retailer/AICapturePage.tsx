import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCart } from '../../context/CartContext';
import {
  createOrderDraftApi,
  updateDraftLineApi,
  deleteDraftLineApi,
  confirmDraftToCartApi,
  OrderDraft,
  DraftLine,
} from '../../api/ai';

export const AICapturePage: React.FC = () => {
  const navigate = useNavigate();
  const { refreshCart } = useCart();

  const [rawText, setRawText] = useState('');
  const [draft, setDraft] = useState<OrderDraft | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [updatingLineId, setUpdatingLineId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const samplePrompts = [
    '5 peti biscuit, 2 case detergent',
    'मुझे 10 पेटी ग्लूकोज़ बिस्किट और 5 डिब्बे डिटर्जेंट देना',
    'bhai 3 case chai aur 2 peti biscuit bhej dena',
  ];

  const handleExtract = async (textToExtract?: string) => {
    const text = textToExtract || rawText;
    if (!text.trim()) {
      setError('Please enter or paste an order message');
      return;
    }

    setError(null);
    setSuccessMessage(null);
    setIsExtracting(true);

    try {
      const result = await createOrderDraftApi(text);
      setDraft(result);
      if (textToExtract) {
        setRawText(textToExtract);
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to extract draft. Please try again.';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setIsExtracting(false);
    }
  };

  const handleResolveProduct = async (lineId: string, productId: string) => {
    if (!draft) return;
    setUpdatingLineId(lineId);
    setError(null);
    try {
      const updated = await updateDraftLineApi(draft.id, lineId, {
        resolved_product_id: productId,
      });
      setDraft(updated);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update product selection');
    } finally {
      setUpdatingLineId(null);
    }
  };

  const handleResolveUnit = async (lineId: string, unit: 'case') => {
    if (!draft) return;
    setUpdatingLineId(lineId);
    setError(null);
    try {
      const updated = await updateDraftLineApi(draft.id, lineId, {
        normalized_unit: unit,
      });
      setDraft(updated);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update unit');
    } finally {
      setUpdatingLineId(null);
    }
  };

  const handleUpdateQty = async (lineId: string, newQty: number) => {
    if (!draft || newQty < 1) return;
    setUpdatingLineId(lineId);
    setError(null);
    try {
      const updated = await updateDraftLineApi(draft.id, lineId, {
        resolved_qty_cases: newQty,
      });
      setDraft(updated);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update quantity');
    } finally {
      setUpdatingLineId(null);
    }
  };

  const handleDeleteLine = async (lineId: string) => {
    if (!draft) return;
    setUpdatingLineId(lineId);
    setError(null);
    try {
      const updated = await deleteDraftLineApi(draft.id, lineId);
      setDraft(updated);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to remove line');
    } finally {
      setUpdatingLineId(null);
    }
  };

  const handleConfirmDraft = async () => {
    if (!draft) return;
    setIsConfirming(true);
    setError(null);
    try {
      const res = await confirmDraftToCartApi(draft.id);
      await refreshCart();
      setSuccessMessage(res.message);
      setTimeout(() => {
        navigate('/retailer/cart');
      }, 1200);
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to confirm draft to cart';
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
      setIsConfirming(false);
    }
  };

  // Check if draft has unresolved lines
  const hasUnresolvedLines =
    !draft ||
    draft.lines.length === 0 ||
    draft.lines.some(
      (l) =>
        !l.is_confirmed ||
        l.warning === 'OUT_OF_STOCK' ||
        l.normalized_unit !== 'case' ||
        !(l.resolved_product_id || l.matched_product_id)
    );

  return (
    <div className="max-w-4xl mx-auto py-6 px-4 sm:px-6">
      {/* Header */}
      <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm mb-6">
        <div className="flex items-center gap-3 mb-2">
          <span className="p-2.5 rounded-xl bg-purple-100 text-purple-700 text-xl font-bold">
            ✨
          </span>
          <div>
            <h1 className="text-2xl font-black text-gray-900 tracking-tight">
              AI Order Capture (स्मार्ट ऑर्डर कैप्चर)
            </h1>
            <p className="text-sm text-gray-500 font-medium">
              Paste or type your order message in Hindi, Hinglish, or English. Gemini will extract
              a draft for your review.
            </p>
          </div>
        </div>

        {/* Input Box */}
        <div className="mt-4">
          <textarea
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            placeholder="उदाहरण: 5 peti Parle-G 10 rs wali, 2 case detergent powder"
            rows={4}
            className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-purple-500 focus:border-purple-500 text-sm font-medium resize-none"
            disabled={isExtracting}
          />

          {/* Quick prompt pills */}
          <div className="flex flex-wrap items-center gap-2 mt-2">
            <span className="text-xs font-semibold text-gray-400">Quick Samples:</span>
            {samplePrompts.map((sample, i) => (
              <button
                key={i}
                type="button"
                onClick={() => {
                  setRawText(sample);
                  handleExtract(sample);
                }}
                disabled={isExtracting}
                className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-2.5 py-1 rounded-full transition-colors font-medium border border-gray-200"
              >
                {sample}
              </button>
            ))}
          </div>

          <div className="mt-4 flex justify-between items-center">
            <span className="text-xs text-gray-400 font-medium">
              {rawText.length}/2000 characters
            </span>
            <button
              onClick={() => handleExtract()}
              disabled={isExtracting || !rawText.trim()}
              className="px-6 py-2.5 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-300 text-white rounded-xl text-sm font-bold shadow-sm transition-colors flex items-center gap-2"
            >
              {isExtracting ? (
                <>
                  <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  <span>Extracting Draft...</span>
                </>
              ) : (
                <span>Generate Draft (ड्राफ्ट बनाएं) &rarr;</span>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Error & Success Banners */}
      {error && (
        <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 text-sm font-semibold flex items-center justify-between">
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700 font-bold ml-2">
            ✕
          </button>
        </div>
      )}

      {successMessage && (
        <div className="mb-6 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm font-bold flex items-center gap-2">
          <span>✅ {successMessage}</span>
        </div>
      )}

      {/* Draft Review Screen */}
      {draft && (
        <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center pb-4 border-b border-gray-100 gap-2">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider bg-gray-100 text-gray-700 px-2.5 py-0.5 rounded-full">
                  Status: {draft.status}
                </span>
                <span className={`text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full ${
                  draft.parser_used === 'fallback' ? 'bg-amber-100 text-amber-800' : 'bg-purple-100 text-purple-800'
                }`}>
                  Parser: {draft.parser_used === 'fallback' ? 'Offline Rule-Based' : 'Gemini AI'}
                </span>
                <span className="text-xs text-gray-400 font-medium">
                  {draft.lines.length} item(s) extracted
                </span>
              </div>
              <p className="text-xs text-gray-600 mt-1 italic">
                Original text: &ldquo;{draft.original_message}&rdquo;
              </p>
            </div>

            {draft.status === 'DRAFT' && (
              <button
                onClick={handleConfirmDraft}
                disabled={isConfirming || hasUnresolvedLines}
                className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-xl text-xs font-bold shadow-xs transition-colors"
              >
                {isConfirming
                  ? 'Adding to Cart...'
                  : hasUnresolvedLines
                  ? 'Resolve Issues to Confirm'
                  : 'Send to Cart (कार्ट में जोड़ें) 🛒'}
              </button>
            )}
          </div>

          {/* Offline Fallback Notice */}
          {draft.parser_used === 'fallback' && (
            <div className="mt-4 p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs font-medium flex items-center gap-2">
              <span className="text-base">⚠️</span>
              <span>
                <strong>Offline Rule-Based Parser Used:</strong> This draft was parsed using the local FMCG rule engine (Gemini API was rate-limited or unavailable). Please review item mappings and case quantities before confirming.
              </span>
            </div>
          )}

          {/* Draft Lines */}
          <div className="mt-4 space-y-4">
            {draft.lines.map((line: DraftLine, idx: number) => {
              const activeProduct = line.resolved_product || line.matched_product;
              const isUpdating = updatingLineId === line.id;

              return (
                <div
                  key={line.id}
                  className={`p-4 rounded-xl border transition-all ${
                    line.warning === 'OUT_OF_STOCK'
                      ? 'border-red-200 bg-red-50/40'
                      : line.is_confirmed
                      ? 'border-emerald-200 bg-emerald-50/20'
                      : 'border-amber-200 bg-amber-50/30'
                  }`}
                >
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-bold bg-gray-200 text-gray-800 px-2 py-0.5 rounded">
                        #{idx + 1}
                      </span>
                      <span className="text-xs font-bold text-gray-700 bg-white border border-gray-200 px-2.5 py-0.5 rounded-md">
                        &ldquo;{line.raw_fragment}&rdquo;
                      </span>

                      {/* Status Badges */}
                      {line.match_status === 'confirmed' && (
                        <span className="text-[11px] font-bold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded">
                          CONFIRMED ({line.confidence?.toUpperCase() || 'HIGH'})
                        </span>
                      )}
                      {line.match_status === 'ambiguous' && (
                        <span className="text-[11px] font-bold bg-amber-100 text-amber-800 px-2 py-0.5 rounded">
                          AMBIGUOUS (अस्पष्ट)
                        </span>
                      )}
                      {line.match_status === 'unmatched' && (
                        <span className="text-[11px] font-bold bg-rose-100 text-rose-800 px-2 py-0.5 rounded">
                          UNMATCHED (अनदेखा)
                        </span>
                      )}

                      {line.warning === 'OUT_OF_STOCK' && (
                        <span className="text-[11px] font-black bg-red-600 text-white px-2 py-0.5 rounded">
                          OUT OF STOCK
                        </span>
                      )}
                    </div>

                    <button
                      onClick={() => handleDeleteLine(line.id)}
                      disabled={isUpdating || draft.status !== 'DRAFT'}
                      className="text-xs text-red-500 hover:text-red-700 font-semibold transition-colors"
                      title="Discard item"
                    >
                      Remove ✕
                    </button>
                  </div>

                  {/* Product Details or Selection */}
                  <div className="mt-3 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                    <div className="flex-1">
                      {activeProduct ? (
                        <div>
                          <div className="text-sm font-bold text-gray-900">{activeProduct.name}</div>
                          <div className="text-xs text-gray-500 font-medium">
                            SKU: {activeProduct.sku} | Case Qty: {activeProduct.case_qty} packs | Price:{' '}
                            ₹{Number(activeProduct.dealer_price_per_case ?? (Number(activeProduct.dealer_price_per_pack) * activeProduct.case_qty)).toFixed(2)}/case
                          </div>
                        </div>
                      ) : (
                        <div className="text-xs text-amber-700 font-semibold">
                          ⚠️ {line.clarification_reason || 'Product needs to be selected'}
                        </div>
                      )}
                    </div>

                    {/* Quantity Selector */}
                    <div className="flex items-center gap-2">
                      <label className="text-xs font-semibold text-gray-600">Cases:</label>
                      <input
                        type="number"
                        min="1"
                        value={line.resolved_qty_cases || line.quantity_value || 1}
                        onChange={(e) => handleUpdateQty(line.id, parseInt(e.target.value) || 1)}
                        disabled={isUpdating || draft.status !== 'DRAFT'}
                        className="w-16 px-2 py-1 text-center font-bold text-sm border border-gray-300 rounded-lg focus:ring-1 focus:ring-purple-500"
                      />
                    </div>
                  </div>

                  {/* Ambiguity Resolution Options */}
                  {line.match_status === 'ambiguous' && line.alternatives && line.alternatives.length > 0 && (
                    <div className="mt-3 p-3 bg-white border border-amber-200 rounded-xl">
                      <div className="text-xs font-bold text-amber-900 mb-2">
                        Did you mean one of these products? (कौन सा उत्पाद चुनें?)
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {line.alternatives.map((alt) => (
                          <button
                            key={alt.id}
                            type="button"
                            onClick={() => handleResolveProduct(line.id, alt.id)}
                            disabled={isUpdating}
                            className={`p-2.5 rounded-lg border text-left text-xs transition-all ${
                              line.resolved_product_id === alt.id
                                ? 'border-purple-600 bg-purple-50 font-bold'
                                : 'border-gray-200 hover:border-purple-300 bg-white'
                            }`}
                          >
                            <div className="font-bold text-gray-900">{alt.name}</div>
                            <div className="text-[11px] text-gray-500">
                              SKU: {alt.sku} • ₹{Number(alt.dealer_price_per_case).toFixed(2)}/case
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Case vs Piece Clarification */}
                  {line.normalized_unit !== 'case' && (
                    <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-xl flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
                      <div className="text-xs text-amber-800 font-semibold">
                        ⚠️ Unit was stated as &ldquo;{line.unit_text || 'unspecified'}&rdquo; (quantity: {line.quantity_value || 1}). Wholesale orders require full cases. Confirm as {line.quantity_value || 1} wholesale case{(line.quantity_value || 1) > 1 ? 's' : ''}?
                      </div>
                      <button
                        type="button"
                        onClick={() => handleResolveUnit(line.id, 'case')}
                        disabled={isUpdating}
                        className="px-3 py-1 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-bold shadow-xs whitespace-nowrap"
                      >
                        Confirm {line.quantity_value || 1} as Cases ({line.quantity_value || 1} केस में बदलें) ✓
                      </button>
                    </div>
                  )}

                  {/* Out of Stock Warning Notice */}
                  {line.warning === 'OUT_OF_STOCK' && (
                    <div className="mt-2 text-xs text-red-600 font-bold">
                      ❌ This product is currently out of stock at the warehouse. Please remove this item before
                      confirming to cart.
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default AICapturePage;
