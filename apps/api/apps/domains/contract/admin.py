from django.contrib import admin

from .models import Contract, ContractTemplate


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ["title", "signer_name", "status", "created_at"]
    readonly_fields = [field.name for field in Contract._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(ContractTemplate)
