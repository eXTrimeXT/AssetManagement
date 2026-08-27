import asyncio
import logging
from typing import Dict, Set

logger = logging.getLogger(__name__)

class NotificationManager:
    def __init__(self):
        # Храним МНОЖЕСТВО очередей для каждого сотрудника
        self.active_connections: Dict[str, Set[asyncio.Queue]] = {}

    async def connect(self, employee_id: str) -> asyncio.Queue:
        queue = asyncio.Queue()
        if employee_id not in self.active_connections:
            self.active_connections[employee_id] = set()
        self.active_connections[employee_id].add(queue)
        return queue

    def disconnect(self, employee_id: str, queue: asyncio.Queue):
        if employee_id in self.active_connections:
            self.active_connections[employee_id].discard(queue)
            if not self.active_connections[employee_id]:
                del self.active_connections[employee_id]

    async def broadcast(self, payload: dict):
        # Собираем всех, кого касается это уведомление
        targets = set()
        if payload.get("employee_id"):
            targets.add(payload["employee_id"])
        if payload.get("initiator_id"):
            targets.add(payload["initiator_id"])

        logger.debug(f"Ищем подключения для пользователей: {targets}")

        # Отправляем уведомление во все активные очереди всех затронутых пользователей
        for target_id in targets:
            if target_id in self.active_connections:
                logger.debug(f"Отправляем уведомление пользователю {target_id}")
                for queue in self.active_connections[target_id]:
                    await queue.put(payload)

notification_manager = NotificationManager()