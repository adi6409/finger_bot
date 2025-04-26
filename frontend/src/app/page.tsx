'use client'; // Mark as Client Component because it uses hooks (useAuthStore)

import React from 'react';
import useAuthStore from '@/store/authStore'; // Use alias

// Import MUI components
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Link from '@mui/material/Link'; // Use MUI Link for consistency
import NextLink from 'next/link'; // Use NextLink for routing

const HomePage: React.FC = () => {
  const { isLoggedIn, user } = useAuthStore(); // Get auth state

  // Handle Zustand hydration for SSR/SSG in Next.js
  const [isClient, setIsClient] = React.useState(false);
  React.useEffect(() => {
    setIsClient(true);
  }, []);

  if (!isClient) {
    // Render nothing or a loading state on the server/initial render
    return null;
  }

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '60vh', // Keep minimum height
        width: '100%',
      }}
    >
      <Card sx={{ maxWidth: 450, width: '100%', p: 2 }}> {/* p adds padding */}
        <CardContent>
          <Typography variant="h5" component="h2" gutterBottom color="primary">
            Welcome to Finger Bot Control
          </Typography>
          {isLoggedIn && user ? (
            <Typography variant="body1" color="text.secondary">
              Hello, <Typography component="span" fontWeight="fontWeightMedium">{user.email}</Typography>!<br />
              Use the navigation above to manage your devices and schedules.
            </Typography>
          ) : (
            <Typography variant="body1" color="text.secondary">
              Please{' '}
              <Link component={NextLink} href="/login" passHref underline="hover">
                 log in
              </Link>
              {' '}or{' '}
              <Link component={NextLink} href="/register" passHref underline="hover">
                 register
              </Link>
              {' '}to manage your devices.
            </Typography>
          )}
          {/* Add more dashboard elements here later */}
        </CardContent>
      </Card>
    </Box>
  );
};

export default HomePage;
