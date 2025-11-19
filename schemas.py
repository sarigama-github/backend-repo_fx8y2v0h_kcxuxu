"""
Database Schemas for Barbershop Booking System

Each Pydantic model represents a MongoDB collection.
Collection name is the lowercase of the class name.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal

class Barber(BaseModel):
    """
    Collection: "barber"
    """
    name: str = Field(..., description="Barber full name")
    specialties: List[str] = Field(default_factory=list, description="List of specialties (fade, beard, kids, etc.)")
    phone: Optional[str] = Field(None, description="Contact phone")
    photo_url: Optional[str] = Field(None, description="Profile image URL")
    working_days: List[str] = Field(default_factory=lambda: ["sat", "sun", "mon", "tue", "wed"], description="Working days (sat..fri)")
    start_time: str = Field("09:00", description="Workday start HH:MM 24h")
    end_time: str = Field("20:00", description="Workday end HH:MM 24h")
    slot_minutes: int = Field(30, ge=10, le=240, description="Default slot size in minutes")

class Service(BaseModel):
    """
    Collection: "service"
    """
    title: str = Field(..., description="Service name (e.g., Haircut)")
    duration_minutes: int = Field(30, ge=10, le=240, description="Duration in minutes")
    price: float = Field(0, ge=0, description="Price amount")
    description: Optional[str] = Field(None, description="Optional description")

class Customer(BaseModel):
    """
    Collection: "customer"
    """
    name: str
    phone: str
    email: Optional[str] = None

class Appointment(BaseModel):
    """
    Collection: "appointment"
    """
    barber_id: str = Field(..., description="Barber document id as string")
    service_id: str = Field(..., description="Service document id as string")
    customer_name: str
    customer_phone: str
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD")
    time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="HH:MM 24h start time")
    status: Literal["scheduled", "cancelled"] = Field("scheduled")
    notes: Optional[str] = None
