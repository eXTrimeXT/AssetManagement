import requests
from typing import List, Dict

# Конфигурация
# API_BASE_URL = "http://localhost:8800/api"
API_BASE_URL = "http://10.168.143.7:8800/api"
LOGIN = "root"
PASSWORD = "root"

# Данные типов активов
ASSET_TYPES_DATA: List[Dict[str, str]] = [
    {
        "name": "Компьютер",
        "en_name": "computer"
    },
    {
        "name": "MES оборудование",
        "en_name": "mes_equipment"
    },
    {
        "name": "Расходные материалы",
        "en_name": "supplies"
    },
    {
        "name": "Адаптер питания",
        "en_name": "power_adapter"
    },
    {
        "name": "Оборудование сбора данных",
        "en_name": "data_collection_equipment"
    },
    {
        "name": "Комплектующие",
        "en_name": "Accessories"
    },
    {
        "name": "Сетевое оборудование",
        "en_name": "network_equipment"
    },
    {
        "name": "Печатное оборудование",
        "en_name": "printing_equipment"
    },
    {
        "name": "Серверное оборудование",
        "en_name": "server_hardware"
    }
]


def get_auth_token() -> str:
    """Получает токен авторизации"""
    login_url = f"{API_BASE_URL}/login"
    response = requests.post(
        login_url,
        json={"login": LOGIN, "password": PASSWORD}
    )

    if response.status_code == 200:
        data = response.json()
        return data.get("token", "")
    else:
        raise Exception(f"Ошибка авторизации: {response.status_code} - {response.text}")


def create_asset_type(token: str, asset_type_data: Dict[str, str]) -> Dict:
    """Создает один тип актива"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    url = f"{API_BASE_URL}/assets-types/"
    response = requests.post(url, json=asset_type_data, headers=headers)

    return {
        "status_code": response.status_code,
        "data": asset_type_data,
        "response": response.json() if response.status_code == 201 else response.text,
        "success": response.status_code == 201
    }


def main():
    print("🚀 Начинаю создание типов активов...\n")

    # 1. Получаем токен
    try:
        token = get_auth_token()
        print(f"✅ Авторизация успешна (токен получен)\n")
    except Exception as e:
        print(f"❌ Ошибка авторизации: {e}")
        return

    # 2. Создаем типы активов
    success_count = 0
    error_count = 0

    for i, asset_type in enumerate(ASSET_TYPES_DATA, 1):
        print(f"[{i}/{len(ASSET_TYPES_DATA)}] Создание: {asset_type['name']}...", end=" ")

        try:
            result = create_asset_type(token, asset_type)

            if result["success"]:
                print("✅ Успешно")
                success_count += 1
            else:
                print(f"❌ Ошибка {result['status_code']}")
                error_count += 1
                print(f"   Ответ: {result['response']}")

        except Exception as e:
            print(f"❌ Исключение: {e}")
            error_count += 1

    # 3. Итоги
    print("\n" + "="*50)
    print(f"📊 Результаты:")
    print(f"   ✅ Успешно создано: {success_count}")
    print(f"   ❌ Ошибок: {error_count}")
    print(f"   📝 Всего: {len(ASSET_TYPES_DATA)}")
    print("="*50)


if __name__ == "__main__":
    main()