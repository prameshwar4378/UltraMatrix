"""
URL configuration for AI_TIMETABLE_SAAS project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static
from WebsiteApp.views import index

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('Accounts.urls')),
    path('', index, name='index'),
    path('', include('WebsiteApp.urls')),
    path('', include('Schools.urls')),
    path("", include("Academic.urls")),
    path("", include("Classes.urls")),
    path("", include("Teachers.urls")),
    path("", include("Subjects.urls")),
    path("", include("Rooms.urls")),
    path("", include("Timetables.urls")),
    path("", include("Timetables.builder_urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
