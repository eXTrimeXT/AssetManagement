# import asyncio
# import os
# import json
# import httpx
# from dotenv import load_dotenv
# from typing import Optional, Dict, Any
#
# from app.schemas.assets.AssetSchemas import AssetResponse
#
# load_dotenv()
# AI_AGENT_TOKEN = os.getenv("AI_AGENT_TOKEN")
#
# async def send_agent_request(content: str) -> str | None:
#     url = "https://hiagent.gwm.cn/api/aigw/v1/chat/completions"
#
#     headers = {
#         "Authorization": f"Bearer {AI_AGENT_TOKEN}"
#     }
#
#     json = {
#         "model": "d7uk27hun0790uk9jrvg",
#         "messages": [
#             {
#                 "role": "user",
#                 "content": content
#             }
#         ],
#         "thinking": {
#             "type": "enable"
#         }
#     }
#
#     async with httpx.AsyncClient(verify=False) as client:
#         response = await client.post(url, headers=headers, json=json)
#         response.raise_for_status()
#         data = response.json()
#
#         answer: str = data.get("choices")[0].get("message").get("content")
#         answer = answer.replace('**', '').replace('«', '').replace('»', '').strip()
#
#         # Гарантированная очистка от markdown-оберток ```json ... ```
#         if answer.startswith("```json"):
#             answer = answer[7:]
#         if answer.startswith("```"):
#             answer = answer[3:]
#         if answer.endswith("```"):
#             answer = answer[:-3]
#
#         answer = answer.strip()
#         print(answer)
#         return answer or None
#
# async def addon_asset_by_agent(asset: AssetResponse) -> Dict[str, Any]:
#     asset_dict = asset.model_dump() if hasattr(asset, 'model_dump') else asset.dict()
#
#     prompt = f"""
# Есть данные актива:
# {json.dumps(asset_dict, ensure_ascii=False, indent=2)}
#
# Определи и заполни поля, которые можно извлечь из названия (name) или других доступных данных:
# - model_name (модель)
# - manufacturer_name (производитель)
# - asset_type_name (тип актива, например: Ноутбук, Монитор, Принтер, Сетевое оборудование и т.д.)
# - os_name (операционная система, если применимо)
#
# Ответь строго в формате json без доп символов (```json ).
# Хорошо подумай перед ответом. Если поле не удается определить, оставь его null.
# """
#
#     response_text = await send_agent_request(prompt)
#     if not response_text:
#         return asset_dict
#
#     try:
#         updated_asset = json.loads(response_text)
#         return updated_asset
#     except json.JSONDecodeError as e:
#         print(f"Ошибка парсинга JSON от AI агента: {e}")
#         return asset_dict


import os
import json
import httpx
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List

from app.schemas.assets.AssetSchemas import AssetResponse

load_dotenv()
AI_AGENT_TOKEN = os.getenv("AI_AGENT_TOKEN")

async def send_agent_request(content: str) -> Optional[str]:
    url = "https://hiagent.gwm.cn/api/aigw/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {AI_AGENT_TOKEN}"
    }

    payload = {
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
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        answer: str = data.get("choices")[0].get("message").get("content")
        answer = answer.replace('**', '').replace('«', '').replace('»', '').strip()

        # Гарантированная очистка от markdown-оберток
        if answer.startswith("```json"):
            answer = answer[7:]
        if answer.startswith("```"):
            answer = answer[3:]
        if answer.endswith("```"):
            answer = answer[:-3]

        answer = answer.strip()
        print(answer)
        return answer or None

async def addon_asset_by_agent(asset: AssetResponse, asset_types_list: List[str]) -> Dict[str, Any]:
    asset_dict = asset.model_dump() if hasattr(asset, 'model_dump') else asset.dict()

    # Формируем строку со списком типов для промпта
    types_str = ", ".join([f'"{t}"' for t in asset_types_list])

    prompt = f"""
Есть данные актива:
{json.dumps(asset_dict, ensure_ascii=False, indent=2)}

Доступные типы активов (asset_type_name) в системе:
[{types_str}]

Определи и заполни поля, которые можно извлечь из названия (name) или других доступных данных:
- model_name (модель)
- manufacturer_name (производитель)
- asset_type_name (тип актива). Выбери строго один из доступных типов активов, указанных выше. Если точного совпадения нет, выбери наиболее подходящий по смыслу.
- os_name (операционная система, если применимо)

Ответь строго в формате json без доп символов (```json ).
Хорошо подумай перед ответом. Если поле не удается определить, оставь его null.
"""

    response_text = await send_agent_request(prompt)
    if not response_text:
        return asset_dict

    try:
        updated_asset = json.loads(response_text)
        return updated_asset
    except json.JSONDecodeError as e:
        print(f"Ошибка парсинга JSON от AI агента: {e}")
        return asset_dict