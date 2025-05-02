# Finger Bot Unified Server

This project combines the frontend, backend API, and TCP socket server into a single unified server for HTTPS reasons. This simplifies deployment and avoids cross-origin issues.

## Architecture

The unified server consists of:

1. **Frontend**: Next.js application served at the root path
2. **Backend API**: FastAPI application mounted at `/api`
3. **TCP Socket**: For microcontroller communication, running on a dynamically assigned port

## Setup

Run the setup script to install all required dependencies:

```bash
chmod +x setup.sh
./setup.sh
```

## Running the Server

1. Start the Next.js frontend development server:

```bash
cd frontend
npm run dev -- -p 3001
```

2. In a separate terminal, start the unified server:

```bash
python server.py
```

The unified server will be available at http://localhost:3000

## How It Works

- The main server (server.py) creates a FastAPI application that:
  - Mounts the backend API under `/api`
  - Starts a TCP server on a dynamically assigned port for microcontroller communication
  - Proxies all other requests to the Next.js development server

- The frontend communicates with the backend API using relative URLs (`/api/...`)
- The microcontroller connects to the TCP server using the dynamically assigned port provided during device setup

## Development

- Frontend code is in the `frontend/` directory
- Backend code is in the `backend/` directory
- Microcontroller code is in the `micropython/` directory

## Production Deployment

For production deployment, you would:

1. Build the Next.js frontend:

```bash
cd frontend
npm run build
```

2. Modify the server.py to serve the static files from the `frontend/.next` directory instead of proxying to the development server

3. Deploy the unified server behind a reverse proxy like Nginx with HTTPS enabled


## Known Issues

- Wrong WiFi password on setup will cause the device to not connect to the network. The user will need to reset the device and try again.

