'use client';

import * as React from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import NextAppDirEmotionCacheProvider from '@/components/EmotionCache'; // Use alias path
import { ThemeContextProvider, useThemeContext } from '@/context/ThemeContext'; // Import context

// Define basic light and dark palettes (can be customized further)
const lightTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2', // Example blue
    },
    secondary: {
      main: '#dc004e', // Example pink
    },
    background: {
      default: '#f3f4f6', // Light gray background
      paper: '#ffffff',   // White paper background
    },
  },
});

const darkTheme = createTheme({
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

// Inner component to access context
function ThemeSetter({ children }: { children: React.ReactNode }) {
  const { mode } = useThemeContext();
  const theme = mode === 'dark' ? darkTheme : lightTheme;

  return (
     <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
  )
}


export default function ThemeRegistry({ children }: { children: React.ReactNode }) {
  return (
    <NextAppDirEmotionCacheProvider options={{ key: 'mui' }}>
      {/* Wrap with the context provider */}
      <ThemeContextProvider>
         {/* Use the inner component to apply the theme based on context */}
        <ThemeSetter>
          {children}
        </ThemeSetter>
      </ThemeContextProvider>
    </NextAppDirEmotionCacheProvider>
  );
}
