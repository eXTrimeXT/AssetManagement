# import asyncio
# import logging
# from typing import Dict, Set
#
# logger = logging.getLogger(__name__)
#
# class NotificationManager:
#     def __init__(self):
#         # Храним МНОЖЕСТВО очередей для каждого сотрудника (поддержка нескольких вкладок)
#         self.active_connections: Dict[str, Set[asyncio.Queue]] = {}
#
#     async def connect(self, employee_id: str) -> asyncio.Queue:
#         queue = asyncio.Queue()
#         if employee_id not in self.active_connections:
#             self.active_connections[employee_id] = set()
#         self.active_connections[employee_id].add(queue)
#         return queue
#
#     def disconnect(self, employee_id: str, queue: asyncio.Queue):
#         if employee_id in self.active_connections:
#             # Удаляем только конкретную очередь этой вкладки
#             self.active_connections[employee_id].discard(queue)
#             # Если у пользователя не осталось активных подключений, удаляем его из словаря
#             if not self.active_connections[employee_id]:
#                 del self.active_connections[employee_id]
#
#     async def broadcast(self, payload: dict):
#         target_employee_id = payload.get("employee_id")
#         logger.debug(f"Ищем подключения для employee_id: {target_employee_id}")
#
#         # Отправляем уведомление во ВСЕ активные очереди (вкладки) этого пользователя
#         if target_employee_id and target_employee_id in self.active_connections:
#             queues = self.active_connections[target_employee_id]
#             logger.debug(f"Найдено {len(queues)} активных подключений. Отправляем уведомление.")
#             for q in queues:
#                 await q.put(payload)
#
#         # Если это системное уведомление для всех
#         elif target_employee_id == "all":
#             for queues in self.active_connections.values():
#                 for q in queues:
#                     await q.put(payload)
#
# notification_manager = NotificationManager()


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
        target_employee_id = payload.get("employee_id")
        logger.debug(f"Получен сигнал обновления для employee_id: {target_employee_id}")

        if target_employee_id and target_employee_id in self.active_connections:
            queues = self.active_connections[target_employee_id]
            logger.debug(f"Отправляем сигнал обновления в {len(queues)} вкладок(ки)")
            for q in queues:
                await q.put(payload)
        elif target_employee_id == "all":
            for queues in self.active_connections.values():
                for q in queues:
                    await q.put(payload)

notification_manager = NotificationManager()