"""
Unified server for Finger Bot that serves:
1. Frontend (Next.js)
2. Backend API (FastAPI) under /api
3. TCP socket for microcontroller communication
"""

import asyncio
import os
import signal
import socket
import struct
import json
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import subprocess
import sys
from contextlib import asynccontextmanager
from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()

SERVER_HOST = os.getenv("SERVER_HOST", "localhost:3333")
SERVER_PORT = int(os.getenv("SERVER_PORT", 3000))

# Import the backend app
from backend.main import app as backend_app

# Set SERVER_HOST in backend app state for server-info endpoint
backend_app.state.server_host = SERVER_HOST
backend_app.state.server_port = SERVER_PORT

# Create the main app
app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Since frontend and backend are on same origin, this is less critical
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add middleware to disable compression
@app.middleware("http")
async def no_compression_middleware(request: Request, call_next):
    response = await call_next(request)
    
    # Ensure no compression is used
    response.headers["Content-Encoding"] = "identity"
    
    # Remove any existing content-encoding headers
    if "content-encoding" in response.headers:
        del response.headers["content-encoding"]
    
    return response

# Mount the backend API under /api
app.mount("/api", backend_app)

# Helper function to proxy requests to the Next.js dev server
async def proxy_to_nextjs(request: Request, path: str = ""):
    import httpx
    import requests
    from starlette.background import BackgroundTask
    from starlette.responses import StreamingResponse
    
    next_url = f"http://localhost:3001/{path}"
    
    # Try a simpler approach using requests for direct proxying
    try:
        # Forward the request with the same method, headers, and body
        headers = dict(request.headers)
        # Remove host header to avoid conflicts
        if "host" in headers:
            del headers["host"]
            
        # Explicitly disable compression to avoid encoding issues
        headers["Accept-Encoding"] = "identity"
        
        # Get the request body
        body = await request.body()
        
        # Make the request using requests (synchronous but simpler)
        response = requests.request(
            method=request.method,
            url=next_url,
            headers=headers,
            params=request.query_params,
            data=body,
            allow_redirects=True,
            stream=True  # Stream the response
        )
        
        # Create a clean set of headers
        headers = dict(response.headers)
        
        # Remove any content encoding headers
        if "content-encoding" in headers:
            del headers["content-encoding"]
            
        # Remove content-length as it might be incorrect
        if "content-length" in headers:
            del headers["content-length"]
            
        # Remove transfer-encoding as it might cause issues
        if "transfer-encoding" in headers:
            del headers["transfer-encoding"]
        
        # Function to close the response when done
        def close_response():
            response.close()
        
        # Return a streaming response
        return StreamingResponse(
            response.iter_content(chunk_size=8192),
            status_code=response.status_code,
            headers=headers,
            media_type=response.headers.get("content-type"),
            background=BackgroundTask(close_response)
        )
    except Exception as e:
        # If the Next.js server is not running, return a helpful message
        return HTMLResponse(
            content=f"""
            <html>
            <body>
                <h1>Frontend Development Server Not Running</h1>
                <p>The Next.js development server should be running on port 3001.</p>
                <p>Please start it with:</p>
                <pre>cd frontend && npm run dev -- -p 3001</pre>
                <p>Error: {str(e)}</p>
            </body>
            </html>
            """,
            status_code=503
        )

# Root route handler
@app.api_route("/", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def root(request: Request):
    return await proxy_to_nextjs(request)

# WebSocket handler for TCP socket communication
@app.websocket("/ws/device")
async def websocket_endpoint(websocket):
    await websocket.accept()
    
    # This will be used to handle the WebSocket to TCP bridge
    # The implementation depends on how you want to handle the communication
    # between the WebSocket and the TCP socket
    
    try:
        while True:
            data = await websocket.receive_text()
            # Process the data and forward to TCP socket if needed
            # This is a placeholder for the actual implementation
            await websocket.send_text(f"Received: {data}")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()

# (TCP server logic removed; all device communication is now via HTTP/WebSocket)

# Proxy to Next.js dev server for frontend
@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def serve_frontend(request: Request, full_path: str):
    # This is a fallback route that will serve the frontend for any path not handled by the API
    
    # Check if the path is for the API
    if full_path.startswith("api/"):
        # This should be handled by the mounted backend_app
        pass
    
    # For all other paths, proxy to the Next.js dev server
    return await proxy_to_nextjs(request, full_path)

# Main entry point
if __name__ == "__main__":
    # Start the server with compression disabled
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=3000,
        http="h11",  # Use h11 protocol which is simpler
        limit_concurrency=100,
        timeout_keep_alive=5,
        access_log=True,
        use_colors=True
    )
