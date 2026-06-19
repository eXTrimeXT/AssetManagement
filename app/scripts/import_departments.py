import asyncio
import sys
from pathlib import Path
import pandas as pd
import httpx

# Добавляем корень проекта в PATH
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


class DepartmentImporter:
    """Импорт подразделений через API-эндпоинты."""

    def __init__(self, base_url: str, token: str, excel_path: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        self.excel_path = excel_path
        self.departments_cache = {}  # abbreviation → id
        self.divisions_cache = {}    # abbreviation → id
        self.stats = {"created": 0, "skipped": 0, "errors": 0}

    async def _post(self, endpoint: str, data: dict) -> dict | None:
        """Отправка POST-запроса к эндпоинту."""
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, json=data, headers=self.headers)
                if response.status_code == 201:
                    return response.json()
                elif response.status_code == 400:
                    # Дубликат аббревиатуры
                    return None
                else:
                    print(f"⚠️ Ошибка {response.status_code}: {response.text}")
                    return None
            except httpx.RequestError as e:
                print(f"❌ Ошибка запроса: {e}")
                return None

    async def _get_parent_id(self, cache: dict, current_abbr: str) -> int | None:
        """Получение ID последнего созданного родителя из кэша."""
        # Ищем последний добавленный элемент в кэше (сохраняет порядок иерархии)
        for abbr in reversed(list(cache.keys())):
            return cache[abbr]
        return None

    async def import_row(self, name: str, gradation: str, abbreviation: str):
        """Обработка одной строки из Excel."""
        if not name or not abbreviation or abbreviation.lower() in ("nan", "none", ""):
            return
        if gradation not in ("Департамент", "Отдел", "Группа"):
            return

        try:
            if gradation == "Департамент":
                data = {"name": name, "abbreviation": abbreviation}
                result = await self._post("/departments/", data)
                if result:
                    self.departments_cache[abbreviation] = result["id"]
                    self.stats["created"] += 1
                    print(f"✅ Департамент: {abbreviation}")
                else:
                    # Проверяем, существует ли уже (возможно, создан ранее)
                    self.stats["skipped"] += 1
                    # Всё равно добавляем в кэш, если найдём через поиск (опционально)
                    print(f"⚠️ Департамент '{abbreviation}' уже существует или ошибка")

            elif gradation == "Отдел":
                parent_id = await self._get_parent_id(self.departments_cache, abbreviation)
                if not parent_id:
                    print(f"⚠️ Отдел '{abbreviation}' без родительского департамента — пропущен")
                    self.stats["skipped"] += 1
                    return

                data = {
                    "name": name,
                    "abbreviation": abbreviation,
                    "department_id": parent_id
                }
                result = await self._post("/divisions/", data)
                if result:
                    self.divisions_cache[abbreviation] = result["id"]
                    self.stats["created"] += 1
                    print(f"✅ Отдел: {abbreviation}")
                else:
                    self.stats["skipped"] += 1
                    print(f"⚠️ Отдел '{abbreviation}' уже существует или ошибка")

            elif gradation == "Группа":
                parent_id = await self._get_parent_id(self.divisions_cache, abbreviation)
                if not parent_id:
                    print(f"⚠️ Группа '{abbreviation}' без родительского отдела — пропущен")
                    self.stats["skipped"] += 1
                    return

                data = {
                    "name": name,
                    "abbreviation": abbreviation,
                    "division_id": parent_id
                }
                result = await self._post("/groups/", data)
                if result:
                    self.stats["created"] += 1
                    print(f"✅ Группа: {abbreviation}")
                else:
                    self.stats["skipped"] += 1
                    print(f"⚠️ Группа '{abbreviation}' уже существует или ошибка")

        except Exception as e:
            self.stats["errors"] += 1
            print(f"❌ Ошибка при обработке '{abbreviation}': {e}")

    async def run(self):
        """Запуск импорта."""
        # Чтение Excel
        df = pd.read_excel(self.excel_path, sheet_name="Лист_1", header=0)
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=["Наименование", "Градация", "Аббревиатура (Подразделения)"])
        df["Аббревиатура (Подразделения)"] = df["Аббревиатура (Подразделения)"].astype(str).str.strip()
        df["Наименование"] = df["Наименование"].astype(str).str.strip()
        df["Градация"] = df["Градация"].astype(str).str.strip()

        print(f"📄 Загружено строк: {len(df)}")
        print(f"🔗 API Base URL: {self.base_url}")

        for _, row in df.iterrows():
            await self.import_row(
                name=row["Наименование"],
                gradation=row["Градация"],
                abbreviation=row["Аббревиатура (Подразделения)"]
            )

        # Итоги
        print("\n" + "=" * 60)
        print(f"📊 ИТОГИ: создано={self.stats['created']}, пропущено={self.stats['skipped']}, ошибок={self.stats['errors']}")
        print("=" * 60)


