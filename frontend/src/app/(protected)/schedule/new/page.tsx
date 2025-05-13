'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import apiFetch from '@/services/api';

import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Select, { SelectChangeEvent } from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import TextField from '@mui/material/TextField';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import Stack from '@mui/material/Stack';

type Device = {
  id: string;
  name: string;
};

const actions = [
  { value: 'press', label: 'Press' },
  { value: 'release', label: 'Release' },
  // Add more actions as needed
];

const daysOfWeek = [
  { value: 'mon', label: 'Monday' },
  { value: 'tue', label: 'Tuesday' },
  { value: 'wed', label: 'Wednesday' },
  { value: 'thu', label: 'Thursday' },
  { value: 'fri', label: 'Friday' },
  { value: 'sat', label: 'Saturday' },
  { value: 'sun', label: 'Sunday' },
];

type FormState = {
  device_id: string;
  action: string;
  time: string;
  repeat: string[];
};

const NewSchedulePage: React.FC = () => {
  const router = useRouter();
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState<FormState>({
    device_id: '',
    action: actions[0].value,
    time: '',
    repeat: [],
  });
  const [noRepeat, setNoRepeat] = useState(true);

  useEffect(() => {
    const fetchDevices = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await apiFetch('/devices');
        const data = await res.json();
        setDevices(data);
        if (data.length > 0) {
          setForm(f => ({ ...f, device_id: data[0].id }));
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load devices');
      } finally {
        setLoading(false);
      }
    };
    fetchDevices();
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement> | SelectChangeEvent) => {
    const { name, value } = e.target;
    if (name === 'repeat') {
      if (typeof value === 'string') {
        setForm(prev => ({ ...prev, repeat: value ? value.split(',') : [] }));
      } else {
        setForm(prev => ({ ...prev, repeat: value as string[] }));
      }
      setNoRepeat(false);
    } else {
      setForm(prev => ({ ...prev, [name]: value }));
    }
  };

  const handleNoRepeatChange = () => {
    setNoRepeat(true);
    setForm(prev => ({ ...prev, repeat: [] }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.device_id || !form.action || !form.time) {
      setError('Please fill in all required fields.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        ...form,
        repeat: noRepeat ? [] : form.repeat,
      };
      await apiFetch('/schedules', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      router.push('/schedule');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create schedule');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box sx={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      bgcolor: 'background.default',
    }}>
      <Paper sx={{
        width: 420,
        maxWidth: '95vw',
        p: 4,
        borderRadius: 3,
        boxShadow: 6,
        display: 'flex',
        flexDirection: 'column',
        gap: 3,
      }}>
        <Typography variant="h4" color="primary" align="center" gutterBottom>
          New Scheduled Action
        </Typography>
        {error && <Alert severity="error">{error}</Alert>}
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
            <CircularProgress />
          </Box>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <FormControl fullWidth size="medium" sx={{ mb: 2 }}>
              <InputLabel id="device-select-label">Device</InputLabel>
              <Select
                labelId="device-select-label"
                id="device-select"
                name="device_id"
                value={form.device_id}
                label="Device"
                onChange={handleChange}
                required
              >
                {devices.map((d) => (
                  <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth size="medium" sx={{ mb: 2 }}>
              <InputLabel id="action-select-label">Action</InputLabel>
              <Select
                labelId="action-select-label"
                id="action-select"
                name="action"
                value={form.action}
                label="Action"
                onChange={handleChange}
                required
              >
                {actions.map((a) => (
                  <MenuItem key={a.value} value={a.value}>{a.label}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="Time"
              type="time"
              name="time"
              value={form.time}
              onChange={handleChange}
              InputLabelProps={{ shrink: true }}
              required
              inputProps={{ style: { fontSize: 24, letterSpacing: 2 } }}
              sx={{ mb: 2 }}
            />
            <FormControl fullWidth size="medium" sx={{ mb: 2 }}>
              <InputLabel id="repeat-select-label">Repeat</InputLabel>
              <Select<string[]>
                labelId="repeat-select-label"
                id="repeat-select"
                name="repeat"
                multiple
                value={form.repeat}
                label="Repeat"
                onChange={(e) => {
                  const { value } = e.target;
                  setForm(prev => ({
                    ...prev,
                    repeat: typeof value === 'string' ? value.split(',') : (value as string[]),
                  }));
                  setNoRepeat(false);
                }}
                renderValue={(selected) =>
                  (selected as string[]).map(
                    (val) => daysOfWeek.find((d) => d.value === val)?.label || val
                  ).join(', ')
                }
              >
                {daysOfWeek.map((d) => (
                  <MenuItem key={d.value} value={d.value}>
                    {d.label}
                  </MenuItem>
                ))}
              </Select>
              <Button
                variant={noRepeat ? "contained" : "outlined"}
                color="secondary"
                onClick={handleNoRepeatChange}
                sx={{ mt: 1 }}
              >
                No Repeat
              </Button>
            </FormControl>
            <Stack direction="row" spacing={2} justifyContent="center" sx={{ mt: 2 }}>
              <Button
                variant="outlined"
                color="secondary"
                onClick={() => router.push('/schedule')}
                disabled={submitting}
                sx={{ minWidth: 120, fontSize: 18 }}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="contained"
                color="primary"
                disabled={submitting}
                sx={{ minWidth: 120, fontSize: 18 }}
              >
                {submitting ? <CircularProgress size={24} color="inherit" /> : 'Save'}
              </Button>
            </Stack>
          </form>
        )}
      </Paper>
    </Box>
  );
};

export default NewSchedulePage;
