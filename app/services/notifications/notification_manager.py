import asyncio
from typing import Dict

class NotificationManager:
    def __init__(self):
        # Храним очереди для каждого подключенного сотрудника
        self.active_connections: Dict[str, asyncio.Queue] = {}

    async def connect(self, employee_id: str) -> asyncio.Queue:
        queue = asyncio.Queue()
        self.active_connections[employee_id] = queue
        return queue

    def disconnect(self, employee_id: str):
        if employee_id in self.active_connections:
            del self.active_connections[employee_id]

    async def broadcast(self, payload: dict):
        # Получаем employee_id из полезной нагрузки (он должен там быть)
        target_employee_id = payload.get("employee_id")

        # Если уведомление для конкретного пользователя, и он подключен
        if target_employee_id and target_employee_id in self.active_connections:
            await self.active_connections[target_employee_id].put(payload)

        # Если это системное уведомление для всех (например, target_employee_id == "all")
        elif target_employee_id == "all":
            for queue in self.active_connections.values():
                await queue.put(payload)

notification_manager = NotificationManager()