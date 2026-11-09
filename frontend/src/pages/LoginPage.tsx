import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { requestOtp } from '../api/auth';

export const LoginPage: React.FC = () => {
  const { loginWithOtp, loginWithPassword } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Tab: 'retailer' | 'desk'
  const [tab, setTab] = useState<'retailer' | 'desk'>('retailer');

  // Retailer OTP state
  const [mobile, setMobile] = useState('');
  const [otp, setOtp] = useState('');
  const [otpSent, setOtpSent] = useState(false);

  // Order Desk state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as any)?.from?.pathname || (tab === 'retailer' ? '/retailer/dashboard' : '/desk/dashboard');

  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!mobile || mobile.length < 10) {
      setError('Please enter a valid 10-digit mobile number');
      return;
    }
    setLoading(true);
    try {
      await requestOtp(mobile);
      setOtpSent(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to send OTP. Please check the mobile number.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!otp || otp.length < 4) {
      setError('Please enter the verification code');
      return;
    }
    setLoading(true);
    try {
      await loginWithOtp(mobile, otp);
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Verification failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleDeskLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await loginWithPassword(email, password);
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed. Please check your email and password.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto my-8 p-6 bg-white border border-gray-200 rounded-2xl shadow-sm">
      <div className="text-center mb-6">
        <h2 className="text-2xl font-black text-gray-900 tracking-tight">Login to DukaanFlow</h2>
        <p className="text-sm text-gray-500 mt-1">एफएमसीजी रिटेलर ऑर्डरिंग प्लेटफॉर्म</p>
      </div>

      {/* Role Toggle Tabs */}
      <div className="flex bg-gray-100 p-1 rounded-xl mb-6">
        <button
          type="button"
          onClick={() => {
            setTab('retailer');
            setError(null);
          }}
          className={`flex-1 py-2 text-sm font-semibold rounded-lg transition-all ${
            tab === 'retailer' ? 'bg-white text-primary-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          Retailer (किराना)
        </button>
        <button
          type="button"
          onClick={() => {
            setTab('desk');
            setError(null);
          }}
          className={`flex-1 py-2 text-sm font-semibold rounded-lg transition-all ${
            tab === 'desk' ? 'bg-white text-primary-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          Order Desk (स्टाफ)
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl">
          {error}
        </div>
      )}

      {/* Retailer OTP Form */}
      {tab === 'retailer' && (
        <div>
          {!otpSent ? (
            <form onSubmit={handleSendOtp} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
                  Mobile Number (मोबाइल नंबर)
                </label>
                <div className="relative">
                  <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-gray-400 text-sm font-semibold">
                    +91
                  </span>
                  <input
                    type="tel"
                    value={mobile}
                    onChange={(e) => setMobile(e.target.value.replace(/\D/g, '').slice(0, 10))}
                    placeholder="9876543210"
                    className="w-full pl-12 pr-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-gray-900 font-medium"
                    required
                  />
                </div>
              </div>

              <div className="bg-primary-50 border border-primary-200 text-primary-800 text-xs p-2.5 rounded-xl">
                💡 <strong>Demo Mode:</strong> Use registered mobile or test seeded retailer. Demo OTP is <strong>123456</strong>.
              </div>

              <button
                type="submit"
                disabled={loading || mobile.length < 10}
                className="w-full py-2.5 px-4 bg-primary-600 hover:bg-primary-700 disabled:bg-gray-300 text-white font-bold rounded-xl shadow-sm transition-colors"
              >
                {loading ? 'Sending OTP...' : 'Send OTP (ओटीपी भेजें)'}
              </button>
            </form>
          ) : (
            <form onSubmit={handleVerifyOtp} className="space-y-4">
              <div className="text-sm text-gray-600 mb-1">
                Enter the 6-digit code sent to <strong>+91 {mobile}</strong>
              </div>

              <div>
                <input
                  type="text"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="123456"
                  className="w-full px-4 py-2.5 text-center tracking-widest text-xl font-bold border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  required
                />
              </div>

              <button
                type="submit"
                disabled={loading || otp.length < 4}
                className="w-full py-2.5 px-4 bg-primary-600 hover:bg-primary-700 disabled:bg-gray-300 text-white font-bold rounded-xl shadow-sm transition-colors"
              >
                {loading ? 'Verifying...' : 'Verify & Login (सत्यापित करें)'}
              </button>

              <button
                type="button"
                onClick={() => {
                  setOtpSent(false);
                  setOtp('');
                  setError(null);
                }}
                className="w-full text-center text-xs text-primary-600 hover:underline font-semibold"
              >
                Change mobile number
              </button>
            </form>
          )}
        </div>
      )}

      {/* Order Desk Password Form */}
      {tab === 'desk' && (
        <form onSubmit={handleDeskLogin} className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
              Email Address (ईमेल)
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="desk@dukaanflow.in"
              className="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-gray-700 uppercase mb-1">
              Password (पासवर्ड)
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-4 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading || !email || !password}
            className="w-full py-2.5 px-4 bg-primary-600 hover:bg-primary-700 disabled:bg-gray-300 text-white font-bold rounded-xl shadow-sm transition-colors"
          >
            {loading ? 'Logging in...' : 'Sign In as Order Desk'}
          </button>
        </form>
      )}
    </div>
  );
};

export default LoginPage;

