import asyncio
import os
import httpx
from dotenv import load_dotenv

from app.schemas.assets import AssetResponse

load_dotenv()
AI_AGENT_TOKEN = os.getenv("AI_AGENT_TOKEN")

# Функция любого запроса для ИИ
async def send_agent_request(content: str) -> str | None:
    url = "https://hiagent.gwm.cn/api/aigw/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {AI_AGENT_TOKEN}"
    }

    json = {
        "model": "d7uk27hun0790uk9jrvg",
        "messages": [
            {
                "role": "user",
                "content": content
            }
        ],
        "thinking": {
            "type": "enable"
        }
    }

    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(url, headers=headers, json=json)
        response.raise_for_status()
        data = response.json()

        answer: str = data.get("choices")[0].get("message").get("content")
        answer = answer.replace('**', '').replace('«', '').replace('»', '')
        print(answer)
        return answer or None

# TEST
query = """
Есть список:
  {
  "items": [
    {
      "name": "Ноутбук 15.6\" MSI Modern 15 F13MG",
      "inventory_id": "100000004480",
      "serial_number": null,
      "asset_status": "На складе",
      "asset_status_id": 9,
      "quantity": 1,
      "comment": null,
      "date_issue": null,
      "date_purchasing": null,
      "model_id": null,
      "model_name": null,
      "asset_type_id": 0,
      "parent_id": null,
      "every_week_check": false,
      "next_service": null,
      "service_period": 0,
      "check_period": 0,
      "parent_name": null,
      "manufacturer_name": null,
      "vendor_name": null,
      "os_name": null,
      "asset_id": null,
      "material_id": "1000000044800000",
      "created_by": null,
      "updated_by": null,
      "created_at": null,
      "updated_at": null,
      "asset_type_name": "Без типа",
      "location": null,
      "users": [],
      "cost_center_code_from": "RU01050011",
      "cost_center_name_from": "#Отдел сопровождения базовых сервисо",
      "cost_center_shortname_from": null,
      "cost_center_code": "RU01050011",
      "cost_center_name": "#Отдел сопровождения базовых сервисо",
      "cost_center_shortname": null,
      "serving_users": [],
      "current_user": null,
      "current_user_full_name": null,
      "parent": null
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50,
  "total_pages": 1,
  "has_next": false,
  "has_previous": false
}

Определи и заполни поля, которые содержаться там model_name - это модель, manufacturer_name - производитель. И верни этот массив

Ответь строго в формате json без доп символов (```json )
Хорошо подумай перед ответом
"""

asyncio.run(send_agent_request(query))

async def addon_asset_by_agent(asset: AssetResponse):
    prompt = ""