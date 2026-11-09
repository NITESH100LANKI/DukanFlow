import React from 'react';

interface StockStatusBadgeProps {
  status: 'in_stock' | 'low_stock' | 'out_of_stock';
  stockCases: number;
  language?: 'en' | 'hi';
}

export const StockStatusBadge: React.FC<StockStatusBadgeProps> = ({
  status,
  stockCases,
  language = 'en',
}) => {
  if (status === 'out_of_stock' || stockCases <= 0) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-gray-100 text-gray-600 border border-gray-300">
        <span className="w-2 h-2 rounded-full bg-gray-400"></span>
        {language === 'hi' ? 'स्टॉक समाप्त (0 पेटी)' : 'Out of Stock (0 cases)'}
      </span>
    );
  }

  if (status === 'low_stock' || stockCases < 10) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-800 border border-amber-200">
        <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse"></span>
        {language === 'hi' ? `सीमित स्टॉक (${stockCases} पेटी शेष)` : `Low Stock (${stockCases} cases left)`}
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
      <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
      {language === 'hi' ? `उपलब्ध (${stockCases} पेटी)` : `In Stock (${stockCases} cases)`}
    </span>
  );
};

export default StockStatusBadge;
