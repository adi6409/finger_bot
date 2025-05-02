'use client'; // Mark as Client Component

import React, { useEffect, useState } from 'react';
import apiFetch from '@/services/api';
import Link from 'next/link';

// Import MUI components
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import IconButton from '@mui/material/IconButton';
import Alert from '@mui/material/Alert';
import CircularProgress from '@mui/material/CircularProgress'; // For loading state
import Stack from '@mui/material/Stack'; // For layout
import Snackbar from '@mui/material/Snackbar'; // For toasts/notifications
import Divider from '@mui/material/Divider';

// Import MUI Icons
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import SaveIcon from '@mui/icons-material/Save';
import CancelIcon from '@mui/icons-material/Cancel';
import PlayArrowIcon from '@mui/icons-material/PlayArrow'; // For 'Press' action
import AddIcon from '@mui/icons-material/Add'; // For adding new device

type Device = {
  id: string;
  name: string;
};

const DevicesPage: React.FC = () => {
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newDeviceName, setNewDeviceName] = useState('');
  const [creating, setCreating] = useState(false);
  const [pressLoading, setPressLoading] = useState<string | null>(null); // Track loading state per device press
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState<'success' | 'error'>('success');

  // Fetch devices on mount
  useEffect(() => {
    const fetchDevices = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await apiFetch('/devices');
        const data = await response.json();
        setDevices(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error fetching devices');
      } finally {
        setLoading(false);
      }
    };
    fetchDevices();
  }, []);

  // Create new device
  const handleCreateDevice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDeviceName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const response = await apiFetch('/devices', {
        method: 'POST',
        body: JSON.stringify({ name: newDeviceName }),
      });
      const created = await response.json();
      setDevices((prev) => [...prev, created]);
      setNewDeviceName('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error creating device');
    } finally {
      setCreating(false);
    }
  };

  // Delete device
  const handleDeleteDevice = async (id: string) => {
    setError(null);
    // Optional: Add confirmation dialog here
    if (!window.confirm(`Are you sure you want to delete this device?`)) return;
    try {
      await apiFetch(`/devices/${id}`, { method: 'DELETE' });
      setDevices((prev) => prev.filter((d) => d.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error deleting device');
    }
  };

  // Edit device (rename)
  const handleEditDevice = async (id: string, newName: string) => {
    setError(null);
    try {
      const response = await apiFetch(`/devices/${id}`, {
        method: 'PUT',
        body: JSON.stringify({ name: newName }),
      });
      const updated = await response.json();
      setDevices((prev) => prev.map((d) => (d.id === id ? updated : d)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error updating device');
    }
  };

  // Inline edit state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState('');

  const handlePress = async (id: string) => {
    setError(null);
    setPressLoading(id); // Set loading state for this specific button
    try {
      const response = await apiFetch(`/devices/${id}/action`, {
        method: "POST",
        body: JSON.stringify({ action: "press" }),
      });
      const pressResult: { status: string; result: string } = await response.json();
      console.log("Press Result:", pressResult);
      if (pressResult.status === 'done' && pressResult.result === 'True') {
        setSnackbarMessage('Action successful!');
        setSnackbarSeverity('success');
      } else {
        // Handle cases where status is not 'done' or result is not 'True' as failure
        setSnackbarMessage(`Action failed: ${pressResult.result || 'Unknown reason'}`);
        setSnackbarSeverity('error');
      }
      setSnackbarOpen(true);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to press device";
      setError(errorMessage); // Keep existing error state for main alert if needed
      setSnackbarMessage(errorMessage);
      setSnackbarSeverity('error');
      setSnackbarOpen(true);
    } finally {
      setPressLoading(null); // Clear loading state
    }
  };

  return (
    <>
      <Paper sx={{ p: 3, maxWidth: 'md', margin: 'auto' }}>
        <Typography variant="h5" component="h2" gutterBottom color="primary">
          Manage Devices
        </Typography>
        
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h6">Your Devices</Typography>
          <Button 
            component={Link}
            href="/device-setup"
            variant="contained" 
            color="primary"
            startIcon={<AddIcon />}
          >
            Setup New Device
          </Button>
        </Box>
        
        <Divider sx={{ mb: 3 }} />
        
        <Typography variant="subtitle1" gutterBottom>
          Register Device Manually
        </Typography>
        
        <Box component="form" onSubmit={handleCreateDevice} sx={{ display: 'flex', gap: 1, mb: 3 }}>
        <TextField
          label="New Device Name"
          variant="outlined"
          size="small"
          value={newDeviceName}
          onChange={(e) => setNewDeviceName(e.target.value)}
          disabled={creating}
          sx={{ flexGrow: 1 }}
        />
        <Button
          type="submit"
          variant="contained"
          disabled={creating}
          startIcon={creating ? <CircularProgress size={20} color="inherit" /> : null}
        >
          {creating ? 'Registering...' : 'Register Device'}
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table sx={{ minWidth: 650 }} aria-label="devices table">
            <TableHead>
              <TableRow sx={{ '& th': { fontWeight: 'bold' } }}>
                <TableCell>Name</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {devices.map((device) => (
                <TableRow
                  key={device.id}
                  sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
                >
                  <TableCell component="th" scope="row">
                    {editingId === device.id ? (
                      <Box
                        component="form"
                        onSubmit={(e) => {
                          e.preventDefault();
                          handleEditDevice(device.id, editingName);
                          setEditingId(null);
                        }}
                        sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                      >
                        <TextField
                          size="small"
                          variant="outlined"
                          value={editingName}
                          onChange={(e) => setEditingName(e.target.value)}
                          autoFocus
                          sx={{ flexGrow: 1 }}
                        />
                        <IconButton type="submit" color="success" size="small" aria-label="save">
                          <SaveIcon fontSize="small" />
                        </IconButton>
                        <IconButton type="button" color="inherit" size="small" onClick={() => setEditingId(null)} aria-label="cancel">
                          <CancelIcon fontSize="small" />
                        </IconButton>
                      </Box>
                    ) : (
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        {device.name}
                        <IconButton
                          size="small"
                          color="primary"
                          onClick={() => {
                            setEditingId(device.id);
                            setEditingName(device.name);
                          }}
                          sx={{ ml: 1 }}
                          aria-label="edit"
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Box>
                    )}
                  </TableCell>
                  <TableCell align="right">
                    <Stack direction="row" spacing={1} justifyContent="flex-end">
                      <Button
                        variant="contained"
                        color="success"
                        size="small"
                        startIcon={pressLoading === device.id ? <CircularProgress size={16} color="inherit" /> : <PlayArrowIcon />}
                        onClick={() => handlePress(device.id)}
                        disabled={pressLoading === device.id}
                      >
                        Press
                      </Button>
                      <Button
                        variant="outlined"
                        color="error"
                        size="small"
                        startIcon={<DeleteIcon />}
                        onClick={() => handleDeleteDevice(device.id)}
                      >
                        Delete
                      </Button>
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Paper>

      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbarOpen}
        autoHideDuration={6000} // Hide after 6 seconds
        onClose={() => setSnackbarOpen(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }} // Position
      >
        {/* Use Alert inside Snackbar for severity colors */}
        <Alert
          onClose={() => setSnackbarOpen(false)}
          severity={snackbarSeverity}
          variant="filled" // Use filled variant for better visibility
          sx={{ width: '100%' }}
        >
          {snackbarMessage}
        </Alert>
      </Snackbar>
    </>
  );
};

export default DevicesPage;
