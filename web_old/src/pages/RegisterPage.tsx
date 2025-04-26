import React, { useState } from 'react'; // Import useState
import { useForm, SubmitHandler } from 'react-hook-form';
import { Link, useNavigate } from 'react-router-dom'; // Import useNavigate
import useAuthStore from '../store/authStore'; // Import the auth store
import apiFetch from '../services/api'; // Import the apiFetch utility
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// Define the type for our form data
type RegisterFormInputs = {
  email: string;
  password_needs_at_least_8_chars: string;
  confirmPassword: string;
};

const RegisterPage: React.FC = () => {
  const { register, handleSubmit, watch, formState: { errors } } = useForm<RegisterFormInputs>();
  const password = watch('password_needs_at_least_8_chars'); // Watch password field for comparison
  const login = useAuthStore((state) => state.login); // Get login action from store
  const navigate = useNavigate(); // Get navigate function
  const [apiError, setApiError] = useState<string | null>(null); // State for API errors

  // Updated submit handler with API calls
  const onSubmit: SubmitHandler<RegisterFormInputs> = async (data) => {
    setApiError(null); // Clear previous errors
    try {
      // 1. Call the /register endpoint
      const registerResponse = await apiFetch('/register', {
        method: 'POST',
        body: JSON.stringify({
          email: data.email,
          password: data.password_needs_at_least_8_chars, // Use the correct field name
        }),
        // headers: { 'Content-Type': 'application/json' } // apiFetch handles this
      });

      if (!registerResponse.ok) {
        const errorData = await registerResponse.json().catch(() => ({ detail: 'Registration failed.' }));
        throw new Error(errorData.detail || 'Registration failed');
      }

      // 2. Automatically log in the user by calling /token
      const formData = new FormData();
      formData.append('username', data.email);
      formData.append('password', data.password_needs_at_least_8_chars);

      const tokenResponse = await apiFetch('/token', {
        method: 'POST',
        body: formData,
      });

      if (!tokenResponse.ok) {
        // Handle potential login failure after successful registration (unlikely but possible)
        throw new Error('Registration successful, but automatic login failed. Please log in manually.');
      }

      const tokenData: { access_token: string; token_type: string } = await tokenResponse.json();

      // 3. Update auth state and navigate
      login(data.email, tokenData.access_token);
      navigate('/'); // Redirect to home page

    } catch (error) {
      console.error('Registration error:', error);
      setApiError(error instanceof Error ? error.message : 'An unexpected error occurred.');
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded shadow-md w-full max-w-md">
        <h2 className="text-2xl font-bold mb-6 text-center">Register</h2>
        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="mb-4">
            <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="email">
              Email
            </label>
            <Input
              id="email"
              type="email"
              {...register('email', { required: 'Email is required', pattern: { value: /^\S+@\S+$/i, message: 'Invalid email address' } })}
              className={errors.email ? 'border-red-500' : ''}
            />
            {errors.email && <p className="text-red-500 text-xs italic">{errors.email.message}</p>}
          </div>
           {/* Display API Error */}
          {apiError && <p className="text-red-500 text-xs italic mb-4">{apiError}</p>}
          <div className="mb-4">
            <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="password">
              Password
            </label>
            <Input
              id="password"
              type="password"
              {...register('password_needs_at_least_8_chars', { required: 'Password is required', minLength: { value: 8, message: 'Password must be at least 8 characters' } })}
              className={errors.password_needs_at_least_8_chars ? 'border-red-500' : ''}
            />
            {errors.password_needs_at_least_8_chars && <p className="text-red-500 text-xs italic">{errors.password_needs_at_least_8_chars.message}</p>}
          </div>
          <div className="mb-6">
            <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="confirmPassword">
              Confirm Password
            </label>
            <Input
              id="confirmPassword"
              type="password"
              {...register('confirmPassword', {
                required: 'Please confirm your password',
                validate: value => value === password || 'Passwords do not match'
              })}
              className={errors.confirmPassword ? 'border-red-500' : ''}
            />
            {errors.confirmPassword && <p className="text-red-500 text-xs italic">{errors.confirmPassword.message}</p>}
          </div>
          <div className="flex items-center justify-between">
            <Button
              type="submit"
              variant="default"
              className="w-full"
            >
              Register
            </Button>
            <Link to="/login" className="inline-block align-baseline font-bold text-sm text-blue-500 hover:text-blue-800">
              Already have an account? Login
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
};

export default RegisterPage;
