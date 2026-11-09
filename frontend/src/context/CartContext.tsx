import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { Cart, getCart, addCartLine, updateCartLineQty, deleteCartLine, clearCartApi } from '../api/cart';
import { useAuth } from './AuthContext';

interface CartContextType {
  cart: Cart | null;
  loading: boolean;
  error: string | null;
  addToCart: (productId: string, qtyCases: number) => Promise<void>;
  updateQty: (lineId: string, qtyCases: number) => Promise<void>;
  removeLine: (lineId: string) => Promise<void>;
  clearCart: () => Promise<void>;
  refreshCart: () => Promise<void>;
  totalCasesCount: number;
  itemCount: number;
}

const CartContext = createContext<CartContextType | undefined>(undefined);

export const CartProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, isAuthenticated } = useAuth();
  const [cart, setCart] = useState<Cart | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const isRetailer = isAuthenticated && user?.role === 'retailer';

  const refreshCart = useCallback(async () => {
    if (!isRetailer) {
      setCart(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await getCart();
      setCart(data);
    } catch (err: any) {
      // If 401 or not logged in yet, ignore
      if (err.response?.status !== 401) {
        console.error('Failed to load cart', err);
        setError(err.response?.data?.detail || 'Failed to load shopping cart');
      }
    } finally {
      setLoading(false);
    }
  }, [isRetailer]);

  useEffect(() => {
    refreshCart();
  }, [refreshCart]);

  const addToCart = async (productId: string, qtyCases: number) => {
    setError(null);
    try {
      const updatedCart = await addCartLine(productId, qtyCases);
      setCart(updatedCart);
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to add product to cart';
      setError(msg);
      throw new Error(msg);
    }
  };

  const updateQty = async (lineId: string, qtyCases: number) => {
    setError(null);
    try {
      const updatedCart = await updateCartLineQty(lineId, qtyCases);
      setCart(updatedCart);
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to update quantity';
      setError(msg);
      throw new Error(msg);
    }
  };

  const removeLine = async (lineId: string) => {
    setError(null);
    try {
      const updatedCart = await deleteCartLine(lineId);
      setCart(updatedCart);
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to remove product from cart';
      setError(msg);
      throw new Error(msg);
    }
  };

  const clearCart = async () => {
    setError(null);
    try {
      const updatedCart = await clearCartApi();
      setCart(updatedCart);
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to clear cart';
      setError(msg);
      throw new Error(msg);
    }
  };

  const totalCasesCount = cart?.summary?.total_cases_paid || 0;
  const itemCount = cart?.lines?.length || 0;

  return (
    <CartContext.Provider
      value={{
        cart,
        loading,
        error,
        addToCart,
        updateQty,
        removeLine,
        clearCart,
        refreshCart,
        totalCasesCount,
        itemCount,
      }}
    >
      {children}
    </CartContext.Provider>
  );
};

export const useCart = (): CartContextType => {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error('useCart must be used within a CartProvider');
  }
  return context;
};

export default CartContext;
