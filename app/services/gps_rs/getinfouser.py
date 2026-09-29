from typing import List

import httpx

async def get_user_allowed_cost_centers(token: str) -> List[str]:
    url = "http://gps-test.hmmr.ru/api/getinfouser"
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(url, json={"token": token})
        response.raise_for_status()
        data = response.json()

    allowed_codes = []
    for perm in data.get("permission_departments", []):
        if perm.get("read") is True and perm.get("write") is True:
            code = perm.get("department_code")
            if code:
                allowed_codes.append(str(code).strip().upper())
    return allowed_codes