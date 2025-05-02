import useAuthStore from '../store/authStore'; // Import store to get token

const API_BASE_URL = '/api'; // Backend API is now mounted under /api

// Function to get the current auth token
const getAuthToken = (): string | null => {
  // Zustand state is accessed outside React components like this
  return useAuthStore.getState().token;
};

// Custom fetch function to automatically add Authorization header
const apiFetch = async (url: string, options: RequestInit = {}): Promise<Response> => {
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  // Ensure Content-Type is set for POST/PUT/PATCH JSON requests if not already set
  if (options.method && ['POST', 'PUT', 'PATCH'].includes(options.method.toUpperCase()) && options.body && !headers.has('Content-Type')) {
     if (typeof options.body === 'string') {
        try {
            JSON.parse(options.body); // Check if it's a JSON string
            headers.set('Content-Type', 'application/json');
        } catch (e) {
            // Not a JSON string, do nothing (or handle other types like FormData)
        }
     } else if (!(options.body instanceof FormData)) {
         // If body is an object but not FormData, assume JSON
         headers.set('Content-Type', 'application/json');
     }
  }


  const response = await fetch(`${API_BASE_URL}${url}`, {
    ...options,
    headers,
  });

  // Optional: Add global error handling here if needed
  if (!response.ok) {
    // Handle specific status codes, e.g., 401 Unauthorized
    if (response.status === 401) {
      useAuthStore.getState().logout(); // Auto-logout on 401
      // Optionally redirect to login
    }
    // Throw an error to be caught by the calling function
    const errorData = await response.json().catch(() => ({ detail: 'An unknown error occurred' }));
    throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
  }

  return response;
};

export default apiFetch;
