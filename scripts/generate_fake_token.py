import os
import jwt
import time
from dotenv import load_dotenv

load_dotenv()
SECRET = os.getenv("JWT_SECRET_KEY", "")
print(f"{SECRET=}")

now = int(time.time())
payload = {
    "iat": now,
    "exp": now + 365 * 24 * 60 * 60,  # 365 дней
    # "exp": now + 2 * 60,  # 365 дней
    "login": "gw07001905", # 00001905
    "last_ip": "10.168.154.42",
    "last_time": "12:47:52 21.07.2026",
    "department": "RDC",
    "permissions": [
        {"name_group": "computer", "read": True, "write": False},
        {"name_group": "mes_equipment", "read": False, "write": False},
        {"name_group": "supplies", "read": False, "write": False},
        {"name_group": "power_adapter", "read": False, "write": False},
        {"name_group": "data_collection_equipment", "read": False, "write": False},
        {"name_group": "Accessories", "read": False, "write": False},
        {"name_group": "network_equipment", "read": False, "write": False},
        {"name_group": "printing_equipment", "read": False, "write": False},
        {"name_group": "server_hardware", "read": False, "write": False},
        {"name_group": "users", "read": False, "write": False},
        {"name_group": "AssetsMU", "read": False, "write": False}
    ],
    "assets_admin": True,
    "user_data": {
        "email": "Tatiana.Moskvina@hmmr.ru",
        "fullname": "KE",
        "department": "SDG",
        "distinguishedName": "CN=KE,OU=SOFTWARE DEVELOPMENT GROUP (SDG),OU=INFORMATION SYSTEMS SUPPORT SECTION (ISSS),OU=Russian Digital Center (RDC),OU=Users,OU=HMMR,DC=local,DC=hmmr,DC=ru",
        "groups": []
    },
    "permission_departments": [
        {
            "name_group": "\u0410\u043a\u0442\u0438\u0432\u044b RDC",
            "read": True,
            "write": True,
            "department": "RDC",
            "department_code": "RU01050099"
        },
        {
            "name_group": "\u0410\u043a\u0442\u0438\u0432\u044b MSG",
            "read": True,
            "write": True,
            "department": "MSG",
            "department_code": "RU01050020"
        },
        {
            "name_group": "\u0410\u043a\u0442\u0438\u0432\u044b ",
            "read": True,
            "write": True,
            "department": None,
            "department_code": "RU01000098"
        }
    ],
}

token = jwt.encode(
    payload,
    key=SECRET,
    algorithm="HS256"
)
print(token)