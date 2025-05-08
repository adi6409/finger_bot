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
      
      // Get the MAC address immediately after connecting
      await getMacAddress(characteristic);
      
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
        // Longer delay between chunks to ensure they're processed properly
        await new Promise(resolve => setTimeout(resolve, 300));
      }
      
      // Add a final delay after all chunks are sent to ensure the device has time to process
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    return true;
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
      
      // Wait for the ESP32 to process the configuration and connect to WiFi
      console.log('Waiting for WiFi configuration to complete...');
      await new Promise(resolve => setTimeout(resolve, 5000));
      
      // Try to read the response with retries
      let response = null;
      let retries = 5;
      let wifiConfigured = false;
      
      while (retries > 0 && !wifiConfigured) {
        try {
          // Read response
          const value = await bluetoothDevice.characteristic.readValue();
          const decoder = new TextDecoder();
          const responseText = decoder.decode(value);
          
          if (responseText) {
            try {
              response = JSON.parse(responseText);
              console.log('WiFi configuration response:', response);
              
              if (response.status === 'success') {
                setSuccess('WiFi configured successfully!');
                wifiConfigured = true;
                break;
              } else if (response.status === 'error') {
                throw new Error(response.message || 'Failed to configure WiFi');
              }
            } catch (jsonError) {
              console.warn(`Error parsing JSON response: ${jsonError}`);
            }
          }
        } catch (readError) {
          console.warn(`Retry ${6 - retries}/5 failed:`, readError);
          
          // If this is a GATT operation error, the device might have disconnected
          // after successfully configuring WiFi
          if (readError instanceof Error && readError.message.includes('GATT operation failed')) {
            console.log('GATT operation error detected. Device may have disconnected after WiFi configuration.');
            
            // Assume success if we've sent the configuration
            console.log('WiFi configuration was likely successful. Proceeding with setup.');
            setSuccess('WiFi configured successfully!');
            wifiConfigured = true;
            break;
          }
        }
        
        retries--;
        if (retries > 0) {
          // Wait before retrying
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
      }
      
      // If we couldn't confirm WiFi configuration but we have a device MAC,
      // proceed anyway as the device might have disconnected after successful configuration
      if (!wifiConfigured && deviceMac) {
        console.log('Could not confirm WiFi configuration, but proceeding with device MAC from URL');
        setSuccess('WiFi configuration sent. Proceeding with setup.');
      } else if (!wifiConfigured) {
        throw new Error('Could not confirm WiFi configuration');
      }
      
  // We don't need to get the MAC address here anymore as we get it during initial connection
      
      // Move to next step
      setActiveStep(2);
    } catch (err) {
      console.error('WiFi configuration error:', err);
      
      // Check if this is a GATT operation error, which often occurs when the device
      // disconnects after successful WiFi configuration
      if (err instanceof Error && err.message.includes('GATT operation failed')) {
        console.log('GATT operation error detected. This may be normal if the device disconnected after WiFi configuration.');
        
        // We know we've sent the configuration data successfully before the error
        console.log('WiFi configuration was sent successfully before disconnection. Proceeding with setup.');
        setSuccess('WiFi configured successfully!');
        
        // Since we can't get the MAC address via BLE anymore (device disconnected),
        // we'll rely on the MAC address from the URL if available
        if (deviceMac) {
          // Move to next step
          setActiveStep(2);
          return;
        } else {
          setError('Device disconnected. Please restart the setup process with a device MAC address.');
        }
      } else {
        setError(`Failed to configure WiFi: ${err instanceof Error ? err.message : String(err)}`);
      }
    } finally {
      setLoading(false);
    }
  };

  // Get MAC address from device
  const getMacAddress = async (characteristic: any) => {
    try {
      if (!deviceMac) { // Only get MAC if we don't already have it
        console.log('Getting device MAC address...');
        await sendBleCommand(characteristic, { command: 'get_mac' });
        
        // Wait for the ESP32 to process the command
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Try to read the MAC address
        const macValue = await characteristic.readValue();
        const decoder = new TextDecoder();
        const macResponseText = decoder.decode(macValue);
        
        if (macResponseText) {
          try {
            const macResponse = JSON.parse(macResponseText);
            console.log('MAC address response:', macResponse);
            
            if (macResponse.mac) {
              // Update URL with MAC address
              router.replace(`/device-setup?mac=${macResponse.mac}`);
              return macResponse.mac;
            }
          } catch (jsonError) {
            console.warn('Error parsing MAC address JSON:', jsonError);
          }
        }
      }
      return deviceMac; // Return existing MAC if we have it
    } catch (macError) {
      console.warn('Error getting MAC address:', macError);
      return deviceMac; // Return existing MAC if there was an error
    }
  };

  // Register device
  const registerDevice = async () => {
    if (!deviceName.trim()) {
      setError('Please enter a device name');
      return;
    }

    // Try to get the MAC address again if we don't have it yet
    let macAddress = deviceMac;
    if (!macAddress && bluetoothDevice?.device?.gatt?.connected && bluetoothDevice?.characteristic) {
      macAddress = await getMacAddress(bluetoothDevice.characteristic);
    }

    if (!macAddress) {
      setError('Could not get device MAC address. Please try again.');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      console.log(`Registering device with MAC: ${macAddress} and name: ${deviceName}`);
      
      // First, register device with backend
      const response = await apiFetch('/devices', {
        method: 'POST',
        body: JSON.stringify({ 
          name: deviceName,
          device_id: macAddress // Use the MAC address we obtained via Bluetooth
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server returned ${response.status}`);
      }

      const device = await response.json();
      setRegisteredDeviceId(device.id);
      
      // If the Bluetooth device is still connected, send the registration command to the device
      if (bluetoothDevice?.device?.gatt?.connected && bluetoothDevice?.characteristic) {
        try {
          console.log('Sending device registration command to device');
          await sendBleCommand(bluetoothDevice.characteristic, {
            command: 'register_device',
            name: deviceName
          });
          
          // Wait for the device to process the registration
          await new Promise(resolve => setTimeout(resolve, 1000));
          
          console.log('Device registration command sent successfully');
        } catch (bleError) {
          console.warn('Error sending registration command to device:', bleError);
          // Continue even if this fails, as the device is already registered in the backend
        }
      } else {
        console.log('Bluetooth device not connected, skipping device-side registration');
      }
      
      setSuccess('Device registered successfully!');
      
      // Move to final step
      setActiveStep(3);
      
      // Disconnect from Bluetooth device if still connected
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
