import { Routes, Route, Link, useNavigate } from 'react-router-dom'; // Remove BrowserRouter
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import useAuthStore from './store/authStore'; // Import auth store
import ProtectedRoute from './components/ProtectedRoute'; // Import ProtectedRoute
import HomePage from './pages/HomePage'; // Import HomePage
import DevicesPage from './pages/DevicesPage'; // Import DevicesPage
import SchedulePage from './pages/SchedulePage'; // Import SchedulePage
import { Button } from "@/components/ui/button";
import { useState, useEffect } from "react";


function App() {
  const { isLoggedIn, logout } = useAuthStore(); // Get state and logout action
  const navigate = useNavigate(); // Get navigate function

  const handleLogout = () => {
    logout();
    navigate('/login'); // Redirect to login after logout
  };

  // Dark mode state
  const [darkMode, setDarkMode] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("theme") === "dark";
    }
    return false;
  });

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  }, [darkMode]);

  const toggleDarkMode = () => setDarkMode((d) => !d);

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-900">
      <nav className="bg-blue-600 dark:bg-gray-800 text-white p-4">
        <ul className="flex space-x-4 items-center">
          <li><Link to="/">Home</Link></li>
          {isLoggedIn ? (
            <>
              <li><Link to="/devices">Devices</Link></li>
              <li><Link to="/schedule">Schedule</Link></li>
              <li>
                <Button
                  onClick={handleLogout}
                  variant="destructive"
                  size="sm"
                  className="font-bold"
                >
                  Logout
                </Button>
              </li>
            </>
          ) : (
            <>
              <li><Link to="/login">Login</Link></li>
              <li><Link to="/register">Register</Link></li>
            </>
          )}
          <li>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Toggle dark mode"
              onClick={toggleDarkMode}
              className="text-xl"
            >
              {darkMode ? "☀️" : "🌙"}
            </Button>
          </li>
        </ul>
      </nav>

      <main className="p-4">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          {/* Protected Routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/devices" element={<DevicesPage />} />
            <Route path="/schedule" element={<SchedulePage />} />
          </Route>
        </Routes>
      </main>
    </div>
  );
}

export default App;
