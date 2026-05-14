from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import School 
from Accounts.models import SchoolUser

admin.site.register(School)
admin.site.register(SchoolUser)