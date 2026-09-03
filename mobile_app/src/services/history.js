import AsyncStorage from '@react-native-async-storage/async-storage';

const HISTORY_KEY = '@eagle_operation_history';

export const addToHistory = async (operation) => {
  try {
    const stored = await AsyncStorage.getItem(HISTORY_KEY);
    const history = stored ? JSON.parse(stored) : [];

    const newEntry = {
      id: Date.now(),
      timestamp: Date.now(),
      phone: operation.phone,
      action: operation.action,
      success: operation.success || false,
      message: operation.message || operation.error || 'No details',
      duration: operation.duration || 0,
    };

    const newHistory = [newEntry, ...history].slice(0, 100);
    await AsyncStorage.setItem(HISTORY_KEY, JSON.stringify(newHistory));
    return newEntry;
  } catch (error) {
    console.log('History save error:', error);
    return null;
  }
};

export const getHistory = async () => {
  try {
    const stored = await AsyncStorage.getItem(HISTORY_KEY);
    if (stored) {
      return JSON.parse(stored).sort((a, b) => b.timestamp - a.timestamp);
    }
    return [];
  } catch (error) {
    console.log('History load error:', error);
    return [];
  }
};

export const clearHistory = async () => {
  try {
    await AsyncStorage.removeItem(HISTORY_KEY);
  } catch (error) {
    console.log('History clear error:', error);
  }
};
