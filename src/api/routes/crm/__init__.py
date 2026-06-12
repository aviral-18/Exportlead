from fastapi import APIRouter
from src.api.routes.crm import (
    contacts, followups, history, leads,
    notes, opportunities, purchase_orders, quotations, samples,
)

router = APIRouter(prefix="/crm", tags=["CRM"])
router.include_router(leads.router)
router.include_router(contacts.router)
router.include_router(history.router)
router.include_router(notes.router)
router.include_router(followups.router)
router.include_router(opportunities.router)
router.include_router(samples.router)
router.include_router(quotations.router)
router.include_router(purchase_orders.router)
