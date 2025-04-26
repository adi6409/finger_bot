import React, { useState } from 'react'; // Import useState
import { useForm, SubmitHandler } from 'react-hook-form';
import { Link, useNavigate } from 'react-router-dom'; // Import useNavigate
import useAuthStore from '../store/authStore'; // Import the auth store
import apiFetch from '../services/api'; // Import the apiFetch utility
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// Define the type for our form data
type LoginFormInputs = {
  email: string;
  password_needs_at_least_8_chars: string; // Example validation requirement in name
};

const LoginPage: React.FC = () => {
  const { register, handleSubmit, formState: { errors } } = useForm<LoginFormInputs>();
  const login = useAuthStore((state) => state.login); // Get login action from store
  const navigate = useNavigate(); // Get navigate function
  const [apiError, setApiError] = useState<string | null>(null); // State for API errors

  // Updated submit handler with API call
  const onSubmit: SubmitHandler<LoginFormInputs> = async (data) => {
    setApiError(null); // Clear previous errors
    try {
      // FastAPI's OAuth2PasswordRequestForm expects form data
      const formData = new FormData();
      formData.append('username', data.email);
      // Use the correct field name from the form data type
      formData.append('password', data.password_needs_at_least_8_chars);

      const response = await apiFetch('/token', {
        method: 'POST',
        body: formData, // Send as form data
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Login failed. Please check your credentials.' }));
        throw new Error(errorData.detail || 'Login failed');
      }

      const tokenData: { access_token: string; token_type: string } = await response.json();

      // Call login action with email and token
      login(data.email, tokenData.access_token);
      navigate('/'); // Redirect to home page after successful login

    } catch (error) {
      console.error('Login error:', error);
      setApiError(error instanceof Error ? error.message : 'An unexpected error occurred.');
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded shadow-md w-full max-w-md">
        <h2 className="text-2xl font-bold mb-6 text-center">Login</h2>
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
          <div className="mb-6">
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
          <div className="flex items-center justify-between">
            <Button
              type="submit"
              variant="default"
              className="w-full"
            >
              Sign In
            </Button>
            <Link to="/register" className="inline-block align-baseline font-bold text-sm text-blue-500 hover:text-blue-800">
              Don't have an account? Register
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;
