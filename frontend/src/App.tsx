import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { CartProvider } from './context/CartContext';
import RootLayout from './layouts/RootLayout';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import RetailerDashboard from './pages/RetailerDashboard';
import DeskDashboard from './pages/DeskDashboard';
import ProductCataloguePage from './pages/ProductCataloguePage';
import CartPage from './pages/CartPage';
import NotFoundPage from './pages/NotFoundPage';
import ProtectedRoute from './components/ProtectedRoute';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <CartProvider>
          <Routes>
            <Route path="/" element={<RootLayout />}>
              <Route index element={<HomePage />} />
              <Route path="login" element={<LoginPage />} />
              <Route
                path="retailer/dashboard"
                element={
                  <ProtectedRoute allowedRoles={['retailer']}>
                    <RetailerDashboard />
                  </ProtectedRoute>
                }
              />
              <Route
                path="retailer/catalogue"
                element={
                  <ProtectedRoute allowedRoles={['retailer', 'order_desk']}>
                    <ProductCataloguePage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="catalogue"
                element={
                  <ProtectedRoute allowedRoles={['retailer', 'order_desk']}>
                    <ProductCataloguePage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="retailer/cart"
                element={
                  <ProtectedRoute allowedRoles={['retailer']}>
                    <CartPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="cart"
                element={
                  <ProtectedRoute allowedRoles={['retailer']}>
                    <CartPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="desk/dashboard"
                element={
                  <ProtectedRoute allowedRoles={['order_desk']}>
                    <DeskDashboard />
                  </ProtectedRoute>
                }
              />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </CartProvider>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
