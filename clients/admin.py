from django.contrib import admin
from .models import ClientOrganization, ClientContact

class ContactInline(admin.TabularInline):
    model = ClientContact
    extra = 1

@admin.register(ClientOrganization)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'industry', 'email', 'phone', 'is_active', 'open_tickets')
    list_filter = ('industry', 'is_active')
    search_fields = ('name', 'email')
    inlines = [ContactInline]
