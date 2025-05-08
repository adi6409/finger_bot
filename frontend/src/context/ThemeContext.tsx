'use client';

import React, { createContext, useContext, useState, useMemo, ReactNode, useEffect } from 'react';

/**
 * Theme mode type definition
 */
export type ThemeMode = 'light' | 'dark';

/**
 * Theme context interface
 */
interface ThemeContextType {
  mode: ThemeMode;
  toggleMode: () => void;
}

// Create the context with undefined as default value
const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

/**
 * Hook to use the theme context
 * @returns The theme context
 * @throws Error if used outside of ThemeContextProvider
 */
export const useThemeContext = () => {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useThemeContext must be used within a ThemeContextProvider');
  }
  return context;
};

/**
 * Theme context provider component
 * Manages theme state and provides theme context to children
 */
export const ThemeContextProvider = ({ children }: { children: ReactNode }) => {
  const [mode, setMode] = useState<ThemeMode>('light');

  // Effect to read initial theme from localStorage/system preference
  useEffect(() => {
    // Only run on client side
    if (typeof window !== 'undefined') {
      const savedTheme = localStorage.getItem("theme") as ThemeMode | null;
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      const initialMode = savedTheme || (prefersDark ? 'dark' : 'light');
      setMode(initialMode);
    }
  }, []);

  // Effect to update localStorage and document class when mode changes
  useEffect(() => {
    if (typeof window !== 'undefined') {
      // Save to localStorage
      localStorage.setItem("theme", mode);
      
      // Update document class for CSS selectors
      if (mode === 'dark') {
        document.documentElement.classList.add("dark");
      } else {
        document.documentElement.classList.remove("dark");
      }
    }
  }, [mode]);

  // Toggle between light and dark mode
  const toggleMode = () => {
    setMode((prevMode) => (prevMode === 'light' ? 'dark' : 'light'));
  };

  // Memoize the context value to prevent unnecessary re-renders
  const value = useMemo(() => ({ mode, toggleMode }), [mode]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};
