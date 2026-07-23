from pydantic import BaseModel, ConfigDict
from typing import Optional

class DeviceInfo(BaseModel):
    model: str
    name: str

class SystemInfo(BaseModel):
    android_version: str
    android_api_version: str
    build_number: str
    language: str
    timezone: str
    uptime: str


class HardwareInfo(BaseModel):
    processor: str
    processor_architecture: str
    ram_total: str
    ram_free: str
    storage_total: str
    storage_free: str
    cameras: str
    screen_resolution: str

class NetworkInfo(BaseModel):
    connection_type: str
    wifi_ssid: Optional[str] = None
    wifi_bssid: Optional[str] = None
    wifi_gateway: Optional[str] = None
    mac_address: Optional[str] = None
    ip_addresses: Optional[str] = None
    bluetooth: Optional[str] = None

class BatteryInfo(BaseModel):
    level: str
    status: str
    temperature: str

class AndroidDataCreate(BaseModel):
    serial_number: str
    request_time: str
    device: DeviceInfo
    system: SystemInfo
    hardware: HardwareInfo
    network: NetworkInfo
    battery: BatteryInfo

class AndroidDataResponse(AndroidDataCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)