import React from 'react';
import { Scheme } from '../../api/catalogue';

interface SchemeBadgeProps {
  scheme?: Scheme | null;
  language?: 'en' | 'hi';
}

export const SchemeBadge: React.FC<SchemeBadgeProps> = ({ scheme, language = 'en' }) => {
  if (!scheme || !scheme.is_active) {
    return null;
  }

  const isBuyNGetM = scheme.scheme_type === 'BUY_N_GET_M_FREE';

  return (
    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-bold bg-primary-50 text-primary-800 border border-primary-200 shadow-xs">
      <span className="text-sm">{isBuyNGetM ? '🎁' : '🏷️'}</span>
      <span>
        {isBuyNGetM ? (
          language === 'hi' ? (
            `स्कीम: ${scheme.min_qty} पेटी पर ${scheme.free_qty || 1} पेटी मुफ्त`
          ) : (
            `Scheme: Buy ${scheme.min_qty} Cases Get ${scheme.free_qty || 1} Free`
          )
        ) : (
          language === 'hi' ? (
            `स्कीम: ${scheme.min_qty}+ पेटी पर ${scheme.discount_pct}% छूट`
          ) : (
            `Scheme: ${scheme.discount_pct}% discount on ${scheme.min_qty}+ cases`
          )
        )}
      </span>
    </div>
  );
};

export default SchemeBadge;

