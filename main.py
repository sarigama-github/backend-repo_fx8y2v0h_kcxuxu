import os
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Barber, Service, Appointment

app = FastAPI(title="Barbershop Booking API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helpers

def oid(oid_str: str) -> ObjectId:
    try:
        return ObjectId(oid_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")


def to_public(doc):
    if not doc:
        return doc
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    # Convert datetime to iso
    for k, v in list(doc.items()):
        if hasattr(v, "isoformat"):
            doc[k] = v.isoformat()
    return doc


# Seed endpoint to insert some default barbers and services if empty
@app.post("/seed")
def seed_data():
    if db is None:
        raise HTTPException(500, detail="Database not configured")

    if db["barber"].count_documents({}) == 0:
        barbers = [
            Barber(name="علی", specialties=["کوتاهی", "خط ریش"], phone="09120000001"),
            Barber(name="مهدی", specialties=["فید", "ریش"], phone="09120000002"),
        ]
        for b in barbers:
            create_document("barber", b)

    if db["service"].count_documents({}) == 0:
        services = [
            Service(title="کوتاهی مو", duration_minutes=30, price=200000),
            Service(title="اصلاح ریش", duration_minutes=20, price=120000),
            Service(title="پکیج کامل", duration_minutes=60, price=350000),
        ]
        for s in services:
            create_document("service", s)

    return {"message": "Seeded"}


# Public listing endpoints
@app.get("/barbers")
def list_barbers():
    items = get_documents("barber")
    return [to_public(d) for d in items]


@app.get("/services")
def list_services():
    items = get_documents("service")
    return [to_public(d) for d in items]


# Availability calculation
class AvailabilityResponse(BaseModel):
    date: str
    slots: List[str]


def time_range(start: datetime, end: datetime, step_min: int):
    t = start
    while t + timedelta(minutes=step_min) <= end:
        yield t
        t += timedelta(minutes=step_min)


@app.get("/availability", response_model=AvailabilityResponse)
def availability(
    barber_id: str = Query(...),
    date: str = Query(..., description="YYYY-MM-DD"),
):
    bdoc = db["barber"].find_one({"_id": oid(barber_id)})
    if not bdoc:
        raise HTTPException(404, detail="Barber not found")

    # Working hours
    start_h, start_m = map(int, bdoc.get("start_time", "09:00").split(":"))
    end_h, end_m = map(int, bdoc.get("end_time", "20:00").split(":"))
    slot_min = int(bdoc.get("slot_minutes", 30))

    day = datetime.strptime(date, "%Y-%m-%d")
    start_dt = day.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    end_dt = day.replace(hour=end_h, minute=end_m, second=0, microsecond=0)

    # Fetch existing appointments for the day
    apps = list(db["appointment"].find({"barber_id": barber_id, "date": date, "status": "scheduled"}))
    taken_times = set(a["time"] for a in apps)

    slots = []
    for t in time_range(start_dt, end_dt, slot_min):
        st = t.strftime("%H:%M")
        if st not in taken_times:
            slots.append(st)

    return AvailabilityResponse(date=date, slots=slots)


# Booking endpoint
class CreateAppointment(BaseModel):
    barber_id: str
    service_id: str
    customer_name: str
    customer_phone: str
    date: str
    time: str
    notes: Optional[str] = None


@app.post("/appointments")
def create_appointment(payload: CreateAppointment):
    # Validate barber and service exist
    if not db["barber"].find_one({"_id": oid(payload.barber_id)}):
        raise HTTPException(404, detail="Barber not found")
    sdoc = db["service"].find_one({"_id": oid(payload.service_id)})
    if not sdoc:
        raise HTTPException(404, detail="Service not found")

    # Ensure slot free
    exists = db["appointment"].find_one({
        "barber_id": payload.barber_id,
        "date": payload.date,
        "time": payload.time,
        "status": "scheduled",
    })
    if exists:
        raise HTTPException(409, detail="این زمان قبلا رزرو شده است")

    appo = Appointment(**payload.model_dump(), status="scheduled")
    new_id = create_document("appointment", appo)
    return {"id": new_id, "message": "نوبت با موفقیت ثبت شد"}


@app.get("/appointments")
def list_appointments(barber_id: Optional[str] = None, date: Optional[str] = None):
    q = {}
    if barber_id:
        q["barber_id"] = barber_id
    if date:
        q["date"] = date
    docs = list(db["appointment"].find(q).sort("created_at", -1))
    return [to_public(d) for d in docs]


@app.delete("/appointments/{appointment_id}")
def cancel_appointment(appointment_id: str):
    res = db["appointment"].update_one({"_id": oid(appointment_id)}, {"$set": {"status": "cancelled", "updated_at": datetime.utcnow()}})
    if res.matched_count == 0:
        raise HTTPException(404, detail="Appointment not found")
    return {"message": "نوبت لغو شد"}


@app.get("/")
def root():
    return {"name": "Barbershop API", "endpoints": ["/barbers", "/services", "/availability", "/appointments"]}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected"
            response["collections"] = db.list_collection_names()
        else:
            response["database"] = "❌ Not Configured"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
