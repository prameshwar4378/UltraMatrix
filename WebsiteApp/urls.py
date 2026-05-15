from django.urls import path
from . import views

urlpatterns = [
    path("features/", views.features, name="website_features"), 
    path("ai_engine/", views.ai_engine, name="website_ai_engine"),
    path("pricing/", views.pricing, name="website_pricing"),
    path("contact-us/", views.contact_us, name="contact_us"),
]
