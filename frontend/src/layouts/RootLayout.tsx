import React, { useState } from 'react';
import { Outlet, Link } from 'react-router-dom';
import { LanguageToggle, Language } from '../components/LanguageToggle';
import { useAuth } from '../context/AuthContext';
import { useCart } from '../context/CartContext';

export const RootLayout: React.FC = () => {
  const [language, setLanguage] = useState<Language>('en');
  const { user, isAuthenticated, logout } = useAuth();
  const { totalCasesCount } = useCart();

  const titles = {
    en: {
      appName: 'DukaanFlow',
      tagline: 'FMCG Retailer Ordering Platform',
      badge: 'Phase 2 Initialized',
      login: 'Sign In',
      logout: 'Logout',
      dashboard: 'Dashboard',
    },
    hi: {
      appName: 'दुकानफ्लो',
      tagline: 'एफएमसीजी रिटेलर ऑर्डरिंग प्लेटफॉर्म',
      badge: 'फेज 2 आरंभ',
      login: 'लॉग इन',
      logout: 'लॉग आउट',
      dashboard: 'डैशबोर्ड',
    },
  };

  const t = titles[language];
  const dashboardPath = user?.role === 'retailer' ? '/retailer/dashboard' : '/desk/dashboard';

  return (
    <div className="min-h-screen flex flex-col bg-gray-50 text-gray-900">
      {/* Top Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-3">
              <Link to="/" className="flex items-center space-x-2 touch-target">
                <span className="text-2xl font-black text-primary-600 tracking-tight">
                  {t.appName}
                </span>
                <span className="hidden sm:inline-block text-xs uppercase px-2 py-0.5 rounded bg-primary-100 text-primary-700 font-bold tracking-wider">
                  {t.badge}
                </span>
              </Link>
            </div>

            <div className="flex items-center space-x-4">
              {isAuthenticated && user ? (
                <div className="flex items-center space-x-3">
                  <Link
                    to="/retailer/catalogue"
                    className="text-xs font-bold text-gray-700 hover:text-primary-600 transition-colors"
                  >
                    {language === 'hi' ? 'कैटलॉग' : 'Catalogue'}
                  </Link>

                  {user.role === 'retailer' && (
                    <>
                      <Link
                        to="/retailer/cart"
                        className="relative inline-flex items-center gap-1 text-xs font-bold text-primary-700 bg-primary-50 hover:bg-primary-100 px-3 py-1 rounded-lg transition-colors"
                        title="Shopping Cart"
                      >
                        <span>🛒</span>
                        <span>{language === 'hi' ? 'कार्ट' : 'Cart'}</span>
                        {totalCasesCount > 0 && (
                          <span className="ml-1 inline-flex items-center justify-center px-1.5 py-0.5 text-[10px] font-black rounded-full bg-primary-600 text-white">
                            {totalCasesCount}
                          </span>
                        )}
                      </Link>
                      <Link
                        to="/orders"
                        className="text-xs font-bold text-gray-700 hover:text-primary-600 transition-colors"
                      >
                        {language === 'hi' ? 'मेरे ऑर्डर्स' : 'My Orders'}
                      </Link>
                    </>
                  )}

                  {user.role === 'order_desk' && (
                    <Link
                      to="/desk/orders"
                      className="text-xs font-bold text-primary-700 bg-primary-50 hover:bg-primary-100 px-3 py-1 rounded-lg transition-colors"
                    >
                      {language === 'hi' ? 'ऑर्डर कतार' : 'Order Queue'}
                    </Link>
                  )}

                  <Link
                    to={dashboardPath}
                    className="text-xs font-bold text-gray-700 hover:text-primary-600"
                  >
                    {user.name} ({user.role === 'retailer' ? 'किराना' : 'डेस्क'})
                  </Link>
                  <button
                    onClick={logout}
                    className="text-xs text-red-600 hover:text-red-700 font-semibold"
                  >
                    {t.logout}
                  </button>
                </div>
              ) : (
                <Link
                  to="/login"
                  className="px-3 py-1.5 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-xs font-bold transition-colors"
                >
                  {t.login}
                </Link>
              )}

              <LanguageToggle
                currentLanguage={language}
                onToggle={setLanguage}
              />
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Outlet context={{ language }} />
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 py-4 text-center text-xs text-gray-500">
        <p>DukaanFlow — Jabalpur FMCG Distribution Network &copy; 2026</p>
      </footer>
    </div>
  );
};

export default RootLayout;
