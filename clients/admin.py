from django.contrib import admin
from .models import ClientOrganization, ClientContact

class ContactInline(admin.TabularInline):
    model = ClientContact
    extra = 1

@admin.register(ClientOrganization)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'industry', 'email', 'phone', 'status', 'open_tickets', 'user')
    list_filter = ('industry', 'status')
    search_fields = ('name', 'email', 'tax_id')
    inlines = [ContactInline]
