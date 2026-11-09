import React from 'react';
import { useAuth } from '../context/AuthContext';

export const DeskDashboard: React.FC = () => {
  const { user, logout } = useAuth();

  return (
    <div className="max-w-4xl mx-auto py-6">
      <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm mb-6">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider bg-purple-100 text-purple-700 px-2.5 py-1 rounded-full">
              Order Desk Manager (ऑर्डर डेस्क)
            </span>
            <h1 className="text-2xl font-black text-gray-900 mt-2">{user?.name}</h1>
            <p className="text-sm text-gray-500 font-medium">Email: {user?.identifier}</p>
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
        <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
          <h2 className="text-lg font-bold text-gray-900 mb-2">Order Review & Approval</h2>
          <p className="text-sm text-gray-600 mb-4">
            Review submitted kirana orders, verify inventory, modify line quantities, and approve.
          </p>
          <span className="inline-block text-xs font-bold bg-amber-100 text-amber-800 px-2 py-1 rounded-md">
            Order Review Workflow
          </span>
        </div>

        <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
          <h2 className="text-lg font-bold text-gray-900 mb-2">Tally CSV Export</h2>
          <p className="text-sm text-gray-600 mb-4">
            Generate and download Tally XML/CSV exports for approved orders.
          </p>
          <span className="inline-block text-xs font-bold bg-amber-100 text-amber-800 px-2 py-1 rounded-md">
            ERP Integration
          </span>
        </div>
      </div>
    </div>
  );
};

export default DeskDashboard;

