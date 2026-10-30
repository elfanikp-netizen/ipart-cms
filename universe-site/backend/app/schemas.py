from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VehicleFields(BaseModel):
    year: int = Field(ge=1886, le=2100)
    make: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=150)
    notes: str = Field(default="", max_length=4000)


class VehicleCreate(VehicleFields):
    pass


class VehicleUpdate(VehicleFields):
    pass


class VehicleOut(VehicleFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    vin_count: int = 0


class VehicleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    year: int
    make: str
    model: str


class VinFields(BaseModel):
    id_vehicle: int
    vin: str = Field(min_length=1, max_length=32)
    notes: str = Field(default="", max_length=4000)


class VinCreate(VinFields):
    pass


class VinUpdate(VinFields):
    pass


class VinOut(VinFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle: VehicleSummary
    created_at: datetime
    updated_at: datetime


class OemOut(BaseModel):
    id: int
    id_vin: int
    oem: str
    description: str
    notes: str
    vin: str
    year: int
    make: str
    model: str
    created_at: datetime
    updated_at: datetime


class OemFields(BaseModel):
    id_vin: int
    oem: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=4000)
    notes: str = Field(default="", max_length=4000)


class OemCreate(OemFields):
    pass


class OemUpdate(OemFields):
    pass


class OemImportOut(BaseModel):
    vehicles_created: int = 0
    vins_created: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class PageOut(BaseModel):
    items: list
    page: int
    page_size: int
    total: int
    pages: int


class ImportOut(BaseModel):
    vehicles_created: int = 0
    vehicles_updated: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class CccMarketRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    oem: str
    vin: str
    crawl_date: datetime
    market_index: int
    description: str
    vendor: str
    market_data: dict | list
    created_at: datetime
    updated_at: datetime


class CccMarketGroupOut(BaseModel):
    oem: str
    vin: str
    crawl_date: datetime


class CccMarketPageOut(BaseModel):
    items: list[CccMarketGroupOut]
    page: int
    page_size: int
    total: int
    pages: int


class ActivityOut(BaseModel):
    id: int
    user_id: int | None
    username: str
    action: str
    detail: str
    created_at: datetime


class ActivityPageOut(BaseModel):
    items: list[ActivityOut]
    page: int
    page_size: int
    total: int
    pages: int