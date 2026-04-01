import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from app.core.config import settings

router = APIRouter()


def _validate_ws_token(token: str | None) -> dict | None:
    """Validate JWT token from WebSocket query params. Returns decoded payload or None."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("sub") is None:
            return None
        return payload
    except JWTError:
        return None


class ConnectionManager:
    def __init__(self):
        self.ambulance_connections: dict = {}
        self.hospital_connections: dict = {}
    
    async def connect_ambulance(self, case_id: int, ws: WebSocket):
        await ws.accept()
        self.ambulance_connections[case_id] = ws
    
    async def connect_hospital(self, case_id: int, ws: WebSocket):
        await ws.accept()
        self.hospital_connections[case_id] = ws
    
    async def forward_location(self, case_id: int, data: dict):
        if case_id in self.hospital_connections:
            try:
                await self.hospital_connections[case_id].send_json(data)
            except (ConnectionError, RuntimeError):
                del self.hospital_connections[case_id]
    
    def disconnect(self, case_id: int, role: str):
        if role == "ambulance":
            self.ambulance_connections.pop(case_id, None)
        else:
            self.hospital_connections.pop(case_id, None)

manager = ConnectionManager()

@router.websocket("/ws/ambulance/{case_id}")
async def websocket_ambulance(websocket: WebSocket, case_id: int):
    # SECURITY: Validate JWT token before allowing WebSocket connection
    token = websocket.query_params.get("token")
    payload = _validate_ws_token(token)
    if not payload:
        await websocket.close(code=1008, reason="Authentication required")
        return
    
    await manager.connect_ambulance(case_id, websocket)
    last_eta_calc = 0.0

    try:
        while True:
            data = await websocket.receive_json()
            
            # WebSocket ETA tick - 60-second ORS ping interval
            now = time.time()
            if now - last_eta_calc >= 60.0:
                # TODO: Make ORS API call with data['lat'], data['lng'] and hospital coords
                # Update data['eta_minutes'] with real routing time
                # Example:
                # ors_response = await httpx.get("https://api.openrouteservice.org/...", params={...})
                # data['eta_minutes'] = ors_response.json()['features'][0]['properties']['summary']['duration'] / 60
                
                last_eta_calc = now
            
            await manager.forward_location(case_id, data)
    except WebSocketDisconnect:
        manager.disconnect(case_id, "ambulance")

@router.websocket("/ws/hospital/{case_id}")
async def websocket_hospital(websocket: WebSocket, case_id: int):
    # SECURITY: Validate JWT token before allowing WebSocket connection
    token = websocket.query_params.get("token")
    payload = _validate_ws_token(token)
    if not payload:
        await websocket.close(code=1008, reason="Authentication required")
        return
    
    await manager.connect_hospital(case_id, websocket)
    try:
        while True:
            # The hospital just listens, but we need to receive to detect disconnects
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(case_id, "hospital")
