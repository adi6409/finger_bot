'use client'; // Mark as Client Component

import React, { useEffect, useState } from 'react';
import apiFetch from '@/services/api';

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
import CircularProgress from '@mui/material/CircularProgress';
import Stack from '@mui/material/Stack';
import Select, { SelectChangeEvent } from '@mui/material/Select'; // For Select input
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';

// Import MUI Icons
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import SaveIcon from '@mui/icons-material/Save';
import CancelIcon from '@mui/icons-material/Cancel';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';

type Device = {
  id: string;
  name: string;
};

type Schedule = {
  id: string;
  device_id: string;
  action: string;
  time: string; // "HH:MM"
  repeat: string;
};

const SchedulePage: React.FC = () => {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [serverTime, setServerTime] = useState<string | null>(null);

  // Form state for new schedule
  const [newSchedule, setNewSchedule] = useState<Omit<Schedule, 'id'>>({
    device_id: '',
    action: 'press', // Default action
    time: '',
    repeat: '',
  });
  const [creating, setCreating] = useState(false);

  // Fetch server time on mount
  useEffect(() => {
    const fetchServerTime = async () => {
      try {
        const response = await apiFetch('/time');
        const data = await response.json();
        setServerTime(data.time);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error fetching server time');
      }
    };
    fetchServerTime();
  });


  // Fetch schedules and devices on mount
  useEffect(() => {
    const fetchAll = async () => {
      setLoading(true);
      setError(null);
      try {
        const [schedulesRes, devicesRes] = await Promise.all([
          apiFetch('/schedules'),
          apiFetch('/devices'),
        ]);
        setSchedules(await schedulesRes.json());
        const devicesData = await devicesRes.json();
        setDevices(devicesData);
        // Set default device_id for new schedule form if devices exist
        if (devicesData.length > 0 && !newSchedule.device_id) {
            setNewSchedule(s => ({ ...s, device_id: devicesData[0].id }));
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error fetching data');
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Run only once

  // Handle input changes for the new schedule form
  const handleNewScheduleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement> | SelectChangeEvent) => {
    const { name, value } = e.target;
    setNewSchedule((prev) => ({ ...prev, [name]: value }));
  };

  // Create new schedule
  const handleCreateSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSchedule.device_id || !newSchedule.action || !newSchedule.time || !newSchedule.repeat) {
        setError("Please fill in all schedule details.");
        return;
    };
    setCreating(true);
    setError(null);
    try {
      const response = await apiFetch('/schedules', {
        method: 'POST',
        body: JSON.stringify(newSchedule),
      });
      const created = await response.json();
      setSchedules((prev) => [...prev, created]);
      // Reset form
      setNewSchedule({
        device_id: devices.length > 0 ? devices[0].id : '',
        action: 'press',
        time: '',
        repeat: '',
       });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error creating schedule');
    } finally {
      setCreating(false);
    }
  };

  // Delete schedule
  const handleDeleteSchedule = async (id: string) => {
    setError(null);
    if (!window.confirm(`Are you sure you want to delete this schedule?`)) return;
    try {
      await apiFetch(`/schedules/${id}`, { method: 'DELETE' });
      setSchedules((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error deleting schedule');
    }
  };

  // Edit schedule (inline)
  const [editingId, setEditingId] = useState<string | null>(null);
  const [currentEditData, setCurrentEditData] = useState<Schedule | null>(null);

  const handleEditChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement> | SelectChangeEvent) => {
    const { name, value } = e.target;
    setCurrentEditData(prev => prev ? { ...prev, [name]: value } : null);
  };

  const startEditing = (schedule: Schedule) => {
    setEditingId(schedule.id);
    setCurrentEditData({ ...schedule });
  };

  const cancelEditing = () => {
    setEditingId(null);
    setCurrentEditData(null);
  };

  const handleSaveEdit = async (id: string) => {
    if (!currentEditData) return;
    setError(null);
    try {
      const response = await apiFetch(`/schedules/${id}`, {
        method: 'PUT',
        body: JSON.stringify(currentEditData),
      });
      const updated = await response.json();
      setSchedules((prev) => prev.map((s) => (s.id === id ? updated : s)));
      cancelEditing();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error updating schedule');
    }
  };

  return (
    <Paper sx={{ p: 3, maxWidth: 'lg', margin: 'auto' }}> {/* Wider container */}
      <Typography variant="h5" component="h2" gutterBottom color="primary">
        Manage Schedules
      </Typography>

      {/* Add New Schedule Button */}
      <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
        <Button
          variant="contained"
          color="primary"
          size="large"
          startIcon={<AddCircleOutlineIcon />}
          sx={{
            fontSize: 22,
            px: 5,
            py: 2,
            borderRadius: 3,
            boxShadow: 3,
            minWidth: 280,
            minHeight: 64,
            letterSpacing: 1,
          }}
          onClick={() => window.location.assign('/schedule/new')}
        >
          Add New Schedule
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* Schedules Table */}
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table sx={{ minWidth: 700 }} aria-label="schedules table">
            <TableHead>
              <TableRow sx={{ '& th': { fontWeight: 'bold' } }}>
                <TableCell>Device</TableCell>
                <TableCell>Action</TableCell>
                <TableCell>Time</TableCell>
                <TableCell>Repeat</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {schedules.map((schedule) => {
                const device = devices.find((d) => d.id === schedule.device_id);
                const isEditing = editingId === schedule.id;
                return (
                  <TableRow key={schedule.id} hover>
                    {isEditing && currentEditData ? (
                      // Edit Mode Cells
                      <>
                        <TableCell sx={{ verticalAlign: 'top', pt: 1.5 }}>
                          <FormControl fullWidth size="small">
                            <Select
                              name="device_id"
                              value={currentEditData.device_id}
                              onChange={handleEditChange}
                            >
                              {devices.map((d) => (
                                <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        </TableCell>
                        <TableCell sx={{ verticalAlign: 'top', pt: 1.5 }}>{currentEditData.action}</TableCell>
                        <TableCell sx={{ verticalAlign: 'top', pt: 1.5 }}>
                          <TextField
                            type="time"
                            name="time"
                            value={currentEditData.time}
                            onChange={handleEditChange}
                            size="small"
                            InputLabelProps={{ shrink: true }}
                            fullWidth
                          />
                        </TableCell>
                        <TableCell sx={{ verticalAlign: 'top', pt: 1.5 }}>
                          <TextField
                            type="text"
                            name="repeat"
                            value={currentEditData.repeat}
                            onChange={handleEditChange}
                            size="small"
                            fullWidth
                          />
                        </TableCell>
                        <TableCell align="right" sx={{ verticalAlign: 'top', pt: 1.5 }}>
                          <Stack direction="row" spacing={1} justifyContent="flex-end">
                            <IconButton color="success" size="small" onClick={() => handleSaveEdit(schedule.id)} aria-label="save">
                              <SaveIcon fontSize="small" />
                            </IconButton>
                            <IconButton color="inherit" size="small" onClick={cancelEditing} aria-label="cancel">
                              <CancelIcon fontSize="small" />
                            </IconButton>
                          </Stack>
                        </TableCell>
                      </>
                    ) : (
                      // View Mode Cells
                      <>
                        <TableCell>{device ? device.name : 'Unknown Device'}</TableCell>
                        <TableCell>{schedule.action}</TableCell>
                        <TableCell>{schedule.time}</TableCell>
                        <TableCell>{schedule.repeat}</TableCell>
                        <TableCell align="right">
                          <Stack direction="row" spacing={1} justifyContent="flex-end">
                            <IconButton color="primary" size="small" onClick={() => startEditing(schedule)} aria-label="edit">
                              <EditIcon fontSize="small" />
                            </IconButton>
                            <IconButton color="error" size="small" onClick={() => handleDeleteSchedule(schedule.id)} aria-label="delete">
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </Stack>
                        </TableCell>
                      </>
                    )}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Paper>
  );
};

export default SchedulePage;
