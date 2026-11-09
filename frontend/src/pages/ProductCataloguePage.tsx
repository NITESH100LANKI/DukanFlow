import React, { useState, useEffect, useCallback } from 'react';
import { useOutletContext } from 'react-router-dom';
import {
  Product,
  ProductListResponse,
  getProducts,
  getCategories,
} from '../api/catalogue';
import SearchBar from '../components/catalogue/SearchBar';
import ProductCard from '../components/catalogue/ProductCard';
import ProductDetailModal from '../components/catalogue/ProductDetailModal';
import { Language } from '../components/LanguageToggle';

export const ProductCataloguePage: React.FC = () => {
  const context = useOutletContext<{ language: Language }>();
  const language = context?.language || 'en';

  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [pageSize] = useState(12);

  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [inStockOnly, setInStockOnly] = useState(false);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);

  // Fetch distinct categories once
  useEffect(() => {
    let isMounted = true;
    getCategories()
      .then((cats) => {
        if (isMounted) setCategories(cats);
      })
      .catch((err) => {
        console.error('Failed to load categories', err);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  // Fetch products whenever filters or page change
  const fetchProducts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data: ProductListResponse = await getProducts({
        q: searchTerm,
        category: selectedCategory === 'all' ? undefined : selectedCategory,
        in_stock: inStockOnly,
        page,
        page_size: pageSize,
      });
      setProducts(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err: any) {
      console.error('Error fetching catalogue:', err);
      setError(
        err.response?.data?.detail ||
          (language === 'hi'
            ? 'कैटलॉग लोड करने में त्रुटि। कृपया पुनः प्रयास करें।'
            : 'Failed to load product catalogue. Please check connection and try again.')
      );
    } finally {
      setLoading(false);
    }
  }, [searchTerm, selectedCategory, inStockOnly, page, pageSize, language]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  const handleSearchChange = (val: string) => {
    setSearchTerm(val);
    setPage(1);
  };

  const handleCategoryChange = (cat: string) => {
    setSelectedCategory(cat);
    setPage(1);
  };

  const handleInStockToggle = (checked: boolean) => {
    setInStockOnly(checked);
    setPage(1);
  };

  const handleResetFilters = () => {
    setSearchTerm('');
    setSelectedCategory('all');
    setInStockOnly(false);
    setPage(1);
  };

  return (
    <div className="max-w-7xl mx-auto py-2">
      {/* Page Header */}
      <div className="mb-6 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-primary-700 bg-primary-100 px-2.5 py-0.5 rounded-full">
            {language === 'hi' ? 'थोक कैटलॉग' : 'Wholesale FMCG Catalogue'}
          </span>
          <h1 className="text-2xl sm:text-3xl font-black text-gray-900 mt-1">
            {language === 'hi' ? 'उत्पाद एवं योजनाएं (Schemes)' : 'Product Catalogue & Schemes'}
          </h1>
          <p className="text-xs sm:text-sm text-gray-500 font-medium mt-0.5">
            {language === 'hi'
              ? 'किराना दुकानदारों के लिए थोक दरें एवं आकर्षक पेटी स्कीमें'
              : 'Wholesale case pricing and distributor schemes for verified Kirana retailers'}
          </p>
        </div>

        <div className="text-right">
          <span className="text-xs font-bold text-gray-500">
            {language === 'hi' ? 'कुल उत्पाद:' : 'Total Products:'}{' '}
            <strong className="text-gray-900">{total}</strong>
          </span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <SearchBar
        searchTerm={searchTerm}
        onSearchChange={handleSearchChange}
        selectedCategory={selectedCategory}
        onCategoryChange={handleCategoryChange}
        categories={categories}
        inStockOnly={inStockOnly}
        onInStockToggle={handleInStockToggle}
        language={language}
      />

      {/* Error Banner */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-2xl p-6 text-center my-6">
          <p className="font-semibold text-sm mb-3">{error}</p>
          <button
            onClick={fetchProducts}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl text-xs font-bold transition-colors"
          >
            {language === 'hi' ? 'पुनः प्रयास करें (Retry)' : 'Retry'}
          </button>
        </div>
      )}

      {/* Loading Skeletons */}
      {loading && !error && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5" data-testid="catalogue-skeleton">
          {[1, 2, 3, 4, 5, 6].map((idx) => (
            <div
              key={idx}
              className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm animate-pulse flex flex-col justify-between h-72"
            >
              <div>
                <div className="flex justify-between mb-4">
                  <div className="h-4 bg-gray-200 rounded w-20"></div>
                  <div className="h-4 bg-gray-200 rounded w-24"></div>
                </div>
                <div className="h-6 bg-gray-200 rounded w-3/4 mb-2"></div>
                <div className="h-3 bg-gray-100 rounded w-full mb-4"></div>
                <div className="h-16 bg-gray-100 rounded-xl mb-4"></div>
              </div>
              <div className="h-10 bg-gray-200 rounded-xl"></div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && products.length === 0 && (
        <div
          className="bg-white border border-gray-200 rounded-3xl p-12 text-center my-6 max-w-lg mx-auto shadow-sm"
          data-testid="catalogue-empty"
        >
          <div className="w-16 h-16 bg-gray-100 text-gray-400 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl">
            🔍
          </div>
          <h3 className="text-lg font-bold text-gray-900 mb-1">
            {language === 'hi' ? 'कोई उत्पाद नहीं मिला' : 'No Products Found'}
          </h3>
          <p className="text-xs text-gray-500 mb-6">
            {language === 'hi'
              ? 'आपके खोज या फ़िल्टर के अनुसार कोई उत्पाद उपलब्ध नहीं है।'
              : 'No products match your current search criteria or category filter.'}
          </p>
          <button
            onClick={handleResetFilters}
            className="px-5 py-2.5 bg-primary-600 hover:bg-primary-700 text-white rounded-xl text-xs font-bold transition-colors shadow-xs"
          >
            {language === 'hi' ? 'फ़िल्टर हटाएं (Reset Filters)' : 'Reset Filters'}
          </button>
        </div>
      )}

      {/* Product Grid */}
      {!loading && !error && products.length > 0 && (
        <div
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5"
          data-testid="product-grid"
        >
          {products.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              onSelect={setSelectedProduct}
              language={language}
            />
          ))}
        </div>
      )}

      {/* Pagination Bar */}
      {!loading && !error && totalPages > 1 && (
        <div className="mt-8 flex justify-between items-center bg-white border border-gray-200 rounded-2xl px-5 py-3 shadow-sm">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="px-3.5 py-1.5 border border-gray-300 rounded-xl text-xs font-bold text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            &larr; {language === 'hi' ? 'पिछला' : 'Previous'}
          </button>

          <span className="text-xs font-medium text-gray-600">
            {language === 'hi'
              ? `पृष्ठ ${page} / ${totalPages} (${total} उत्पाद)`
              : `Page ${page} of ${totalPages} (${total} products)`}
          </span>

          <button
            disabled={page >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            className="px-3.5 py-1.5 border border-gray-300 rounded-xl text-xs font-bold text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {language === 'hi' ? 'अगला' : 'Next'} &rarr;
          </button>
        </div>
      )}

      {/* Detail Modal */}
      <ProductDetailModal
        product={selectedProduct}
        onClose={() => setSelectedProduct(null)}
        language={language}
      />
    </div>
  );
};

export default ProductCataloguePage;
