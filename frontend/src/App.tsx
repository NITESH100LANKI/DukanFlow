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
import OrdersPage from './pages/retailer/OrdersPage';
import OrderDetailPage from './pages/retailer/OrderDetailPage';
import DeskOrderQueuePage from './pages/desk/DeskOrderQueuePage';
import DeskOrderDetailPage from './pages/desk/DeskOrderDetailPage';
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
                path="orders"
                element={
                  <ProtectedRoute allowedRoles={['retailer']}>
                    <OrdersPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="orders/:id"
                element={
                  <ProtectedRoute allowedRoles={['retailer', 'order_desk']}>
                    <OrderDetailPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="desk/orders"
                element={
                  <ProtectedRoute allowedRoles={['order_desk']}>
                    <DeskOrderQueuePage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="desk/orders/:id"
                element={
                  <ProtectedRoute allowedRoles={['order_desk']}>
                    <DeskOrderDetailPage />
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
