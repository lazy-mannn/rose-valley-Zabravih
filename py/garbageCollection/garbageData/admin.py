from django.contrib import admin
from .models import TrashCan, FillRecord, APIKey

@admin.register(TrashCan)
class TrashCanAdmin(admin.ModelAdmin):
    list_display = ('id', 'nfc_uid', 'latitude', 'longitude', 'last_emptied')
    search_fields = ('id', 'nfc_uid')
    ordering = ('id',)
    readonly_fields = ('last_emptied',)
    
    fieldsets = (
        ('Bin Information', {
            'fields': ('id', 'latitude', 'longitude')
        }),
        ('NFC Tag', {
            'fields': ('nfc_uid',),
            'description': 'Paste the NFC tag UID here (e.g., 123456789)'
        }),
        ('Status', {
            'fields': ('last_emptied',),
            'classes': ('collapse',)
        }),
    )

@admin.register(FillRecord)
class FillRecordAdmin(admin.ModelAdmin):
    list_display = ('trashcan', 'fill_level', 'source', 'timestamp')
    list_filter = ('source', 'timestamp', 'trashcan')
    search_fields = ('trashcan__id', 'trashcan__nfc_uid')
    ordering = ('-timestamp',)
    readonly_fields = ('timestamp',)

@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('device_name', 'is_active', 'created_at', 'last_used', 'key_preview')
    list_filter = ('is_active', 'created_at', 'last_used')
    search_fields = ('device_name', 'description', 'key')
    readonly_fields = ('key', 'created_at', 'last_used')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Device Information', {
            'fields': ('device_name', 'description', 'is_active')
        }),
        ('API Key', {
            'fields': ('key',),
            'classes': ('collapse',),
            'description': 'API key is generated automatically. Keep this secure!'
        }),
        ('Usage Statistics', {
            'fields': ('created_at', 'last_used'),
            'classes': ('collapse',)
        }),
    )
    
    def key_preview(self, obj):
        """Show truncated key in list view for security"""
        if obj.key:
            return f"{obj.key[:20]}...{obj.key[-10:]}"
        return "-"
    key_preview.short_description = "Key (truncated)"
    
    actions = ['activate_keys', 'deactivate_keys']
    
    def activate_keys(self, request, queryset):
        """Bulk activate API keys"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"✅ Activated {updated} API key(s)")
    activate_keys.short_description = "✅ Activate selected API keys"
    
    def deactivate_keys(self, request, queryset):
        """Bulk deactivate API keys"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"❌ Deactivated {updated} API key(s)")
    deactivate_keys.short_description = "❌ Deactivate selected API keys"

