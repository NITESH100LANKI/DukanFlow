import React from 'react';
import { Product } from '../../api/catalogue';
import StockStatusBadge from './StockStatusBadge';
import SchemeBadge from './SchemeBadge';

interface ProductCardProps {
  product: Product;
  onSelect: (product: Product) => void;
  language?: 'en' | 'hi';
}

export const ProductCard: React.FC<ProductCardProps> = ({
  product,
  onSelect,
  language = 'en',
}) => {
  const isOutOfStock = product.stock_cases <= 0;
  const packPriceFormatted = Number(product.dealer_price_per_pack).toFixed(2);
  const casePriceFormatted = Number(product.dealer_price_per_case).toFixed(2);

  return (
    <div
      onClick={() => onSelect(product)}
      className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm hover:shadow-md hover:border-primary-300 transition-all cursor-pointer flex flex-col justify-between"
      data-testid={`product-card-${product.sku}`}
    >
      <div>
        {/* Top Badges */}
        <div className="flex flex-wrap justify-between items-center gap-2 mb-3">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono font-bold uppercase tracking-wider bg-gray-100 text-gray-700 px-2 py-0.5 rounded">
              {product.sku}
            </span>
            {product.category && (
              <span className="text-[11px] font-semibold text-primary-700 bg-primary-50 px-2 py-0.5 rounded">
                {product.category}
              </span>
            )}
          </div>
          <StockStatusBadge
            status={product.stock_status}
            stockCases={product.stock_cases}
            language={language}
          />
        </div>

        {/* Product Name & Description */}
        <h3 className="text-lg font-bold text-gray-900 leading-snug mb-1">
          {product.name}
        </h3>
        {product.description && (
          <p className="text-xs text-gray-500 line-clamp-2 mb-3">
            {product.description}
          </p>
        )}

        {/* Packaging Specs */}
        <div className="bg-gray-50 rounded-xl p-2.5 mb-3 text-xs text-gray-600 flex justify-between items-center">
          <div>
            <span className="font-semibold text-gray-800">
              {language === 'hi' ? 'पैक साइज:' : 'Pack Size:'}
            </span>{' '}
            {product.pack_size || 'Standard'}
          </div>
          <div>
            <span className="font-semibold text-gray-800">
              {language === 'hi' ? 'पेटी मात्रा:' : 'Case Qty:'}
            </span>{' '}
            <span className="font-bold text-gray-900">{product.case_qty}</span> packs/case
          </div>
        </div>

        {/* Pricing Box */}
        <div className="border border-emerald-100 bg-emerald-50/50 rounded-xl p-3 mb-3">
          <div className="flex justify-between items-baseline">
            <span className="text-xs font-semibold text-emerald-900">
              {language === 'hi' ? 'पेटी दर (Case Rate):' : 'Wholesale Case Rate:'}
            </span>
            <span className="text-xl font-black text-emerald-700">
              ₹{casePriceFormatted}
            </span>
          </div>
          <div className="flex justify-between items-center text-xs text-gray-600 mt-1">
            <span>{language === 'hi' ? 'प्रति पैक दर:' : 'Unit price:'}</span>
            <span className="font-semibold">₹{packPriceFormatted} / pack</span>
          </div>
          <p className="text-[10px] text-gray-400 mt-1 italic">
            *Demo assumption: per-pack pricing. Billed by full case.
          </p>
        </div>

        {/* Active Scheme Banner */}
        {product.active_scheme && (
          <div className="mb-3">
            <SchemeBadge scheme={product.active_scheme} language={language} />
          </div>
        )}
      </div>

      {/* Action Footer */}
      <div className="pt-3 border-t border-gray-100 flex gap-2">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onSelect(product);
          }}
          className="flex-1 py-2.5 px-3 border border-gray-300 rounded-xl text-xs font-bold text-gray-700 hover:bg-gray-50 transition-colors"
        >
          {language === 'hi' ? 'विवरण देखें (Details)' : 'View Details'}
        </button>

        <button
          type="button"
          disabled={isOutOfStock}
          onClick={(e) => {
            e.stopPropagation();
            onSelect(product);
          }}
          className={`flex-1 py-2.5 px-3 rounded-xl text-xs font-bold transition-colors ${
            isOutOfStock
              ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
              : 'bg-primary-600 hover:bg-primary-700 text-white shadow-xs'
          }`}
        >
          {isOutOfStock
            ? language === 'hi'
              ? 'स्टॉक नहीं है'
              : 'Out of Stock'
            : language === 'hi'
            ? 'ऑर्डर जोड़ें +'
            : 'Order Cases +'}
        </button>
      </div>
    </div>
  );
};

export default ProductCard;
