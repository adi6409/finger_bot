import { create } from 'zustand';
import { persist } from 'zustand/middleware'; // Import persist middleware

// Define the shape of the store's state
interface AuthState {
  isLoggedIn: boolean;
  user: { email: string } | null;
  token: string | null; // Add token field
  login: (email: string, token: string) => void; // Update login signature
  logout: () => void;
  setToken: (token: string | null) => void; // Action to explicitly set token
}

// Create the Zustand store with persist middleware
const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      isLoggedIn: false,
      user: null,
      token: null, // Initial token state
      login: (email, token) => set({ isLoggedIn: true, user: { email }, token }), // Set token on login
      logout: () => set({ isLoggedIn: false, user: null, token: null }), // Clear token on logout
      setToken: (token) => set({ token }), // Action to set token
    }),
    {
      name: 'auth-storage', // Name of the item in storage (localStorage by default)
      // Optionally specify parts of the state to persist
      // partialize: (state) => ({ token: state.token, isLoggedIn: state.isLoggedIn, user: state.user }),
    }
  )
);


export default useAuthStore;
