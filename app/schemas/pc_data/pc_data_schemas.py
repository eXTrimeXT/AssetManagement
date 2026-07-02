from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import List, Optional


class User(BaseModel):
    username: str
    userpath: str
    sid: str

class Network(BaseModel):
    line_speed_mbps: str
    ipv6_link_local: str
    ipv4_address: str
    default_gateway_ipv4: str
    dns_servers_ipv4: List[str]
    manufacturer: str
    description: str
    driver_version: str
    mac_address: str

class Os(BaseModel):
    os: str
    os_release: str
    os_version: str
    pc_arch: str
    pc_name: str
    device_type: str
    product_id: str
    device_id: str
    serial_number: str

class Cpu(BaseModel):
    name: str
    cores: int
    processors: int
    speed: str

class Ram(BaseModel):
    total: str
    sticks: List[str]

class Gpu(BaseModel):
    name: str
    vram: str
    driver: str

class Disk(BaseModel):
    model: str
    size: str
    interface: str

class Components(BaseModel):
    cpu: Cpu
    motherboard: str
    ram: Ram
    gpu: List[Gpu]
    disks: List[Disk]

class PCDataCreate(BaseModel):
    user: User
    network: Network
    os: Os
    components: Components
    office_package: List[str]
    programs: List[str]
    updated_at: datetime

class PCDataResponse(PCDataCreate):
    id: int
    # user_id: Optional[int] = None
    user_tab_id: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)