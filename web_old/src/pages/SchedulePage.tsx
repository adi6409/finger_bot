import React, { useEffect, useState } from 'react';
import apiFetch from '../services/api';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

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

  // Form state for new schedule
  const [newSchedule, setNewSchedule] = useState({
    device_id: '',
    action: 'press',
    time: '',
    repeat: '',
  });
  const [creating, setCreating] = useState(false);

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
        if (!schedulesRes.ok || !devicesRes.ok) throw new Error('Failed to fetch schedules or devices');
        setSchedules(await schedulesRes.json());
        setDevices(await devicesRes.json());
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, []);

  // Create new schedule
  const handleCreateSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSchedule.device_id || !newSchedule.action || !newSchedule.time || !newSchedule.repeat) return;
    setCreating(true);
    setError(null);
    try {
      const response = await apiFetch('/schedules', {
        method: 'POST',
        body: JSON.stringify(newSchedule),
      });
      if (!response.ok) throw new Error('Failed to create schedule');
      const created = await response.json();
      setSchedules((prev) => [...prev, created]);
      setNewSchedule({ device_id: '', action: '', time: '', repeat: '' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setCreating(false);
    }
  };

  // Delete schedule
  const handleDeleteSchedule = async (id: string) => {
    setError(null);
    try {
      const response = await apiFetch(`/schedules/${id}`, { method: 'DELETE' });
      if (!response.ok) throw new Error('Failed to delete schedule');
      setSchedules((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  // Edit schedule (inline)
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingSchedule, setEditingSchedule] = useState<Schedule | null>(null);

  const handleEditSchedule = async (id: string) => {
    if (!editingSchedule) return;
    setError(null);
    try {
      const response = await apiFetch(`/schedules/${id}`, {
        method: 'PUT',
        body: JSON.stringify(editingSchedule),
      });
      if (!response.ok) throw new Error('Failed to update schedule');
      const updated = await response.json();
      setSchedules((prev) => prev.map((s) => (s.id === id ? updated : s)));
      setEditingId(null);
      setEditingSchedule(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  return (
    <div className="flex justify-center items-center min-h-screen bg-gray-100">
      <div className="bg-white shadow-lg rounded-lg p-8 max-w-2xl w-full">
        <h2 className="text-2xl font-bold mb-4 text-blue-700">Manage Schedules</h2>

        <form onSubmit={handleCreateSchedule} className="flex flex-wrap items-center mb-4 gap-2">
          <select
            value={newSchedule.device_id}
            onChange={(e) => setNewSchedule((s) => ({ ...s, device_id: e.target.value }))}
            className="border rounded px-3 py-2"
            required
          >
            <option value="">Select device</option>
            {devices.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
          <Input
            type="time"
            value={newSchedule.time}
            onChange={(e) => setNewSchedule((s) => ({ ...s, time: e.target.value }))}
            required
          />
          <Input
            type="text"
            value={newSchedule.repeat}
            onChange={(e) => setNewSchedule((s) => ({ ...s, repeat: e.target.value }))}
            placeholder="Repeat (e.g. Daily, Wednesdays)"
            required
          />
          <Button
            type="submit"
            variant="default"
            disabled={creating}
          >
            {creating ? 'Adding...' : 'Add New Schedule'}
          </Button>
        </form>

        {error && <p className="text-red-500 mb-2">{error}</p>}
        {loading ? (
          <p>Loading schedules...</p>
        ) : (
          <div className="bg-white shadow-md rounded">
            <table className="min-w-full table-auto">
              <thead className="bg-gray-200">
                <tr>
                  <th className="px-4 py-2 text-left">Device</th>
                  <th className="px-4 py-2 text-left">Action</th>
                  <th className="px-4 py-2 text-left">Time</th>
                  <th className="px-4 py-2 text-left">Repeat</th>
                  <th className="px-4 py-2 text-left">Actions</th>
                </tr>
              </thead>
              <tbody>
                {schedules.map((schedule, index) => {
                  const device = devices.find((d) => d.id === schedule.device_id);
                  return (
                    <tr key={schedule.id} className={index % 2 === 0 ? 'bg-gray-50' : ''}>
                      {editingId === schedule.id ? (
                        <>
                          <td className="border px-4 py-2">
                            <select
                              value={editingSchedule?.device_id || ''}
                              onChange={(e) =>
                                setEditingSchedule((s) =>
                                  s ? { ...s, device_id: e.target.value } : null
                                )
                              }
                              className="border rounded px-2 py-1"
                            >
                              <option value="">Select device</option>
                              {devices.map((d) => (
                                <option key={d.id} value={d.id}>{d.name}</option>
                              ))}
                            </select>
                          </td>
                          <td className="border px-4 py-2">
                            <Input
                              type="time"
                              value={editingSchedule?.time || ''}
                              onChange={(e) =>
                                setEditingSchedule((s) =>
                                  s ? { ...s, time: e.target.value } : null
                                )
                              }
                              className="px-2 py-1"
                            />
                          </td>
                          <td className="border px-4 py-2">
                            <Input
                              type="text"
                              value={editingSchedule?.repeat || ''}
                              onChange={(e) =>
                                setEditingSchedule((s) =>
                                  s ? { ...s, repeat: e.target.value } : null
                                )
                              }
                              className="px-2 py-1"
                            />
                          </td>
                          <td className="border px-4 py-2">
                            <Button
                              variant="secondary"
                              size="sm"
                              className="text-green-600 font-bold mr-2"
                              onClick={() => handleEditSchedule(schedule.id)}
                            >
                              Save
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-gray-500"
                              onClick={() => {
                                setEditingId(null);
                                setEditingSchedule(null);
                              }}
                            >
                              Cancel
                            </Button>
                          </td>
                        </>
                      ) : (
                        <>
                          <td className="border px-4 py-2">{device ? device.name : 'Unknown'}</td>
                          <td className="border px-4 py-2">{schedule.action}</td>
                          <td className="border px-4 py-2">{schedule.time}</td>
                          <td className="border px-4 py-2">{schedule.repeat}</td>
                          <td className="border px-4 py-2">
                            <Button
                              variant="link"
                              size="sm"
                              className="text-blue-500 hover:text-blue-700 mr-2 p-0 h-auto"
                              onClick={() => {
                                setEditingId(schedule.id);
                                setEditingSchedule(schedule);
                              }}
                            >
                              Edit
                            </Button>
                            <Button
                              variant="destructive"
                              size="sm"
                              className="text-red-500 hover:text-red-700"
                              onClick={() => handleDeleteSchedule(schedule.id)}
                            >
                              Delete
                            </Button>
                          </td>
                        </>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default SchedulePage;
