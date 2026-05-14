import requests

from fastapi import APIRouter, status, Response

# API_URL = "http://10.168.143.7:8800/api"
API_URL = "http://localhost:8800/api"
headers = {
    "accept": "application/json",
    "Content-Type": "application/json"
}

START = 1
END = 11

# Словари ID для связки данных
location_id = []
software_id = []
asset_type_id = []
vendor_class_id = []
user_id = []
company_id = []
warehouse_id = []
vendor_id = []
class_id = []
model_id = []
asset_id = []
catalog_id = []

# === Независимые ===
def location_post():
    for i in range(START, END):
        json = {
            "country": f"Country {i}",
            "city": f"City {i}",
            "address": f"Address {i}",
            "room": f"Room {i}",
            "floor": f"Floor {i}"
        }
        response = requests.post(API_URL + "/locations", json=json, headers=headers)
        location_id.append(response.json().get("location_id"))
        print(f"{response.status_code} = {response.json()}")

def software_post():
    for i in range(START, END):
        json ={
            "admin_permission": False,
            "comment": f"ПО {i}",
            "installed_at": "2026-04-01T10:00:00",
            "office_key": f"{i}{i}{i}{i}",
            "office_type": f"Microsoft Office {i}",
            "os_key": f"{i}{i}{i}{i}",
            "os_type": f"Windows {i}{i}",
            "remote_control": f"TeamViewer {i}"
        }
        response = requests.post(API_URL + "/software", json=json, headers=headers)
        software_id.append(response.json().get("software_id"))
        print(f"{response.status_code} = {response.json()}")

def asset_types_post():
    for i in range(START, END):
        json = { "name": f"asset_type {i}"}
        response = requests.post(API_URL + "/assets-types", json=json, headers=headers)
        asset_type_id.append(response.json().get("asset_type_id"))
        print(f"{response.status_code} = {response.json()}")

def vendor_classes_post():
    for i in range(START, END):
        json = { "name": f"vendor_class {i}"}
        response = requests.post(API_URL + "/vendor-classes", json=json, headers=headers)
        vendor_class_id.append(response.json().get("vendor_class_id"))
        print(f"{response.status_code} = {response.json()}")

def users_post():
    # написать получение id locations, users
    for i in range(START, END):
        json = {
            "department": "IT-отдел",
            "email": f"{i}@company.com",
            "is_active": True,
            "owner": f"{i} Иванов Иван Иванович",
            "phone": "+7 (999) 123-45-67",
            "role": "user",
            "user_en_name": f"{i} Ivanov Ivan",
            "user_position": "Инженер",
            "user_tab_id": f"{i}"
        }
        response = requests.post(API_URL + "/users", json=json, headers=headers)
        user_id.append(response.json().get("user_id"))
        print(f"{response.status_code} = {response.json()}")

# === Одиночные зависимости ===
# Зависимость от Locations
def companies_post():
    for i in range(START, END):
        json = {
            "company_name": f"company_name {i}",
            "gen_director": f"gen_director {i}",
            "phone_number": f"phone_number {i}",
            "location_id": location_id[i-1]
        }
        response = requests.post(API_URL + "/companies", json=json, headers=headers)
        company_id.append(response.json().get("company_id"))
        print(f"{response.status_code} = {response.json()}")

def asset_classes_post():
    # написать получение id locations, users
    for i in range(START, END):
        json = {
            "class_name": f"class_name {i}",
            "class_type_id": asset_type_id[i-1],
            "description": f"description {i}",
            "created_by": user_id[i-1]
        }
        response = requests.post(API_URL + "/catalog/classes", json=json, headers=headers)
        class_id.append(response.json().get("class_id"))
        print(f"{response.status_code} = {response.json()}")

# === Двойные зависимости ===
# 2 Зависимость от location и users
def warehouses_post():
    # написать получение id locations, users
    for i in range(START, END):
        json = {
            "name": f"warehouses_name {i}",
            "location_id": location_id[i-1],
            "prepared_by": user_id[i-1]
        }
        response = requests.post(API_URL + "/warehouses", json=json, headers=headers)
        warehouse_id.append(response.json().get("warehouse_id"))
        print(f"{response.status_code} = {response.json()}")

def asset_models_post():
    # написать получение id locations, users
    for i in range(START, END):
        json = {
            "model_name": f"model_name {i}",
            "class_id": class_id[i-1],
            "description": "string",
            "is_active": True,
            "is_serial_required": True,
            "created_by": user_id[i-1]
        }
        response = requests.post(API_URL + "/catalog/models", json=json, headers=headers)
        model_id.append(response.json().get("model_id"))
        print(f"{response.status_code} = {response.json()}")

# === Тройная зависимость===
def vendors_post():
    for i in range(START, END):
        json = {
            "name": f"vendor {i}",
            "vendor_class_id": vendor_class_id[i-1],
            "company_id": company_id[i-1],
            "created_by": user_id[i-1]
        }
        response = requests.post(API_URL + "/vendors", json=json, headers=headers)
        vendor_id.append(response.json().get("vendor_id"))
        print(f"{response.status_code} = {response.json()}")

def assets_post():
    for i in range(START, END):
        json = {
            "asset_status": "Приемка",
            "asset_type_id": asset_type_id[i-1],
            "checked_by": user_id[i-1],
            "date_issue": "2026-04-01",
            "date_purchasing": "2026-03-15",
            "inventory_id": f"инвентарный номер {i}",
            "manufacturer_id": vendor_id[i-1],
            "name": f"имя {i}",
            "prepared_by": user_id[i-1],
            "price": i,
            "location_id": location_id[i-1],
            "software_id": software_id[i-1],
            "serial_number": f"серийный номер {i}",
            "vendor_id": vendor_id[i-1]
        }
        response = requests.post(f"{API_URL}/assets/?current_user_id={user_id[i-1]}", json=json, headers=headers)
        asset_id.append(response.json().get("asset_id"))
        print(f"{response.status_code} = {response.json()}")

def catalog_items_post():
    for i in range(START, END):
        json = {
            "class_id": class_id[i-1],
            "model_id": model_id[i-1],
            "asset_id": asset_id[i-1],
            "owner_id": user_id[i-1],
            "warehouse_id": warehouse_id[i-1],
            "warranty_end_date": "2026-04-22",
            "created_by": user_id[i-1]
        }

        response = requests.post(f"{API_URL}/catalog/items/?current_user_id={i}", json=json, headers=headers)
        catalog_id.append(response.json().get("catalog_id"))
        print(f"\n{response.status_code} = {response.json()}")


router_seed_api = APIRouter(tags=["API SEED"])

@router_seed_api.post("/seed", status_code=status.HTTP_201_CREATED)
def seed_api():
    """ Запускает посев данных во всех таблицах, по умолчанию 10 записей за 1 прогон"""
    # location_post()
    # software_post()
    asset_types_post()
    # vendor_classes_post()
    # users_post()
    # companies_post()
    # asset_classes_post()
    # warehouses_post()
    # asset_models_post()
    # vendors_post()
    # assets_post()
    # catalog_items_post()
    return Response(status_code=status.HTTP_204_NO_CONTENT)