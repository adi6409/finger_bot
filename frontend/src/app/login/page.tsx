'use client'; // Mark as Client Component

import React, { useState } from 'react';
import { useForm, SubmitHandler, Controller } from 'react-hook-form';
import NextLink from 'next/link'; // Use NextLink for routing
import { useRouter } from 'next/navigation';
import useAuthStore from '@/store/authStore';
import apiFetch from '@/services/api';

// Import MUI components
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import TextField from '@mui/material/TextField';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import Link from '@mui/material/Link'; // Use MUI Link
import Alert from '@mui/material/Alert';
import Stack from '@mui/material/Stack';

// Define the type for our form data
type LoginFormInputs = {
  email: string;
  password: string;
};

const LoginPage: React.FC = () => {
  // Use Controller for MUI compatibility with react-hook-form
  const { control, handleSubmit, formState: { errors } } = useForm<LoginFormInputs>({
    defaultValues: { email: '', password: '' }, // Set default values
  });
  const login = useAuthStore((state) => state.login);
  const router = useRouter();
  const [apiError, setApiError] = useState<string | null>(null);

  const onSubmit: SubmitHandler<LoginFormInputs> = async (data) => {
    setApiError(null);
    try {
      const formData = new FormData();
      formData.append('username', data.email);
      formData.append('password', data.password);

      const response = await apiFetch('/token', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
         const errorData = await response.json().catch(() => ({ detail: 'Login failed. Please check your credentials.' }));
         throw new Error(errorData.detail || 'Login failed');
      }

      const tokenData: { access_token: string; token_type: string } = await response.json();

      login(data.email, tokenData.access_token);
      router.push('/'); // Redirect to home page

    } catch (error) {
      console.error('Login error:', error);
      setApiError(error instanceof Error ? error.message : 'An unexpected error occurred.');
    }
  };

  // Handle Zustand hydration
  const [isClient, setIsClient] = React.useState(false);
  React.useEffect(() => {
    setIsClient(true);
  }, []);

  if (!isClient) {
    return null; // Or a loading indicator
  }

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 'calc(100vh - 64px)', // Adjust based on AppBar height (default is 64px)
      }}
    >
      <Card sx={{ maxWidth: 400, width: '100%', p: 1 }}>
        <CardContent>
          <Typography variant="h5" component="h2" gutterBottom align="center">
            Login
          </Typography>
          <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate sx={{ mt: 1 }}>
            <Stack spacing={2}> {/* Use Stack for spacing form elements */}
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

              {apiError && <Alert severity="error" sx={{ width: '100%' }}>{apiError}</Alert>}

              <Button
                type="submit"
                fullWidth
                variant="contained"
                sx={{ mt: 2, mb: 1 }} // Add margin top/bottom
              >
                Sign In
              </Button>
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
