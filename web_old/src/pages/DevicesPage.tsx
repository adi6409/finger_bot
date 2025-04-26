import React, { useEffect, useState } from 'react';
import apiFetch from '../services/api';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

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

  // Fetch devices on mount
  useEffect(() => {
    const fetchDevices = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await apiFetch('/devices');
        if (!response.ok) throw new Error('Failed to fetch devices');
        const data = await response.json();
        setDevices(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
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
      if (!response.ok) throw new Error('Failed to create device');
      const created = await response.json();
      setDevices((prev) => [...prev, created]);
      setNewDeviceName('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setCreating(false);
    }
  };

  // Delete device
  const handleDeleteDevice = async (id: string) => {
    setError(null);
    try {
      const response = await apiFetch(`/devices/${id}`, { method: 'DELETE' });
      if (!response.ok) throw new Error('Failed to delete device');
      setDevices((prev) => prev.filter((d) => d.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
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
      if (!response.ok) throw new Error('Failed to update device');
      const updated = await response.json();
      setDevices((prev) => prev.map((d) => (d.id === id ? updated : d)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  // Inline edit state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState('');

  const handlePress = async (id:string) => {
    try {
      const response = await apiFetch(`/devices/${id}/action`, {
        method: "POST",
        body: JSON.stringify({ action: "press" }),
        headers: { "Content-Type": "application/json" },
      });

      const pressResult: {status: string, result: string} = await response.json();
      console.log("Result: " + pressResult.result)
      

    } catch (err) {
      setError("Failed to press device");
    }
  }

  return (
    <div className="flex justify-center items-center min-h-screen bg-gray-100">
      <div className="bg-white shadow-lg rounded-lg p-8 max-w-2xl w-full">
        <h2 className="text-2xl font-bold mb-4 text-blue-700">Manage Devices</h2>

        <form onSubmit={handleCreateDevice} className="flex items-center mb-4 gap-2">
          <Input
            type="text"
            value={newDeviceName}
            onChange={(e) => setNewDeviceName(e.target.value)}
            placeholder="Device name"
            disabled={creating}
          />
          <Button
            type="submit"
            variant="default"
            disabled={creating}
          >
            {creating ? 'Registering...' : 'Register New Device'}
          </Button>
        </form>

        {error && <p className="text-red-500 mb-2">{error}</p>}
        {loading ? (
          <p>Loading devices...</p>
        ) : (
          <div className="bg-white shadow-md rounded">
            <table className="min-w-full table-auto">
              <thead className="bg-gray-200">
                <tr>
                  <th className="px-4 py-2 text-left">Name</th>
                  <th className="px-4 py-2 text-left">Actions</th>
                </tr>
              </thead>
              <tbody>
                {devices.map((device, index) => (
                  <tr key={device.id} className={index % 2 === 0 ? 'bg-gray-50' : ''}>
                    <td className="border px-4 py-2">
                      {editingId === device.id ? (
                        <form
                          onSubmit={(e) => {
                            e.preventDefault();
                            handleEditDevice(device.id, editingName);
                            setEditingId(null);
                          }}
                          className="flex items-center gap-2"
                        >
                          <Input
                            type="text"
                            value={editingName}
                            onChange={(e) => setEditingName(e.target.value)}
                            className="px-2 py-1"
                            autoFocus
                          />
                          <Button type="submit" variant="secondary" size="sm" className="text-green-600 font-bold">Save</Button>
                          <Button type="button" variant="ghost" size="sm" className="text-gray-500" onClick={() => setEditingId(null)}>
                            Cancel
                          </Button>
                        </form>
                      ) : (
                        <>
                          {device.name}
                          <Button
                            variant="link"
                            size="sm"
                            className="ml-2 text-blue-500 hover:text-blue-700 text-xs p-0 h-auto"
                            onClick={() => {
                              setEditingId(device.id);
                              setEditingName(device.name);
                            }}
                          >
                            Edit
                          </Button>
                        </>
                      )}
                    </td>
                    <td className="border px-4 py-2">
                    <div className="flex gap-2">
                      <Button
                        variant="default"
                        size="sm"
                        className="text-green-700"
                        onClick={() => handlePress(device.id)}
                      >
                        Press!
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        className="text-red-500 hover:text-red-700"
                        onClick={() => handleDeleteDevice(device.id)}
                      >
                        Delete
                      </Button>
                    </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default DevicesPage;
