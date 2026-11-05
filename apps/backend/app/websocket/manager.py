import asyncio
import json
import logging
import os
from fastapi import WebSocket
from redis.asyncio import Redis

logger = logging.getLogger(__name__)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.redis = None
        self.pubsub = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Failed to send message to websocket: {e}")
                self.disconnect(connection)

    async def listen_to_redis(self):
        """Listens to Redis Pub/Sub and broadcasts to all WebSockets with auto-reconnection."""
        logger.info("Starting Redis Pub/Sub listener...")
        while True:
            try:
                self.redis = Redis.from_url(REDIS_URL, decode_responses=True)
                self.pubsub = self.redis.pubsub()
                await self.pubsub.subscribe("form141:events")
                logger.info("Subscribed to form141:events channel")
                
                async for message in self.pubsub.listen():
                    if message["type"] == "message":
                        data = message["data"]
                        await self.broadcast(data)
            except asyncio.CancelledError:
                logger.info("Redis listener cancelled.")
                break
            except Exception as e:
                logger.debug(f"Redis pubsub wait: {e}. Retrying in 4s...")
                await asyncio.sleep(4)

manager = ConnectionManager()
