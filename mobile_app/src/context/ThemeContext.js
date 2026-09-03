import React, { createContext, useContext, useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const EAGLE_COLORS = {
  gold: '#FFD700',
  darkGold: '#B8860B',
  fire: '#DC2626',
  darkRed: '#991B1B',
  steel: '#4682B4',
  dark: '#0f172a',
  darker: '#020617',
  card: '#1e293b',
  text: '#f8fafc',
  muted: '#94a3b8',
};

const THEME_KEY = '@eagle_theme';

const THEMES = {
  dark: {
    ...EAGLE_COLORS,
    name: 'dark',
    primary: EAGLE_COLORS.dark,
    secondary: EAGLE_COLORS.darker,
    accent: EAGLE_COLORS.gold,
  },
  golden: {
    ...EAGLE_COLORS,
    name: 'golden',
    primary: '#B8860B',
    secondary: '#DAA520',
    accent: '#FFD700',
    dark: '#1a1400',
    darker: '#0d0a00',
    card: '#2d2000',
  },
  red: {
    ...EAGLE_COLORS,
    name: 'red',
    primary: '#7F1D1D',
    secondary: '#991B1B',
    accent: '#EF4444',
    dark: '#1a0505',
    darker: '#0d0202',
    card: '#2d0a0a',
  },
};

const ThemeContext = createContext({
  theme: THEMES.dark,
  themeName: 'dark',
  setTheme: () => {},
});

export const ThemeProvider = ({ children }) => {
  const [themeName, setThemeName] = useState('dark');

  useEffect(() => {
    loadTheme();
  }, []);

  const loadTheme = async () => {
    try {
      const stored = await AsyncStorage.getItem(THEME_KEY);
      if (stored && THEMES[stored]) {
        setThemeName(stored);
      }
    } catch (error) {
      console.log('Theme load error:', error);
    }
  };

  const setTheme = async (name) => {
    try {
      await AsyncStorage.setItem(THEME_KEY, name);
      setThemeName(name);
    } catch (error) {
      console.log('Theme save error:', error);
    }
  };

  const theme = THEMES[themeName] || THEMES.dark;

  return (
    <ThemeContext.Provider value={{ theme, themeName, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => useContext(ThemeContext);

export default ThemeContext;
