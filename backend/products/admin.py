from django.contrib import admin

from .models import DonViTinh


@admin.register(DonViTinh)
class DonViTinhAdmin(admin.ModelAdmin):
    list_display = ("ma_dvt", "ten_dvt", "ky_hieu")
    search_fields = ("ma_dvt", "ten_dvt", "ky_hieu")
