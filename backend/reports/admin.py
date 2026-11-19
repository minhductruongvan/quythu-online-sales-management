from django.contrib import admin

from .models import NhatKyXuatBaoCao, PhanQuyenBaoCao


@admin.register(PhanQuyenBaoCao)
class PhanQuyenBaoCaoAdmin(admin.ModelAdmin):
    list_display = (
        "ma_phan_quyen",
        "nhan_vien",
        "loai_bao_cao",
        "quyen_xem",
        "quyen_xuat",
        "thoi_diem_thu_hoi",
    )
    list_filter = ("loai_bao_cao", "quyen_xem", "quyen_xuat")
    search_fields = ("ma_phan_quyen", "nhan_vien__ma_nv", "nhan_vien__ho_ten")


@admin.register(NhatKyXuatBaoCao)
class NhatKyXuatBaoCaoAdmin(admin.ModelAdmin):
    list_display = (
        "ma_nhat_ky_xuat",
        "nhan_vien",
        "loai_bao_cao",
        "ky_bao_cao",
        "dinh_dang_file",
        "thoi_diem_xuat",
    )
    list_filter = ("loai_bao_cao", "dinh_dang_file")
    search_fields = ("ma_nhat_ky_xuat", "nhan_vien__ma_nv", "nhan_vien__ho_ten")
    readonly_fields = (
        "ma_nhat_ky_xuat",
        "nhan_vien",
        "loai_bao_cao",
        "ky_bao_cao",
        "bo_loc_ap_dung",
        "dinh_dang_file",
        "thoi_diem_xuat",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
