from fastapi import APIRouter

from app.api.v1 import (
    aftersales, attachment, auth, cart, catalog, channel, customer, fulfillment, inventory, invoice, order,
    payment, refund, report, staff, webhooks,
)
from app.api.v1 import assistant
from app.api.v1 import knowledge
from app.api.v1 import ontology

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(attachment.router)
api_router.include_router(staff.router)
api_router.include_router(channel.router)
api_router.include_router(channel.public_router)
api_router.include_router(catalog.router)
api_router.include_router(inventory.router)
api_router.include_router(customer.router)
api_router.include_router(cart.router)
api_router.include_router(order.router)
api_router.include_router(payment.router)
api_router.include_router(fulfillment.router)
api_router.include_router(aftersales.router)
api_router.include_router(refund.router)
api_router.include_router(invoice.router)
api_router.include_router(report.router)
api_router.include_router(webhooks.router)
api_router.include_router(knowledge.router)
api_router.include_router(ontology.router)
api_router.include_router(assistant.router)
