'use client'; // Mark as a Client Component

import React, { ReactNode } from 'react';
import Link from 'next/link'; // Use Next.js Link for navigation
import { useRouter } from 'next/navigation';
import useAuthStore from '@/store/authStore';
import { useThemeContext } from '@/context/ThemeContext'; // Import theme context hook

// Import MUI components
import AppBar from '@mui/material/AppBar';
import Box from '@mui/material/Box';
import Toolbar from '@mui/material/Toolbar';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';
import Brightness4Icon from '@mui/icons-material/Brightness4'; // Dark mode icon
import Brightness7Icon from '@mui/icons-material/Brightness7'; // Light mode icon

interface LayoutProps {
  children: ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const { isLoggedIn, logout } = useAuthStore();
  const router = useRouter();
  const { mode, toggleMode } = useThemeContext(); // Get theme mode and toggle function

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  // Helper component for Nav Links to integrate Next.js Link with MUI Button styling
  const NavLink = ({ href, children }: { href: string; children: ReactNode }) => (
    <Button
      component={Link} // Use Next.js Link component
      href={href}
      sx={{ color: 'inherit', textTransform: 'none' }} // Inherit color, normal text case
    >
      {children}
    </Button>
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <AppBar position="static">
        <Toolbar>
          {/* Use Typography for the main title/link if desired, or just buttons */}
          {/* <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            <Link href="/" passHref legacyBehavior>
              <MuiLink color="inherit" underline="none">Finger Bot</MuiLink>
            </Link>
          </Typography> */}

          {/* Navigation Links */}
          <Box sx={{ flexGrow: 1, display: 'flex', gap: 1 }}>
             <NavLink href="/">Home</NavLink>
            {isLoggedIn ? (
              <>
                <NavLink href="/devices">Devices</NavLink>
                <NavLink href="/schedule">Schedule</NavLink>
              </>
            ) : (
              <>
                <NavLink href="/login">Login</NavLink>
                <NavLink href="/register">Register</NavLink>
              </>
            )}
          </Box>

          {/* Auth Button and Theme Toggle */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
             {isLoggedIn && (
               <Button color="inherit" variant="outlined" size="small" onClick={handleLogout}>
                 Logout
               </Button>
             )}
            <IconButton sx={{ ml: 1 }} onClick={toggleMode} color="inherit" aria-label="toggle theme">
              {mode === 'dark' ? <Brightness7Icon /> : <Brightness4Icon />}
            </IconButton>
          </Box>

        </Toolbar>
      </AppBar>

      {/* Main content area */}
      {/* Container centers content and provides padding */}
      <Container component="main" sx={{ flexGrow: 1, py: 3 }}> {/* py adds padding top/bottom */}
        {children}
      </Container>

      {/* Optional Footer */}
      {/* <Box component="footer" sx={{ py: 2, mt: 'auto', backgroundColor: 'background.paper' }}>
        <Container maxWidth="lg">
          <Typography variant="body2" color="text.secondary" align="center">
            {'© '}
            {new Date().getFullYear()}
            {' Finger Bot'}
          </Typography>
        </Container>
      </Box> */}
    </Box>
  );
};

export default Layout;
