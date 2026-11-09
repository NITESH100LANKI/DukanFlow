import React from 'react';
import { Link } from 'react-router-dom';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="text-center py-12">
      <h2 className="text-4xl font-extrabold text-gray-900 tracking-tight">404</h2>
      <p className="mt-2 text-base text-gray-600">Page not found</p>
      <div className="mt-6">
        <Link
          to="/"
          className="touch-target inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700"
        >
          Return Home
        </Link>
      </div>
    </div>
  );
};

export default NotFoundPage;