async def main():
    importer = DepartmentImporter(
        # base_url="http://localhost:8800",
        base_url="http://10.168.143.7:8800",
        token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3Nzk2ODU3MDUsImV4cCI6MTc3OTcyODkwNSwibG9naW4iOiJndzA3MDE1MzcwIiwibGFzdF9pcCI6IjEwLjE2OC4xMzUuNjEiLCJsYXN0X3RpbWUiOiIxNDowMTo1MCAyMi4wNS4yMDI2IiwiZGVwYXJ0bWVudCI6bnVsbCwicGVybWlzc2lvbnMiOlt7Im5hbWVfZ3JvdXAiOiJjb21wdXRlciIsInJlYWQiOmZhbHNlLCJ3cml0ZSI6ZmFsc2V9LHsibmFtZV9ncm91cCI6Im1lc19lcXVpcG1lbnQiLCJyZWFkIjpmYWxzZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6InN1cHBsaWVzIiwicmVhZCI6dHJ1ZSwid3JpdGUiOmZhbHNlfSx7Im5hbWVfZ3JvdXAiOiJwb3dlcl9hZGFwdGVyIiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6ImRhdGFfY29sbGVjdGlvbl9lcXVpcG1lbnQiLCJyZWFkIjp0cnVlLCJ3cml0ZSI6dHJ1ZX0seyJuYW1lX2dyb3VwIjoiQWNjZXNzb3JpZXMiLCJyZWFkIjp0cnVlLCJ3cml0ZSI6dHJ1ZX0seyJuYW1lX2dyb3VwIjoibmV0d29ya19lcXVpcG1lbnQiLCJyZWFkIjp0cnVlLCJ3cml0ZSI6dHJ1ZX0seyJuYW1lX2dyb3VwIjoicHJpbnRpbmdfZXF1aXBtZW50IiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6InNlcnZlcl9oYXJkd2FyZSIsInJlYWQiOnRydWUsIndyaXRlIjp0cnVlfV0sInVzZXJfZGF0YSI6eyJlbWFpbCI6IlRpbXVyLk1hbHlzaGV2QGhtbXIucnUiLCJmdWxsbmFtZSI6IlRpbXVyIE1hbHlzaGV2IiwiZGVwYXJ0bWVudCI6IklTU1MiLCJkaXN0aW5ndWlzaGVkTmFtZSI6IkNOPVRpbXVyIE1hbHlzaGV2LE9VPUlORk9STUFUSU9OIFNZU1RFTVMgU1VQUE9SVCBTRUNUSU9OIChJU1NTKSxPVT1SdXNzaWFuIERpZ2l0YWwgQ2VudGVyIChSREMpLE9VPVVzZXJzLE9VPUhNTVIsREM9bG9jYWwsREM9aG1tcixEQz1ydSIsImdyb3VwcyI6W119fQ.vhPSQZxD0KxGq2KxjAe4g5b4IanWDfazj-IxgFpYR-8",
        excel_path="C:\\Users\\gw07015370\\projects\\python\\assetsmanagement\\xlsx\\Аббревиатуры подразделений.xlsx"
    )
    await importer.run()


if __name__ == "__main__":
    asyncio.run(main())