'use client';

import React, { useState, useEffect } from 'react';
import { useForm, SubmitHandler, Controller } from 'react-hook-form';
import NextLink from 'next/link';
import { useRouter } from 'next/navigation';
import useAuthStore from '@/store/authStore';
import apiFetch, { ApiError } from '@/services/api';

// MUI components
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Link,
  Alert,
  Stack,
  CircularProgress
} from '@mui/material';

/**
 * Login form input type definition
 */
interface LoginFormInputs {
  email: string;
  password: string;
}

/**
 * Login page component
 */
const LoginPage: React.FC = () => {
  // Form handling with react-hook-form
  const { control, handleSubmit, formState: { errors, isSubmitting } } = useForm<LoginFormInputs>({
    defaultValues: { email: '', password: '' },
  });
  
  // Auth store and routing
  const login = useAuthStore((state) => state.login);
  const router = useRouter();
  
  // Error state
  const [apiError, setApiError] = useState<string | null>(null);
  
  // Hydration state
  const [hydrated, setHydrated] = useState(false);
  
  // Handle Zustand hydration
  useEffect(() => {
    setHydrated(true);
  }, []);

  /**
   * Form submission handler
   */
  const onSubmit: SubmitHandler<LoginFormInputs> = async (data) => {
    setApiError(null);
    
    try {
      // Prepare form data for OAuth2 password flow
      const formData = new FormData();
      formData.append('username', data.email);
      formData.append('password', data.password);

      // Send login request
      const response = await apiFetch('/token', {
        method: 'POST',
        body: formData,
      });

      // Parse response
      const tokenData: { access_token: string; token_type: string } = await response.json();

      // Update auth store and redirect
      login(data.email, tokenData.access_token);
      router.push('/');
      
    } catch (error) {
      console.error('Login error:', error);
      
      // Handle API errors
      if (error instanceof ApiError) {
        setApiError(error.message);
      } else {
        setApiError('An unexpected error occurred. Please try again.');
      }
    }
  };

  // Show loading state during hydration
  if (!hydrated) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 'calc(100vh - 64px)',
      }}
    >
      <Card sx={{ maxWidth: 400, width: '100%', p: 1 }}>
        <CardContent>
          <Typography variant="h5" component="h1" gutterBottom align="center">
            Login
          </Typography>
          
          <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate sx={{ mt: 1 }}>
            <Stack spacing={2}>
              {/* Email field */}
              <Controller
                name="email"
                control={control}
                rules={{
                  required: 'Email is required',
                  pattern: { value: /^\S+@\S+$/i, message: 'Invalid email address' }
                }}
                render={({ field }) => (
                  <TextField
                    {...field}
                    margin="normal"
                    required
                    fullWidth
                    id="email"
                    label="Email Address"
                    autoComplete="email"
                    autoFocus
                    error={!!errors.email}
                    helperText={errors.email?.message}
                  />
                )}
              />
              
              {/* Password field */}
              <Controller
                name="password"
                control={control}
                rules={{
                  required: 'Password is required',
                  minLength: { value: 8, message: 'Password must be at least 8 characters' }
                }}
                render={({ field }) => (
                  <TextField
                    {...field}
                    margin="normal"
                    required
                    fullWidth
                    name="password"
                    label="Password"
                    type="password"
                    id="password"
                    autoComplete="current-password"
                    error={!!errors.password}
                    helperText={errors.password?.message}
                  />
                )}
              />

              {/* Error alert */}
              {apiError && (
                <Alert severity="error" sx={{ width: '100%' }}>
                  {apiError}
                </Alert>
              )}

              {/* Submit button */}
              <Button
                type="submit"
                fullWidth
                variant="contained"
                disabled={isSubmitting}
                sx={{ mt: 2, mb: 1 }}
              >
                {isSubmitting ? <CircularProgress size={24} /> : 'Sign In'}
              </Button>
              
              {/* Register link */}
              <Typography variant="body2" align="center">
                <Link component={NextLink} href="/register" passHref underline="hover">
                  {"Don't have an account? Register"}
                </Link>
              </Typography>
            </Stack>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
};

export default LoginPage;
