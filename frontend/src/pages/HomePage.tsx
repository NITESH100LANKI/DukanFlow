import React, { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { fetchHealth, HealthResponse } from '../api/health';
import { Language } from '../components/LanguageToggle';

interface OutletContextType {
  language: Language;
}

export const HomePage: React.FC = () => {
  const { language } = useOutletContext<OutletContextType>();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    fetchHealth()
      .then((data) => {
        if (isMounted) {
          setHealth(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Failed to connect to backend API');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const content = {
    en: {
      heading: 'Welcome to DukaanFlow',
      subheading: 'Digitizing FMCG Retailer Ordering & Message Capture',
      scopeTitle: 'Phase 2 Foundation Initialized',
      scopeDesc:
        'FastAPI backend, React TypeScript frontend, PostgreSQL configuration, and Docker development container are configured and verified.',
      backendStatus: 'Backend API Status',
      dbStatus: 'Database Connection',
      version: 'Platform Version',
      statusOk: 'Operational',
      statusDegraded: 'Degraded',
      readyText: 'Ready for Phase 3: Authentication & Catalogue implementation.',
    },
    hi: {
      heading: 'दुकानफ्लो में आपका स्वागत है',
      subheading: 'एफएमसीजी रिटेलर ऑर्डरिंग एवं मैसेज कैप्चर डिजिटाइजेशन',
      scopeTitle: 'फेज 2 फाउंडेशन सफलतापूर्वक आरंभ',
      scopeDesc:
        'फास्टएपीआई बैकएंड, रिएक्ट टाइपस्क्रिप्ट फ्रंटएंड, पोस्टग्रेसक्यूएल कॉन्फ़िगरेशन और डॉकर डेवलपमेंट कंटेनर सत्यापित हैं।',
      backendStatus: 'बैकएंड एपीआई स्थिति',
      dbStatus: 'डेटाबेस कनेक्शन',
      version: 'प्लेटफॉर्म संस्करण',
      statusOk: 'सक्रिय (ओके)',
      statusDegraded: 'आंशिक सक्रिय',
      readyText: 'फेज 3 (प्रमाणीकरण एवं कैटलॉग) के लिए तैयार।',
    },
  };

  const t = content[language] || content.en;

  return (
    <div className="space-y-6">
      {/* Hero Banner */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 sm:p-8 shadow-sm">
        <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
          {t.heading}
        </h1>
        <p className="mt-2 text-base sm:text-lg text-gray-600">
          {t.subheading}
        </p>

        <div className="mt-6 p-4 rounded-lg bg-primary-50 border border-primary-100">
          <h2 className="text-sm font-bold uppercase tracking-wider text-primary-800">
            {t.scopeTitle}
          </h2>
          <p className="mt-1 text-sm text-primary-900">{t.scopeDesc}</p>
        </div>
      </div>

      {/* Health Diagnostic Card */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
        <h3 className="text-lg font-bold text-gray-900 mb-4">
          {t.backendStatus}
        </h3>

        {loading ? (
          <div className="flex items-center space-x-2 text-gray-500 py-2">
            <span className="inline-block w-4 h-4 border-2 border-primary-600 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm">Connecting to backend...</span>
          </div>
        ) : error ? (
          <div className="rounded-lg bg-amber-50 border border-amber-200 p-4 text-amber-900 text-sm">
            <p className="font-semibold">Backend Status Notice:</p>
            <p className="mt-1">{error}</p>
            <p className="mt-2 text-xs text-amber-700">
              Note: Start the FastAPI server on port 8000 to enable live connectivity.
            </p>
          </div>
        ) : health ? (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-4 rounded-lg bg-gray-50 border border-gray-200">
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                API Status
              </span>
              <p className="mt-1 text-lg font-bold text-green-700">
                {health.status === 'ok' ? t.statusOk : t.statusDegraded}
              </p>
            </div>

            <div className="p-4 rounded-lg bg-gray-50 border border-gray-200">
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t.dbStatus}
              </span>
              <p
                className={`mt-1 text-lg font-bold ${
                  health.db === 'connected' ? 'text-green-700' : 'text-amber-600'
                }`}
              >
                {health.db}
              </p>
            </div>

            <div className="p-4 rounded-lg bg-gray-50 border border-gray-200">
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t.version}
              </span>
              <p className="mt-1 text-lg font-bold text-gray-800">
                v{health.version}
              </p>
            </div>
          </div>
        ) : null}

        <p className="mt-6 text-xs text-gray-500">{t.readyText}</p>
      </div>
    </div>
  );
};

export default HomePage;

