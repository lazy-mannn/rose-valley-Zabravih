from django.contrib import admin
from .models import TrashCan, FillRecord

@admin.register(TrashCan)
class TrashCanAdmin(admin.ModelAdmin):
    list_display = ('id', 'latitude', 'longitude')
    search_fields = ('id',)
    ordering = ('id',)

@admin.register(FillRecord)
class FillRecordAdmin(admin.ModelAdmin):
    list_display = ('trashcan', 'fill_level', 'timestamp')
    list_filter = ('trashcan', 'timestamp')
    search_fields = ('trashcan__id',)
    ordering = ('-timestamp',)
    readonly_fields = ('timestamp',)

