import React from 'react';

export type Language = 'en' | 'hi';

interface LanguageToggleProps {
  currentLanguage: Language;
  onToggle: (lang: Language) => void;
}

export const LanguageToggle: React.FC<LanguageToggleProps> = ({
  currentLanguage,
  onToggle,
}) => {
  return (
    <div className="inline-flex rounded-lg border border-gray-300 bg-white p-1 shadow-sm">
      <button
        type="button"
        onClick={() => onToggle('en')}
        className={`touch-target px-4 py-2 text-sm font-semibold rounded-md transition-colors ${
          currentLanguage === 'en'
            ? 'bg-primary-600 text-white shadow'
            : 'text-gray-700 hover:text-gray-900 hover:bg-gray-50'
        }`}
        aria-pressed={currentLanguage === 'en'}
      >
        English
      </button>
      <button
        type="button"
        onClick={() => onToggle('hi')}
        className={`touch-target px-4 py-2 text-sm font-semibold rounded-md transition-colors ${
          currentLanguage === 'hi'
            ? 'bg-primary-600 text-white shadow'
            : 'text-gray-700 hover:text-gray-900 hover:bg-gray-50'
        }`}
        aria-pressed={currentLanguage === 'hi'}
      >
        हिंदी
      </button>
    </div>
  );
};

export default LanguageToggle;

