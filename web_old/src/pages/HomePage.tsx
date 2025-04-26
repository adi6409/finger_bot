import React from 'react';
import useAuthStore from '../store/authStore'; // Import auth store to display user info

const HomePage: React.FC = () => {
  const { isLoggedIn, user } = useAuthStore(); // Get auth state

  return (
    <div className="flex justify-center items-center min-h-[60vh]">
      <div className="bg-white shadow-lg rounded-lg p-8 max-w-md w-full">
        <h2 className="text-2xl font-bold mb-4 text-blue-700">Welcome to Finger Bot Control</h2>
        {isLoggedIn && user ? (
          <p className="text-gray-700 mb-2">
            Hello, <span className="font-semibold">{user.email}</span>!<br />
            Use the navigation above to manage your devices and schedules.
          </p>
        ) : (
          <p className="text-gray-600 mb-2">
            Please <span className="font-semibold">log in</span> or <span className="font-semibold">register</span> to manage your devices.
          </p>
        )}
        {/* Add more dashboard elements here later */}
      </div>
    </div>
  );
};

export default HomePage;
