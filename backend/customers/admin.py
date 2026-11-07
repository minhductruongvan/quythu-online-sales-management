from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    DiaChiKH,
    GhiChuKhachHang,
    KhachHang,
    LichSuKhachHang,
    LoaiKhachHang,
    NhanVien,
    TaiKhoan,
)


@admin.register(TaiKhoan)
class TaiKhoanAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("ma_tk", "email", "vai_tro", "trang_thai", "is_active")
    list_filter = ("vai_tro", "trang_thai", "is_active")
    search_fields = ("ma_tk", "email", "so_dien_thoai")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Thông tin", {"fields": ("ma_tk", "so_dien_thoai", "vai_tro", "trang_thai")}),
        ("Quyền", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Thời gian", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "ma_tk", "password1", "password2", "vai_tro"),
            },
        ),
    )
    username_field = "email"


@admin.register(KhachHang)
class KhachHangAdmin(admin.ModelAdmin):
    list_display = ("ma_kh", "ho_ten", "email", "so_dien_thoai", "loai_khach_hang", "trang_thai")
    list_filter = ("loai_khach_hang", "trang_thai")
    search_fields = ("ma_kh", "ho_ten", "email", "so_dien_thoai", "tai_khoan__email")


@admin.register(LichSuKhachHang)
class LichSuKhachHangAdmin(admin.ModelAdmin):
    list_display = ("ma_lich_su", "khach_hang", "loai_thay_doi", "nguoi_thuc_hien", "thoi_gian")
    readonly_fields = ("ma_lich_su", "khach_hang", "nguoi_thuc_hien", "loai_thay_doi", "noi_dung_cu", "noi_dung_moi", "thoi_gian")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GhiChuKhachHang)
class GhiChuKhachHangAdmin(admin.ModelAdmin):
    list_display = ("khach_hang", "nguoi_tao", "thoi_gian")
    search_fields = ("khach_hang__ma_kh", "khach_hang__ho_ten", "noi_dung")
    readonly_fields = ("khach_hang", "nguoi_tao", "noi_dung", "thoi_gian")

    def has_change_permission(self, request, obj=None):
        return False


admin.site.register([DiaChiKH, LoaiKhachHang, NhanVien])
