import httpx

async def get_user_cost_center_code(token: str) -> str | None:
    url = "http://gps-test.hmmr.ru/api/getinfouser"

    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Cookie": f"PHPSESSID=8s9909705lor036d1bppe54o85; lang=ru; token={token}",
        "DNT": "1",
        "Origin": "http://gps-test.hmmr.ru",
        "Referer": "http://gps-test.hmmr.ru/itassets/Store/10",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
        "X-KL-kes-Ajax-Request": "Ajax_Request",
        "X-Requested-With": "XMLHttpRequest"
    }

    # Отправляем как form-data, так как Content-Type: application/x-www-form-urlencoded
    payload = {"token": token}

    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(url, headers=headers, data=payload)
        response.raise_for_status()
        data = response.json()
        print(f"{data=}")

    # Ищем department_code, где read и write == true
    for perm in data.get("permission_departments", []):
        if perm.get("read") is True and perm.get("write") is True:
            return perm.get("department_code")

    return None