import requests
import base64
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5

# --- НАСТРОЙКИ ---
BASE_URL = "http://gps-test.hmmr.ru/api"
LOGIN = "gw07015370"
PASSWORD_PLAIN = "Extremehavalworkit!1"

def get_public_key():
    """Шаг 1: Получаем публичный ключ с сервера"""
    try:
        print(f"[1] Запрос ключа: {BASE_URL}/getkey")
        resp = requests.get(f"{BASE_URL}/getkey")
        resp.raise_for_status()
        key_text = resp.text.strip()
        print("[OK] Ключ получен.")
        return key_text
    except Exception as e:
        print(f"[ERROR] Не удалось получить ключ: {e}")
        return None

def encrypt_rsa_pkcs1(public_key_pem, text_to_encrypt):
    """
    Шаг 2: Шифруем данные используя RSA-ECB-PKCS1padding.
    В библиотеке pycryptodome это реализуется через PKCS1_v1_5.
    """
    try:
        # Импортируем ключ из PEM-строки
        rsa_key = RSA.import_key(public_key_pem)

        # Создаем шифр. PKCS1_v1_5 соответствует стандарту PKCS#1 v1.5 padding.
        # RSA по умолчанию работает в режиме ECB (блок за блоком),
        # но для публичного ключа это стандартное поведение при шифровании.
        cipher = PKCS1_v1_5.new(rsa_key)
        print("Зашифрованн")

        # Данные должны быть в байтах
        data_bytes = text_to_encrypt.encode('utf-8')

        # Шифрование
        encrypted_bytes = cipher.encrypt(data_bytes)

        # Конвертируем результат в Base64 для безопасной передачи в JSON
        encrypted_b64 = base64.b64encode(encrypted_bytes).decode('utf-8')

        return encrypted_b64
    except Exception as e:
        print(f"[ERROR] Ошибка шифрования: {e}")
        return None

def login(login, encrypted_password):
    """Шаг 3: Отправляем POST запрос с токеном"""
    url = f"{BASE_URL}/login"

    payload = {
        "login": login,
        "password": encrypted_password  # Сюда кладем зашифрованную строку
    }

    try:
        print(f"[2] Авторизация: {url}")
        # requests автоматически сериализует dict в JSON и ставит Content-Type: application/json
        resp = requests.post(url, json=payload)

        # Выводим сырой ответ для отладки, если что-то не так
        if resp.status_code != 200:
            print(f"[WARN] HTTP Code: {resp.status_code}")
            print(f"[RESPONSE] {resp.text}")

        resp.raise_for_status()

        data = resp.json()
        return data
    except Exception as e:
        print(f"[ERROR] Ошибка авторизации: {e}")
        return None

def main():
    print("--- Начало процесса авторизации ---")

    # 1. Получаем ключ
    pub_key = get_public_key()
    if not pub_key:
        return

    # 2. Шифруем пароль
    # Важно: шифруем именно исходный пароль, а не хеш или что-то еще
    enc_pass = encrypt_rsa_pkcs1(pub_key, PASSWORD_PLAIN)
    if not enc_pass:
        return

    # Для проверки можно вывести длину зашифрованной строки
    print(f"[INFO] Длина зашифрованного пароля (Base64): {len(enc_pass)} симв.")

    # 3. Логинимся
    result = login(LOGIN, enc_pass)

    if result:
        print("\n--- УСПЕШНЫЙ ОТВЕТ ---")
        print(result)

        # Извлекаем токен, если он есть
        if result.get("status") == "success" and "data" in result:
            token = result["data"].get("token")
            if token:
                print(f"\nВАШ ТОКЕН ДЛЯ ЗАПРОСОВ:\n{token}")
    else:
        print("\n--- АВТОРИЗАЦИЯ НЕ УДАЛАСЬ ---")

if __name__ == "__main__":
    main()