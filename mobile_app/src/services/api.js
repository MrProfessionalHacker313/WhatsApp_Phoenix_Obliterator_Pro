import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE_URL_KEY = '@eagle_api_base_url';
const PROXY_KEY = '@eagle_proxy';

const getBaseUrl = async () => {
  try {
    const stored = await AsyncStorage.getItem(API_BASE_URL_KEY);
    if (stored) return stored;
  } catch (error) {
    console.log('Failed to load API base URL', error);
  }
  return 'http://localhost:5000/api';
};

const getProxy = async () => {
  try {
    const stored = await AsyncStorage.getItem(PROXY_KEY);
    return stored || null;
  } catch (error) {
    return null;
  }
};

const api = {
  async request(endpoint, options = {}) {
    const baseUrl = await getBaseUrl();
    const url = `${baseUrl}${endpoint}`;
    const proxy = await getProxy();

    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    if (proxy) {
      // Note: React Native fetch doesn't support proxy directly.
      // In a production app, you would configure proxy at the native level
      // or use a networking library like axios with a proxy agent.
      console.log(`Proxy configured: ${proxy}`);
    }

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        const errorText = await response.text();
        let errorMessage = `HTTP ${response.status}`;
        try {
          const errorJson = JSON.parse(errorText);
          errorMessage = errorJson.error || errorMessage;
        } catch {
          errorMessage = errorText || errorMessage;
        }
        throw new Error(errorMessage);
      }

      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return await response.json();
      }
      return await response.text();
    } catch (error) {
      if (error.message.includes('Network request failed') || error.message.includes('fetch')) {
        throw new Error('Cannot connect to server. Check your network and server address.');
      }
      throw error;
    }
  },

  getStats: async () => {
    return api.request('/stats');
  },

  getPlans: async () => {
    return api.request('/plans');
  },

  executeOperation: async (data) => {
    return api.request('/operation', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  verifyLicense: async (licenseKey) => {
    return api.request('/verify-license', {
      method: 'POST',
      body: JSON.stringify({ key: licenseKey }),
    });
  },

  activateLicense: async (licenseKey) => {
    return api.request('/activate-license', {
      method: 'POST',
      body: JSON.stringify({ key: licenseKey }),
    });
  },

  createStripeCheckoutSession: async (data) => {
    return api.request('/create-checkout-session', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  createPayPalOrder: async (data) => {
    return api.request('/create-paypal-order', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  capturePayPalOrder: async (orderId, plan) => {
    return api.request('/capture-paypal-order', {
      method: 'POST',
      body: JSON.stringify({ order_id: orderId, plan }),
    });
  },
};

export const setBaseUrl = async (url) => {
  try {
    await AsyncStorage.setItem(API_BASE_URL_KEY, url);
  } catch (error) {
    console.log('Failed to save API base URL', error);
  }
};

export const setProxy = async (proxyUrl) => {
  try {
    if (proxyUrl) {
      await AsyncStorage.setItem(PROXY_KEY, proxyUrl);
    } else {
      await AsyncStorage.removeItem(PROXY_KEY);
    }
  } catch (error) {
    console.log('Failed to save proxy', error);
  }
};

export default api;
