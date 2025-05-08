'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import useAuthStore from '@/store/authStore';
import { Box, CircularProgress } from '@mui/material';

/**
 * Protected layout component that ensures users are authenticated
 * Redirects to login page if not authenticated
 */
export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const isLoggedIn = useAuthStore((state) => state.isLoggedIn);
  const router = useRouter();
  
  // State to track client-side hydration
  const [hydrated, setHydrated] = useState(false);
  
  // Handle Zustand hydration
  useEffect(() => {
    setHydrated(true);
  }, []);
  
  // Authentication check and redirect
  useEffect(() => {
    if (hydrated && !isLoggedIn) {
      router.replace('/login');
    }
  }, [hydrated, isLoggedIn, router]);
  
  // Show loading state during hydration
  if (!hydrated) {
    return (
      <Box 
        sx={{ 
          display: 'flex', 
          justifyContent: 'center', 
          alignItems: 'center', 
          height: '100vh' 
        }}
      >
        <CircularProgress />
      </Box>
    );
  }
  
  // Don't render protected content if not logged in
  if (!isLoggedIn) {
    return null;
  }
  
  // Render children if authenticated
  return <>{children}</>;
}
