'use client';

import * as React from 'react';
import { ThemeProvider, createTheme, Theme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import NextAppDirEmotionCacheProvider from '@/components/EmotionCache';
import { ThemeContextProvider, useThemeContext, ThemeMode } from '@/context/ThemeContext';

/**
 * MUI theme definitions for light and dark modes
 */

// Light theme configuration
const lightTheme: Theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2', // Blue
    },
    secondary: {
      main: '#dc004e', // Pink
    },
    background: {
      default: '#f3f4f6', // Light gray background
      paper: '#ffffff',   // White paper background
    },
  },
});

// Dark theme configuration
const darkTheme: Theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#90caf9', // Lighter blue for dark mode
    },
    secondary: {
      main: '#f48fb1', // Lighter pink for dark mode
    },
    background: {
      default: '#111827', // Dark gray background
      paper: '#1f2937',   // Slightly lighter dark paper
    },
  },
});

/**
 * Get the appropriate theme based on the current mode
 * @param mode The current theme mode ('light' or 'dark')
 * @returns The corresponding MUI theme
 */
const getTheme = (mode: ThemeMode): Theme => {
  return mode === 'dark' ? darkTheme : lightTheme;
};

/**
 * Inner component that applies the MUI theme based on the current context
 */
function ThemeSetter({ children }: { children: React.ReactNode }) {
  const { mode } = useThemeContext();
  const theme = getTheme(mode);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  );
}

/**
 * Main ThemeRegistry component that sets up the emotion cache and theme context
 */
export default function ThemeRegistry({ children }: { children: React.ReactNode }) {
  return (
    <NextAppDirEmotionCacheProvider options={{ key: 'mui' }}>
      <ThemeContextProvider>
        <ThemeSetter>
          {children}
        </ThemeSetter>
      </ThemeContextProvider>
    </NextAppDirEmotionCacheProvider>
  );
}
