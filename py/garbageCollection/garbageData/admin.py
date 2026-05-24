from django.contrib import admin
from django.db.models import Count, Max, Avg
from django.utils.html import format_html
from .models import TrashCan, FillRecord, APIKey


# ── TrashCan ──────────────────────────────────────────────────────────────────

class HasNFCFilter(admin.SimpleListFilter):
    title = 'NFC tag'
    parameter_name = 'has_nfc'

    def lookups(self, request, model_admin):
        return [('yes', 'Has NFC tag'), ('no', 'No NFC tag')]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(nfc_uid__isnull=True).exclude(nfc_uid='')
        if self.value() == 'no':
            return queryset.filter(nfc_uid__isnull=True) | queryset.filter(nfc_uid='')


class HasFillDataFilter(admin.SimpleListFilter):
    title = 'fill data'
    parameter_name = 'has_fill'

    def lookups(self, request, model_admin):
        return [('yes', 'Has fill records'), ('no', 'No fill records')]

    def queryset(self, request, queryset):
        annotated = queryset.annotate(record_count=Count('fill_records'))
        if self.value() == 'yes':
            return annotated.filter(record_count__gt=0)
        if self.value() == 'no':
            return annotated.filter(record_count=0)


@admin.register(TrashCan)
class TrashCanAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'public_number', 'district_badge', 'waste_type_badge',
        'bin_status_badge', 'capacity_volume', 'bin_count',
        'nfc_tag', 'last_emptied', 'last_cleaned',
    )
    list_filter = ('district_id', 'waste_type', 'bin_status', HasNFCFilter, HasFillDataFilter)
    search_fields = ('id', 'public_number', 'district_name', 'nfc_uid')
    ordering = ('district_id', 'id')
    list_per_page = 100
    show_full_result_count = False  # skip COUNT(*) on huge tables

    readonly_fields = ('last_emptied', 'last_cleaned')

    fieldsets = (
        ('Location', {
            'fields': ('id', 'latitude', 'longitude'),
        }),
        ('Sofia API', {
            'fields': (
                'public_number', 'district_id', 'district_name',
                'waste_type', 'bin_status', 'capacity_volume',
                'bin_count', 'last_cleaned',
            ),
        }),
        ('Truck tracking', {
            'fields': ('nfc_uid', 'last_emptied'),
            'classes': ('collapse',),
            'description': 'NFC tag links this bin to the RPi scanner on the truck.',
        }),
    )

    # ── Custom display columns ────────────────────────────────────────────

    @admin.display(description='District', ordering='district_id')
    def district_badge(self, obj):
        if not obj.district_id:
            return '—'
        return format_html(
            '<span style="'
            'background:#1D4ED8;color:#fff;padding:2px 7px;'
            'border-radius:4px;font-size:0.78em;font-weight:600;">'
            '{} {}</span>',
            obj.district_id, obj.district_name or '',
        )

    @admin.display(description='Type', ordering='waste_type')
    def waste_type_badge(self, obj):
        colours = {
            'general':   ('#64748B', '#fff'),
            'recycling': ('#2563EB', '#fff'),
            'organic':   ('#16A34A', '#fff'),
            'glass':     ('#0891B2', '#fff'),
            'paper':     ('#D97706', '#fff'),
        }
        bg, fg = colours.get(obj.waste_type, ('#64748B', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 7px;'
            'border-radius:4px;font-size:0.78em;font-weight:600;">{}</span>',
            bg, fg, obj.waste_type or '—',
        )

    @admin.display(description='Status', ordering='bin_status')
    def bin_status_badge(self, obj):
        colours = {
            'active':   ('#16A34A', '#fff'),
            'pending':  ('#D97706', '#fff'),
            'inactive': ('#E63946', '#fff'),
        }
        bg, fg = colours.get(obj.bin_status, ('#64748B', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 7px;'
            'border-radius:4px;font-size:0.78em;font-weight:600;">{}</span>',
            bg, fg, obj.bin_status or '—',
        )

    @admin.display(description='NFC', boolean=True)
    def nfc_tag(self, obj):
        return bool(obj.nfc_uid)


# ── FillRecord ────────────────────────────────────────────────────────────────

@admin.register(FillRecord)
class FillRecordAdmin(admin.ModelAdmin):
    list_display = ('trashcan', 'fill_level_bar', 'source', 'timestamp')
    list_filter = ('source', 'timestamp')
    search_fields = ('trashcan__id', 'trashcan__public_number', 'trashcan__nfc_uid')
    ordering = ('-timestamp',)
    readonly_fields = ('timestamp',)
    list_per_page = 200

    @admin.display(description='Fill level', ordering='fill_level')
    def fill_level_bar(self, obj):
        pct = min(obj.fill_level, 100)
        if pct >= 100:
            colour = '#E63946'
        elif pct >= 80:
            colour = '#F97316'
        elif pct >= 60:
            colour = '#EAB308'
        else:
            colour = '#22C55E'
        overflow = ' ⚠ OVERFLOW' if obj.fill_level > 100 else ''
        return format_html(
            '<div style="display:flex;align-items:center;gap:6px;">'
            '<div style="width:80px;height:10px;background:#e5e7eb;border-radius:5px;overflow:hidden;">'
            '<div style="width:{}%;height:100%;background:{};border-radius:5px;"></div>'
            '</div>'
            '<span style="font-size:0.8em;font-weight:600;">{}{}</span>'
            '</div>',
            pct, colour, obj.fill_level, overflow,
        )


# ── APIKey ────────────────────────────────────────────────────────────────────

@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('device_name', 'status_badge', 'created_at', 'last_used', 'key_preview')
    list_filter = ('is_active',)
    search_fields = ('device_name', 'description', 'key')
    readonly_fields = ('key', 'created_at', 'last_used')
    ordering = ('-created_at',)

    fieldsets = (
        ('Device', {
            'fields': ('device_name', 'description', 'is_active'),
        }),
        ('API Key', {
            'fields': ('key',),
            'classes': ('collapse',),
            'description': 'Auto-generated. Keep secret — treat like a password.',
        }),
        ('Usage', {
            'fields': ('created_at', 'last_used'),
            'classes': ('collapse',),
        }),
    )

    actions = ['activate_keys', 'deactivate_keys']

    @admin.display(description='Status', ordering='is_active')
    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background:#16A34A;color:#fff;padding:2px 8px;'
                'border-radius:4px;font-size:0.78em;font-weight:600;">Active</span>'
            )
        return format_html(
            '<span style="background:#E63946;color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:0.78em;font-weight:600;">Inactive</span>'
        )

    @admin.display(description='Key (truncated)')
    def key_preview(self, obj):
        if obj.key:
            return f'{obj.key[:20]}…{obj.key[-8:]}'
        return '—'

    def activate_keys(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'Activated {updated} key(s).')
    activate_keys.short_description = 'Activate selected keys'

    def deactivate_keys(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'Deactivated {updated} key(s).')
    deactivate_keys.short_description = 'Deactivate selected keys'


# ── Admin site branding ───────────────────────────────────────────────────────

admin.site.site_header = 'Smart Kazan Collector'
admin.site.site_title  = 'Kazan Admin'
admin.site.index_title = 'Operations dashboard'
