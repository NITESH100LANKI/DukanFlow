import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const RetailerDashboard: React.FC = () => {
  const { user, logout } = useAuth();

  return (
    <div className="max-w-4xl mx-auto py-6">
      <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm mb-6">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider bg-primary-100 text-primary-700 px-2.5 py-1 rounded-full">
              Retailer Account (किराना दुकान)
            </span>
            <h1 className="text-2xl font-black text-gray-900 mt-2">{user?.name}</h1>
            <p className="text-sm text-gray-500 font-medium">Registered Mobile: +91 {user?.identifier}</p>
          </div>
          <button
            onClick={logout}
            className="px-4 py-2 border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-xl font-semibold text-sm transition-colors"
          >
            Log Out (लॉग आउट)
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-start mb-2">
              <h2 className="text-lg font-bold text-gray-900">Catalogue & Ordering</h2>
              <span className="inline-block text-[11px] font-bold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full">
                Phase 4 Ready
              </span>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Browse wholesale FMCG products, active schemes (Buy 10 Get 1 Free, 3% discount), and case pricing.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              to="/retailer/catalogue"
              className="flex-1 py-2.5 px-3 bg-primary-600 hover:bg-primary-700 text-white rounded-xl text-xs font-bold transition-colors text-center shadow-xs"
            >
              Browse Catalogue &rarr;
            </Link>
            <Link
              to="/retailer/cart"
              className="py-2.5 px-3 bg-primary-50 hover:bg-primary-100 text-primary-700 border border-primary-200 rounded-xl text-xs font-bold transition-colors text-center"
            >
              🛒 Cart
            </Link>
            <Link
              to="/orders"
              className="py-2.5 px-3 bg-gray-100 hover:bg-gray-200 text-gray-800 rounded-xl text-xs font-bold transition-colors text-center"
            >
              📦 My Orders
            </Link>
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-start mb-2">
              <h2 className="text-lg font-bold text-gray-900">AI Order Capture (स्मार्ट ऑर्डर)</h2>
              <span className="inline-block text-[11px] font-bold bg-purple-100 text-purple-800 px-2 py-0.5 rounded-full">
                Phase 7 Active
              </span>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Paste or type wholesale orders in Hindi, English, or Hinglish. Gemini extracts an editable draft for your confirmation.
            </p>
          </div>
          <Link
            to="/retailer/ai-capture"
            className="w-full py-2.5 px-3 bg-purple-600 hover:bg-purple-700 text-white rounded-xl text-xs font-bold transition-colors text-center shadow-xs"
          >
            Start AI Order (स्मार्ट ऑर्डर बनाएं) &rarr;
          </Link>
        </div>
      </div>
    </div>
  );
};

export default RetailerDashboard;

