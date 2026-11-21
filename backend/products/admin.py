from django.contrib import admin

from .forms import BienTheForm, DanhMucForm, SanPhamForm
from .models import (
    BienTheSanPham,
    DanhMucSanPham,
    DonViTinh,
    HinhAnhSanPham,
    LichSuGiaBienThe,
    SanPham,
)


class BienTheAdminForm(BienTheForm):
    class Meta(BienTheForm.Meta):
        fields = [
            "ma_bien_the",
            "san_pham",
            "huong_vi",
            "quy_cach",
            "don_vi_tinh",
            "barcode",
            "gia_ban_le",
            "gia_ban_si",
            "so_luong_toi_thieu_si",
            "trang_thai",
        ]

    def clean(self):
        self.san_pham = self.cleaned_data.get("san_pham") or self.san_pham
        return super().clean()


class DonViTinhAdmin(admin.ModelAdmin):
    list_display = ("ma_dvt", "ten_dvt", "ky_hieu")
    search_fields = ("ma_dvt", "ten_dvt", "ky_hieu")


class DanhMucSanPhamAdmin(admin.ModelAdmin):
    form = DanhMucForm
    list_display = ("ma_dm", "ten_dm", "trang_thai", "ngay_tao")
    list_filter = ("trang_thai",)
    search_fields = ("ma_dm", "ten_dm")


class SanPhamAdmin(admin.ModelAdmin):
    form = SanPhamForm
    list_display = ("ma_sp", "ten_sp", "danh_muc", "trang_thai", "ngay_tao")
    list_filter = ("trang_thai", "danh_muc")
    search_fields = ("ma_sp", "ten_sp")


class BienTheSanPhamAdmin(admin.ModelAdmin):
    form = BienTheAdminForm
    list_display = (
        "ma_bien_the",
        "san_pham",
        "huong_vi",
        "quy_cach",
        "don_vi_tinh",
        "barcode",
        "gia_ban_le",
        "gia_ban_si",
        "trang_thai",
    )
    list_filter = ("trang_thai", "huong_vi", "quy_cach")
    search_fields = ("ma_bien_the", "barcode", "san_pham__ten_sp")


class HinhAnhSanPhamAdmin(admin.ModelAdmin):
    list_display = ("ma_hinh_anh", "san_pham", "duong_dan", "anh_chinh")
    list_filter = ("anh_chinh",)
    search_fields = ("ma_hinh_anh", "san_pham__ten_sp")


class LichSuGiaBienTheAdmin(admin.ModelAdmin):
    list_display = (
        "ma_bien_the",
        "ten_bien_the",
        "nguoi_thuc_hien",
        "gia_ban_le_cu",
        "gia_ban_le_moi",
        "thoi_gian",
    )
    list_filter = ("thoi_gian",)
    search_fields = ("ma_bien_the", "ten_bien_the")


admin.site.register(DonViTinh, DonViTinhAdmin)
admin.site.register(DanhMucSanPham, DanhMucSanPhamAdmin)
admin.site.register(SanPham, SanPhamAdmin)
admin.site.register(BienTheSanPham, BienTheSanPhamAdmin)
admin.site.register(HinhAnhSanPham, HinhAnhSanPhamAdmin)
admin.site.register(LichSuGiaBienThe, LichSuGiaBienTheAdmin)
