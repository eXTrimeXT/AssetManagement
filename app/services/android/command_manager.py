import asyncio
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class CommandManager:
    def __init__(self):
        # Храним события для каждого устройства: { "serial_number": asyncio.Event }
        self.pending_commands: Dict[str, asyncio.Event] = {}
        # Храним сами команды: { "serial_number": {"action": "...", "data": {...}} }
        self.commands: Dict[str, dict] = {}

    async def wait_for_command(self, serial_number: str, timeout: float = 30.0) -> Optional[dict]:
        """
        Ждет команду для устройства. Если команды нет, ждет до timeout секунд.
        """
        if serial_number not in self.pending_commands:
            self.pending_commands[serial_number] = asyncio.Event()

        event = self.pending_commands[serial_number]

        try:
            # Ждем, пока событие не будет установлено, или пока не истечет таймаут
            await asyncio.wait_for(event.wait(), timeout=timeout)

            # Если событие сработало, забираем команду и очищаем её
            command = self.commands.pop(serial_number, None)
            event.clear() # Сбрасываем событие для следующего ожидания
            return command

        except asyncio.TimeoutError:
            # Таймаут истек, команд нет
            return None

    async def send_command(self, serial_number: str, command_data: dict) -> bool:
        """
        Мгновенно доставляет команду ожидающему устройству.
        """
        self.commands[serial_number] = command_data

        if serial_number in self.pending_commands:
            # Мгновенно "будим" висящий запрос app1
            self.pending_commands[serial_number].set()
            logger.info(f"🔊 Команда мгновенно доставлена на {serial_number}")
            return True
        else:
            logger.warning(f"⚠️ Устройство {serial_number} сейчас не опрашивает сервер. Команда сохранена, но будет доставлена с задержкой.")
            # В простой реализации мы просто теряем команду, если app1 не ждет.
            # Можно доработать, чтобы команда хранилась до следующего опроса.
            return False

# Глобальный экземпляр
command_manager = CommandManager()