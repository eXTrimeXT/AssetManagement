import logging
import base64
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)

API_BASE_URL = "http://gps-test.hmmr.ru/api"


def get_public_key(session: requests.Session) -> dict:
    resp = session.get(f"{API_BASE_URL}/user_key")
    resp.raise_for_status()
    return resp.json()


def encrypt_password(password: str, pem_key: str) -> str:
    pub_key = serialization.load_pem_public_key(pem_key.encode(), backend=default_backend())
    encrypted = pub_key.encrypt(password.encode("utf-8"), padding.PKCS1v15())
    return base64.b64encode(encrypted).decode("utf-8")


def external_login(username: str, password: str) -> str:
    session = requests.Session()
    key = get_public_key(session)
    enc_pwd = encrypt_password(password, key['key'])

    resp = session.post(
        f"{API_BASE_URL}/user_auth",
        json={"login": username, "password": enc_pwd, 'id': key['id']},
        headers={"Content-Type": "application/json"}
    )
    resp.raise_for_status()

    data = resp.json()
    if data.get("status") != "success":
        logger.error(f"Ошибка авторизации: {data.get('msg')}")
        raise RuntimeError(f"Ошибка авторизации: {data.get('msg')}")
    return data["data"]["token"]