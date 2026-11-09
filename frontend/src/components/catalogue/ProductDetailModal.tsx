import React from 'react';
import { Product } from '../../api/catalogue';
import StockStatusBadge from './StockStatusBadge';
import SchemeBadge from './SchemeBadge';

interface ProductDetailModalProps {
  product: Product | null;
  onClose: () => void;
  language?: 'en' | 'hi';
}

export const ProductDetailModal: React.FC<ProductDetailModalProps> = ({
  product,
  onClose,
  language = 'en',
}) => {
  if (!product) return null;

  const packPriceFormatted = Number(product.dealer_price_per_pack).toFixed(2);
  const casePriceFormatted = Number(product.dealer_price_per_case).toFixed(2);
  const isOutOfStock = product.stock_cases <= 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-fade-in"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-xl border border-gray-100 overflow-hidden relative max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
        data-testid="product-detail-modal"
      >
        {/* Header */}
        <div className="flex justify-between items-start mb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono font-bold uppercase bg-gray-100 text-gray-700 px-2.5 py-0.5 rounded">
                {product.sku}
              </span>
              {product.category && (
                <span className="text-xs font-semibold text-primary-700 bg-primary-50 px-2.5 py-0.5 rounded">
                  {product.category}
                </span>
              )}
            </div>
            <h2 className="text-2xl font-black text-gray-900 leading-tight">
              {product.name}
            </h2>
          </div>
          <button
            onClick={onClose}
            data-testid="modal-close-btn"
            className="p-2 text-gray-400 hover:text-gray-600 rounded-full hover:bg-gray-100 transition-colors"
            title="Close"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Stock Status */}
        <div className="mb-4">
          <StockStatusBadge
            status={product.stock_status}
            stockCases={product.stock_cases}
            language={language}
          />
        </div>

        {/* Description */}
        {product.description && (
          <p className="text-sm text-gray-600 mb-5 leading-relaxed bg-gray-50 p-3.5 rounded-2xl border border-gray-200">
            {product.description}
          </p>
        )}

        {/* Pricing & Packaging Breakdown */}
        <div className="border border-gray-200 rounded-2xl p-4 mb-5 space-y-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-gray-500">
            {language === 'hi' ? 'मूल्य एवं पैकेजिंग विवरण' : 'Pricing & Packaging Specifications'}
          </h3>

          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="p-2.5 bg-gray-50 rounded-xl">
              <span className="text-xs text-gray-500 block">
                {language === 'hi' ? 'पैक साइज' : 'Retail Pack Size'}
              </span>
              <span className="font-bold text-gray-900">{product.pack_size || 'N/A'}</span>
            </div>

            <div className="p-2.5 bg-gray-50 rounded-xl">
              <span className="text-xs text-gray-500 block">
                {language === 'hi' ? 'पेटी में पैक संख्या' : 'Packs per Case'}
              </span>
              <span className="font-bold text-gray-900">{product.case_qty} packs</span>
            </div>

            <div className="p-2.5 bg-gray-50 rounded-xl">
              <span className="text-xs text-gray-500 block">
                {language === 'hi' ? 'प्रति पैक डीलर दर' : 'Dealer Price / Pack'}
              </span>
              <span className="font-bold text-gray-900">₹{packPriceFormatted}</span>
            </div>

            <div className="p-2.5 bg-emerald-50 rounded-xl border border-emerald-100">
              <span className="text-xs text-emerald-800 font-semibold block">
                {language === 'hi' ? 'कुल पेटी दर' : 'Calculated Case Price'}
              </span>
              <span className="text-base font-black text-emerald-700">₹{casePriceFormatted}</span>
            </div>
          </div>

          <p className="text-[11px] text-gray-400 italic">
            *Pricing Unit: <strong>{product.price_unit}</strong>. Per-pack pricing is a demo assumption.
            GST treatment is unspecified in accordance with client project rules.
          </p>
        </div>

        {/* Active Scheme Details */}
        {product.active_scheme ? (
          <div className="border border-primary-200 bg-primary-50/50 rounded-2xl p-4 mb-5">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-base">🎁</span>
              <h3 className="text-sm font-bold text-primary-900">
                {language === 'hi' ? 'लागू प्रमोशनल स्कीम' : 'Active Promotional Scheme'}
              </h3>
            </div>
            <div className="mb-2">
              <SchemeBadge scheme={product.active_scheme} language={language} />
            </div>
            <div className="text-xs text-primary-800 space-y-1">
              <p>
                <strong>{language === 'hi' ? 'पात्रता:' : 'Eligibility:'}</strong> Minimum {product.active_scheme.min_qty} cases ordered.
              </p>
              <p>
                <strong>{language === 'hi' ? 'वैधता अवधि:' : 'Validity:'}</strong> {product.active_scheme.valid_from} to {product.active_scheme.valid_to}
              </p>
            </div>
          </div>
        ) : (
          <div className="p-3 bg-gray-50 rounded-xl text-xs text-gray-500 mb-5 text-center">
            {language === 'hi' ? 'इस उत्पाद पर वर्तमान में कोई स्कीम नहीं है।' : 'No active promotional scheme on this product.'}
          </div>
        )}

        {/* Modal Actions */}
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 py-3 px-4 border border-gray-300 rounded-xl text-sm font-bold text-gray-700 hover:bg-gray-50 transition-colors"
          >
            {language === 'hi' ? 'बंद करें (Close)' : 'Close'}
          </button>
          <button
            type="button"
            disabled={isOutOfStock}
            onClick={onClose}
            className={`flex-1 py-3 px-4 rounded-xl text-sm font-bold transition-colors ${
              isOutOfStock
                ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                : 'bg-primary-600 hover:bg-primary-700 text-white shadow-sm'
            }`}
          >
            {isOutOfStock
              ? language === 'hi'
                ? 'स्टॉक समाप्त'
                : 'Out of Stock'
              : language === 'hi'
              ? 'ऑर्डर में जोड़ें'
              : 'Add to Order'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ProductDetailModal;
