from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

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
            except:
                del self.hospital_connections[case_id]
    
    def disconnect(self, case_id: int, role: str):
        if role == "ambulance":
            self.ambulance_connections.pop(case_id, None)
        else:
            self.hospital_connections.pop(case_id, None)

manager = ConnectionManager()

@router.websocket("/ws/ambulance/{case_id}")
async def websocket_ambulance(websocket: WebSocket, case_id: int):
    await manager.connect_ambulance(case_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await manager.forward_location(case_id, data)
    except WebSocketDisconnect:
        manager.disconnect(case_id, "ambulance")

@router.websocket("/ws/hospital/{case_id}")
async def websocket_hospital(websocket: WebSocket, case_id: int):
    await manager.connect_hospital(case_id, websocket)
    try:
        while True:
            # The hospital just listens, but we need to receive to detect disconnects
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(case_id, "hospital")
