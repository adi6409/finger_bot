/**
 * API service for making authenticated requests to the backend
 */

import useAuthStore from '../store/authStore';

// Base URL for all API requests
const API_BASE_URL = '/api';

/**
 * Get the current authentication token from the store
 * @returns The current auth token or null if not authenticated
 */
const getAuthToken = (): string | null => {
  return useAuthStore.getState().token;
};

/**
 * Custom API error class with additional response data
 */
export class ApiError extends Error {
  status: number;
  data?: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

/**
 * Make an authenticated API request
 * 
 * @param url - The API endpoint path (without the base URL)
 * @param options - Fetch options
 * @returns Promise resolving to the fetch Response
 * @throws ApiError if the request fails
 */
const apiFetch = async (url: string, options: RequestInit = {}): Promise<Response> => {
  // Set up headers with authentication if available
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  // Set Content-Type header for JSON requests if not already set
  if (options.method && ['POST', 'PUT', 'PATCH'].includes(options.method.toUpperCase()) && 
      options.body && !headers.has('Content-Type')) {
    if (typeof options.body === 'string') {
      try {
        JSON.parse(options.body); // Check if it's a valid JSON string
        headers.set('Content-Type', 'application/json');
      } catch (e) {
        // Not a JSON string, do nothing (likely FormData or other format)
      }
    } else if (!(options.body instanceof FormData)) {
      // If body is an object but not FormData, assume JSON
      headers.set('Content-Type', 'application/json');
    }
  }

  try {
    // Make the request
    const response = await fetch(`${API_BASE_URL}${url}`, {
      ...options,
      headers,
    });

    // Handle error responses
    if (!response.ok) {
      // Handle 401 Unauthorized by logging out
      if (response.status === 401) {
        useAuthStore.getState().logout();
        // Note: Navigation should be handled by the component using this function
      }

      // Parse error data if possible
      let errorData;
      try {
        errorData = await response.json();
      } catch {
        errorData = { detail: 'An unknown error occurred' };
      }

      // Throw a custom error with status and data
      throw new ApiError(
        errorData.detail || `HTTP error! status: ${response.status}`,
        response.status,
        errorData
      );
    }

    return response;
  } catch (error) {
    // Re-throw ApiError instances
    if (error instanceof ApiError) {
      throw error;
    }

    // Convert other errors to ApiError
    throw new ApiError(
      error instanceof Error ? error.message : 'Network error',
      0, // 0 indicates network/other error, not HTTP status
      { originalError: error }
    );
  }
};

export default apiFetch;
