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
type RegisterFormInputs = {
  email: string;
  password: string;
  confirmPassword: string;
};

const RegisterPage: React.FC = () => {
  const { control, handleSubmit, watch, formState: { errors } } = useForm<RegisterFormInputs>({
    defaultValues: { email: '', password: '', confirmPassword: '' },
  });
  const password = watch('password'); // Watch password field for confirmation validation
  const login = useAuthStore((state) => state.login);
  const router = useRouter();
  const [apiError, setApiError] = useState<string | null>(null);

  const onSubmit: SubmitHandler<RegisterFormInputs> = async (data) => {
    setApiError(null);
    try {
      // 1. Call the /register endpoint
      const registerResponse = await apiFetch('/register', {
        method: 'POST',
        body: JSON.stringify({
          email: data.email,
          password: data.password,
        }),
      });

      if (!registerResponse.ok) {
        const errorData = await registerResponse.json().catch(() => ({ detail: 'Registration failed.' }));
        throw new Error(errorData.detail || 'Registration failed');
      }

      // 2. Automatically log in the user by calling /token
      const formData = new FormData();
      formData.append('username', data.email);
      formData.append('password', data.password);

      const tokenResponse = await apiFetch('/token', {
        method: 'POST',
        body: formData,
      });

      if (!tokenResponse.ok) {
        throw new Error('Registration successful, but automatic login failed. Please log in manually.');
      }

      const tokenData: { access_token: string; token_type: string } = await tokenResponse.json();

      // 3. Update auth state and navigate
      login(data.email, tokenData.access_token);
      router.push('/'); // Redirect to home page

    } catch (error) {
      console.error('Registration error:', error);
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
        minHeight: 'calc(100vh - 64px)', // Adjust based on AppBar height
      }}
    >
      <Card sx={{ maxWidth: 400, width: '100%', p: 1 }}>
        <CardContent>
          <Typography variant="h5" component="h2" gutterBottom align="center">
            Register
          </Typography>
          <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate sx={{ mt: 1 }}>
            <Stack spacing={2}> {/* Use Stack for spacing */}
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
                    error={!!errors.password}
                    helperText={errors.password?.message}
                  />
                )}
              />
              <Controller
                name="confirmPassword"
                control={control}
                rules={{
                  required: 'Please confirm your password',
                  validate: value => value === password || 'Passwords do not match'
                }}
                render={({ field }) => (
                  <TextField
                    {...field}
                    margin="normal"
                    required
                    fullWidth
                    name="confirmPassword"
                    label="Confirm Password"
                    type="password"
                    id="confirmPassword"
                    error={!!errors.confirmPassword}
                    helperText={errors.confirmPassword?.message}
                  />
                )}
              />

              {apiError && <Alert severity="error" sx={{ width: '100%' }}>{apiError}</Alert>}

              <Button
                type="submit"
                fullWidth
                variant="contained"
                sx={{ mt: 2, mb: 1 }}
              >
                Register
              </Button>
              <Typography variant="body2" align="center">
                <Link component={NextLink} href="/login" passHref underline="hover">
                  {'Already have an account? Login'}
                </Link>
              </Typography>
            </Stack>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
};

export default RegisterPage;
