'use client'; // Mark as Client Component

import React, { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import apiFetch from '@/services/api';

// BLE utility functions
const BLE_MTU_SIZE = 20; // Standard BLE MTU size

// Import MUI components
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import Stepper from '@mui/material/Stepper';
import Step from '@mui/material/Step';
import StepLabel from '@mui/material/StepLabel';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import TextField from '@mui/material/TextField';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import Divider from '@mui/material/Divider';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';

// Import MUI Icons
import BluetoothIcon from '@mui/icons-material/Bluetooth';
import WifiIcon from '@mui/icons-material/Wifi';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import DevicesIcon from '@mui/icons-material/Devices';

const steps = ['Connect to Device', 'Configure WiFi', 'Register Device'];

interface BluetoothDevice {
  device: any;
  server: any;
  service: any;
  characteristic: any;
}

const DeviceSetupPage: React.FC = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const deviceMac = searchParams.get('mac');
  
  const [activeStep, setActiveStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [deviceName, setDeviceName] = useState('');
  const [wifiNetworks, setWifiNetworks] = useState<string[]>([]);
  const [selectedNetwork, setSelectedNetwork] = useState('');
  const [wifiPassword, setWifiPassword] = useState('');
  const [bluetoothDevice, setBluetoothDevice] = useState<BluetoothDevice | null>(null);
  const [registeredDeviceId, setRegisteredDeviceId] = useState<string | null>(null);

  // Check if Web Bluetooth API is supported
  const isWebBluetoothSupported = () => {
    return navigator && 'bluetooth' in navigator;
  };

  // Connect to Bluetooth device
  const connectToDevice = async () => {
    try {
      setLoading(true);
      setError(null);

      // Check if Web Bluetooth API is supported
      if (!isWebBluetoothSupported()) {
        throw new Error(
          'Web Bluetooth API is not supported in your browser. ' +
          'Please use Chrome, Edge, or Opera on desktop, or Chrome for Android.'
        );
      }

      // Request Bluetooth device
      const device = await navigator.bluetooth.requestDevice({
        // filters: [
        //   // { namePrefix: 'ESP32' }
        //   // { services: ['4fafc201-1fb5-459e-8fcc-c5c9c331914b'] } // ESP32 BLE service UUID
        // ],
        optionalServices: ['4fafc201-1fb5-459e-8fcc-c5c9c331914b'],
        acceptAllDevices: true,
      });

      console.log('Device selected:', device);

      // Connect to GATT server
      const server = await device.gatt?.connect();
      console.log('Connected to GATT server');

      // Get primary service
      const service = await server?.getPrimaryService('4fafc201-1fb5-459e-8fcc-c5c9c331914b');
      console.log('Got primary service');

      // Get characteristic
      const characteristic = await service?.getCharacteristic('beb5483e-36e1-4688-b7f5-ea07361b26a8');
      console.log('Got characteristic');

      setBluetoothDevice({ device, server, service, characteristic });
      setSuccess('Successfully connected to device!');
      
      // Scan for WiFi networks
      await scanWifiNetworks(characteristic);
      
      // Move to next step
      setActiveStep(1);
    } catch (err) {
      console.error('Bluetooth connection error:', err);
      setError(`Failed to connect: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  // Utility function to send BLE commands safely
  const sendBleCommand = async (characteristic: any, command: any) => {
    const encoder = new TextEncoder();
    const jsonString = JSON.stringify(command);
    console.log(`Sending BLE command: ${jsonString}`);
    
    // Check if the command is small enough to send in one chunk
    const encodedCommand = encoder.encode(jsonString);
    
    if (encodedCommand.length <= BLE_MTU_SIZE) {
      // Small enough to send in one go
      await characteristic.writeValue(encodedCommand);
    } else {
      // Need to chunk the data
      console.log(`Command too large (${encodedCommand.length} bytes), sending in chunks`);
      
      // Send in chunks of BLE_MTU_SIZE bytes
      for (let i = 0; i < encodedCommand.length; i += BLE_MTU_SIZE) {
        const chunk = encodedCommand.slice(i, i + BLE_MTU_SIZE);
        await characteristic.writeValue(chunk);
        // Small delay between chunks to ensure they're processed in order
        await new Promise(resolve => setTimeout(resolve, 50));
      }
    }
  };

  // Scan for WiFi networks
  const scanWifiNetworks = async (characteristic: any) => {
    try {
      setLoading(true);
      setError(null);

      // Send command to scan WiFi networks
      await sendBleCommand(characteristic, { command: 'scan_wifi' });

      // Wait for the ESP32 to scan networks (this takes time)
      console.log('Waiting for WiFi scan to complete...');
      await new Promise(resolve => setTimeout(resolve, 3000));

      // Try to read the response with retries
      let response = null;
      let retries = 5;
      
      while (retries > 0 && !response?.networks) {
        try {
          // Read WiFi networks
          const value = await characteristic.readValue();
          const decoder = new TextDecoder();
          const responseText = decoder.decode(value);
          
          if (responseText) {
            response = JSON.parse(responseText);
            console.log('WiFi scan response:', response);
            
            if (response.networks && response.networks.length > 0) {
              setWifiNetworks(response.networks);
              break;
            }
          }
        } catch (readError) {
          console.warn(`Retry ${6 - retries}/5 failed:`, readError);
        }
        
        retries--;
        if (retries > 0) {
          // Wait before retrying
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
      }
      
      if (!response?.networks) {
        throw new Error('Failed to scan WiFi networks after multiple attempts');
      }
    } catch (err) {
      console.error('WiFi scan error:', err);
      setError(`Failed to scan WiFi networks: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  // Configure WiFi
  const configureWifi = async () => {
    if (!bluetoothDevice?.characteristic) {
      setError('Bluetooth device not connected');
      return;
    }

    if (!selectedNetwork || !wifiPassword) {
      setError('Please select a network and enter password');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Get server info
      const serverInfoResponse = await apiFetch('/server-info');
      const serverInfo = await serverInfoResponse.json();
      console.log('Server info:', serverInfo);

      // Send WiFi credentials and server info to device
      const configData = {
        command: 'configure_wifi',
        ssid: selectedNetwork,
        password: wifiPassword,
        server_host: serverInfo.host,
        server_port: 3000,  // The unified server port
        tcp_port: serverInfo.port  // The TCP port for device connection
      };
      
      console.log('Sending WiFi configuration:', configData);
      await sendBleCommand(bluetoothDevice.characteristic, configData);

      // Wait for the ESP32 to process the configuration
      console.log('Waiting for WiFi configuration to complete...');
      await new Promise(resolve => setTimeout(resolve, 5000));

      // Try to read the response with retries
      let response = null;
      let retries = 5;
      
      while (retries > 0 && !response?.status) {
        try {
          // Read response
          const value = await bluetoothDevice.characteristic.readValue();
          const decoder = new TextDecoder();
          const responseText = decoder.decode(value);
          
          if (responseText) {
            response = JSON.parse(responseText);
            console.log('WiFi configuration response:', response);
            
            if (response.status === 'success') {
              setSuccess('WiFi configured successfully!');
              break;
            } else if (response.status === 'error') {
              throw new Error(response.message || 'Failed to configure WiFi');
            }
          }
        } catch (readError) {
          console.warn(`Retry ${6 - retries}/5 failed:`, readError);
        }
        
        retries--;
        if (retries > 0) {
          // Wait before retrying
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
      }
      
      if (!response?.status) {
        throw new Error('Failed to configure WiFi after multiple attempts');
      }
      
      // Get device MAC address
      console.log('Getting device MAC address...');
      await sendBleCommand(bluetoothDevice.characteristic, { command: 'get_mac' });
      
      // Wait for the ESP32 to process the command
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Try to read the MAC address with retries
      let macResponse = null;
      retries = 5;
      
      while (retries > 0 && !macResponse?.mac) {
        try {
          const macValue = await bluetoothDevice.characteristic.readValue();
          const decoder = new TextDecoder();
          const macResponseText = decoder.decode(macValue);
          
          if (macResponseText) {
            macResponse = JSON.parse(macResponseText);
            console.log('MAC address response:', macResponse);
            
            if (macResponse.mac) {
              // If we got the MAC from the device, use it
              if (!deviceMac) {
                // Only set if not already provided via QR code
                // This is a controlled side effect, but it's necessary
                // to ensure we have the MAC address for registration
                const urlParams = new URLSearchParams(window.location.search);
                if (!urlParams.has('mac')) {
                  router.replace(`/device-setup?mac=${macResponse.mac}`);
                }
              }
              break;
            }
          }
        } catch (readError) {
          console.warn(`MAC retry ${6 - retries}/5 failed:`, readError);
        }
        
        retries--;
        if (retries > 0) {
          // Wait before retrying
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
      }
      
      if (!macResponse?.mac) {
        throw new Error('Failed to get device MAC address after multiple attempts');
      }
      
      // Move to next step
      setActiveStep(2);
    } catch (err) {
      console.error('WiFi configuration error:', err);
      setError(`Failed to configure WiFi: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  // Register device
  const registerDevice = async () => {
    if (!deviceName.trim()) {
      setError('Please enter a device name');
      return;
    }

    if (!deviceMac) {
      setError('Device MAC address is required. Please restart the setup process.');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      console.log(`Registering device with MAC: ${deviceMac} and name: ${deviceName}`);
      
      // Register device with backend
      const response = await apiFetch('/devices', {
        method: 'POST',
        body: JSON.stringify({ 
          name: deviceName,
          device_id: deviceMac // Use the MAC address from QR code or from Bluetooth
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server returned ${response.status}`);
      }

      const device = await response.json();
      setRegisteredDeviceId(device.id);
      setSuccess('Device registered successfully!');
      
      // Move to final step
      setActiveStep(3);
      
      // Disconnect from Bluetooth device
      if (bluetoothDevice?.device?.gatt?.connected) {
        try {
          bluetoothDevice.device.gatt.disconnect();
          console.log('Bluetooth device disconnected');
        } catch (disconnectError) {
          console.warn('Error disconnecting Bluetooth device:', disconnectError);
        }
      }
      
      // Wait a moment before redirecting
      setTimeout(() => {
        router.push('/devices');
      }, 3000);
    } catch (err) {
      console.error('Device registration error:', err);
      setError(`Failed to register device: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  const handleNext = () => {
    switch (activeStep) {
      case 0:
        connectToDevice();
        break;
      case 1:
        configureWifi();
        break;
      case 2:
        registerDevice();
        break;
      default:
        setActiveStep((prevStep) => prevStep + 1);
    }
  };

  const handleBack = () => {
    setActiveStep((prevStep) => prevStep - 1);
  };

  return (
    <Paper sx={{ p: 3, maxWidth: 'md', margin: 'auto' }}>
      <Typography variant="h5" component="h2" gutterBottom color="primary">
        Device Setup
      </Typography>

      <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
        {steps.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

      <Box sx={{ mt: 2, mb: 2 }}>
        {activeStep === 0 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Connect to your ESP32 device
            </Typography>
            <Typography paragraph>
              Make sure your ESP32 device is powered on and in setup mode. The LED should be blinking blue.
            </Typography>
            <Button
              variant="contained"
              color="primary"
              startIcon={<BluetoothIcon />}
              onClick={handleNext}
              disabled={loading}
            >
              {loading ? <CircularProgress size={24} /> : 'Connect via Bluetooth'}
            </Button>
          </Box>
        )}

        {activeStep === 1 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Configure WiFi Connection
            </Typography>
            
            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel id="wifi-network-label">WiFi Network</InputLabel>
              <Select
                labelId="wifi-network-label"
                value={selectedNetwork}
                label="WiFi Network"
                onChange={(e) => setSelectedNetwork(e.target.value)}
                disabled={loading}
              >
                {wifiNetworks.map((network) => (
                  <MenuItem key={network} value={network}>
                    {network}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            
            <TextField
              label="WiFi Password"
              type="password"
              fullWidth
              value={wifiPassword}
              onChange={(e) => setWifiPassword(e.target.value)}
              disabled={loading}
              sx={{ mb: 2 }}
            />
            
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
              <Button onClick={handleBack} disabled={loading}>
                Back
              </Button>
              <Button
                variant="contained"
                color="primary"
                onClick={handleNext}
                disabled={loading || !selectedNetwork || !wifiPassword}
                startIcon={loading ? <CircularProgress size={24} /> : <WifiIcon />}
              >
                Configure WiFi
              </Button>
            </Box>
          </Box>
        )}

        {activeStep === 2 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Register Your Device
            </Typography>
            
            <TextField
              label="Device Name"
              fullWidth
              value={deviceName}
              onChange={(e) => setDeviceName(e.target.value)}
              disabled={loading}
              sx={{ mb: 2 }}
            />
            
            {deviceMac && (
              <Alert severity="info" sx={{ mb: 2 }}>
                Device MAC Address: {deviceMac}
              </Alert>
            )}
            
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2 }}>
              <Button onClick={handleBack} disabled={loading}>
                Back
              </Button>
              <Button
                variant="contained"
                color="primary"
                onClick={handleNext}
                disabled={loading || !deviceName.trim()}
                startIcon={loading ? <CircularProgress size={24} /> : <DevicesIcon />}
              >
                Register Device
              </Button>
            </Box>
          </Box>
        )}

        {activeStep === 3 && (
          <Box sx={{ textAlign: 'center' }}>
            <CheckCircleIcon color="success" sx={{ fontSize: 60, mb: 2 }} />
            <Typography variant="h6" gutterBottom>
              Setup Complete!
            </Typography>
            <Typography paragraph>
              Your device has been successfully registered and connected to WiFi.
            </Typography>
            <Typography paragraph>
              You will be redirected to the devices page in a moment...
            </Typography>
          </Box>
        )}
      </Box>
    </Paper>
  );
};

export default DeviceSetupPage;
