from typing import List, Dict, Any

# Реестр системных пользователей и их прав
# Используется для быстрого определения, является ли пользователь системным
SYSTEM_USERS: Dict[str, List[Dict[str, Any]]] = {
    "root": [
        {"name_group": "computer", "read": True, "write": True},
        {"name_group": "mes_equipment", "read": True, "write": True},
        {"name_group": "supplies", "read": True, "write": True},
        {"name_group": "power_adapter", "read": True, "write": True},
        {"name_group": "data_collection_equipment", "read": True, "write": True},
        {"name_group": "Accessories", "read": True, "write": True},
        {"name_group": "network_equipment", "read": True, "write": True},
        {"name_group": "printing_equipment", "read": True, "write": True},
        {"name_group": "server_hardware", "read": True, "write": True},
        {"name_group": "users", "read": True, "write": True},
        {"name_group": "AssetsMS", "read": True, "write": True},
        {"name_group": "android_data", "read": True, "write": True},
        {"name_group": "pc_data", "read": True, "write": True},
    ],
    "read_only": [
        {"name_group": "computer", "read": True, "write": False},
        {"name_group": "mes_equipment", "read": True, "write": False},
        {"name_group": "supplies", "read": True, "write": False},
        {"name_group": "power_adapter", "read": True, "write": False},
        {"name_group": "data_collection_equipment", "read": True, "write": False},
        {"name_group": "Accessories", "read": True, "write": False},
        {"name_group": "network_equipment", "read": True, "write": False},
        {"name_group": "printing_equipment", "read": True, "write": False},
        {"name_group": "server_hardware", "read": True, "write": False},
        {"name_group": "users", "read": True, "write": False},
        {"name_group": "AssetsMS", "read": True, "write": False},
        {"name_group": "android_data", "read": True, "write": False},
        {"name_group": "pc_data", "read": True, "write": False},
    ],
    "write_only": [
        {"name_group": "computer", "read": False, "write": True},
        {"name_group": "mes_equipment", "read": False, "write": True},
        {"name_group": "supplies", "read": False, "write": True},
        {"name_group": "power_adapter", "read": False, "write": True},
        {"name_group": "data_collection_equipment", "read": False, "write": True},
        {"name_group": "Accessories", "read": False, "write": True},
        {"name_group": "network_equipment", "read": False, "write": True},
        {"name_group": "printing_equipment", "read": False, "write": True},
        {"name_group": "server_hardware", "read": False, "write": True},
        {"name_group": "users", "read": False, "write": True},
        {"name_group": "AssetsMS", "read": False, "write": True},
        {"name_group": "android_data", "read": False, "write": True},
        {"name_group": "pc_data", "read": False, "write": True},
    ],
    "android_data": [
        {"name_group": "android_data", "read": True, "write": True}
    ],
    "pc_data": [
        {"name_group": "pc_data", "read": True, "write": True}
    ]
}

class MockSystemEmployee:
    """
    Легковесный объект, имитирующий Employee для системных пользователей.
    Системные пользователи — "призраки", их нет в таблице zup_employees.
    """
    def __init__(self, login: str):
        self.employee_id = login  # "root", "read_only", и т.д.
        self.login = login
        self.email = f"{login}@system.local"
        self.dismissal_date = None  # Системные пользователи не увольняются
        self.guid = f"system-{login}"
        self.last_name = "System"
        self.first_name = login

    @property
    def full_name_ru(self) -> str:
        return f"System {self.login}"

    @property
    def full_name_en(self) -> str:
        return f"System {self.login}"