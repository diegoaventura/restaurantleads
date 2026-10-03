"""All ORM models — importing this module registers every table on Base.metadata."""

from app.models.ai_generation import AIGeneration
from app.models.contact import Contact
from app.models.delivery_presence import DeliveryPresence
from app.models.follow_up import FollowUp
from app.models.interaction import Interaction
from app.models.lead import Lead
from app.models.restaurant import Restaurant
from app.models.restaurant_source import RestaurantSource
from app.models.user import User

__all__ = [
    "AIGeneration",
    "Contact",
    "DeliveryPresence",
    "FollowUp",
    "Interaction",
    "Lead",
    "Restaurant",
    "RestaurantSource",
    "User",
]
