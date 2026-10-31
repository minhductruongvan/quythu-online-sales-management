# File: backend/orders/admin.py
# Đăng ký các bảng M3 lên trang quản trị /admin/ để xem và kiểm tra dữ liệu.
# Lưu ý: trạng thái đơn KHÔNG sửa ở đây. Mọi chuyển trạng thái phải đi qua
# services.py (giai đoạn 4) để kiểm tra luồng hợp lệ và ghi lịch sử (M3-BR14, BR15).

from django.contrib import admin

from .models import (
    ChiTietDonHang,
    ChiTietGioHang,
    DonHang,
    GiaoDichThanhToan,
    GioHang,
    LichSuTrangThaiDonHang,
    PhuongThucThanhToan,
    TinhThanh,
)


# ==========================================================
# Lớp dùng chung: chỉ cho xem, không thêm/sửa/xóa
# (lịch sử trạng thái và giao dịch thanh toán không được sửa – M3-BR15, BR16)
# ==========================================================
class ChiXemMixin:
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ==========================================================
# 1. Danh mục: tỉnh/thành và phương thức thanh toán
# ==========================================================
@admin.register(TinhThanh)
class TinhThanhAdmin(admin.ModelAdmin):
    list_display = ("ma_tinh", "ten_tinh", "vung_mien", "phi_van_chuyen", "dang_hoat_dong")
    # Sửa phí và bật/tắt ngay trên bảng danh sách, không cần mở từng tỉnh
    list_editable = ("phi_van_chuyen", "dang_hoat_dong")
    list_filter = ("vung_mien", "dang_hoat_dong")
    search_fields = ("ma_tinh", "ten_tinh")
    ordering = ("ma_tinh",)


@admin.register(PhuongThucThanhToan)
class PhuongThucThanhToanAdmin(admin.ModelAdmin):
    list_display = ("ma_pttt", "ten_pttt", "thong_tin_tai_khoan", "dang_kich_hoat")


# ==========================================================
# 2. Giỏ hàng: mỗi giỏ hiện kèm các dòng của nó
# ==========================================================
class ChiTietGioHangInline(admin.TabularInline):
    model = ChiTietGioHang
    extra = 0
    raw_id_fields = ("bien_the",)


@admin.register(GioHang)
class GioHangAdmin(admin.ModelAdmin):
    list_display = ("ma_gio_hang", "khach_hang", "so_dong", "ngay_cap_nhat")
    raw_id_fields = ("khach_hang",)
    inlines = [ChiTietGioHangInline]

    @admin.display(description="Số dòng")
    def so_dong(self, obj):
        return obj.chi_tiet.count()


# ==========================================================
# 3. Đơn hàng: dòng đơn, lịch sử, giao dịch hiện ngay trong trang đơn
# ==========================================================
class ChiTietDonHangInline(admin.TabularInline):
    model = ChiTietDonHang
    extra = 0
    raw_id_fields = ("bien_the",)


class LichSuTrangThaiInline(ChiXemMixin, admin.TabularInline):
    model = LichSuTrangThaiDonHang
    extra = 0


class GiaoDichThanhToanInline(ChiXemMixin, admin.TabularInline):
    model = GiaoDichThanhToan
    extra = 0


@admin.register(DonHang)
class DonHangAdmin(admin.ModelAdmin):
    list_display = (
        "ma_dh",
        "khach_hang",
        "tinh_thanh",
        "tong_thanh_toan",
        "phuong_thuc_thanh_toan",
        "trang_thai",
        "trang_thai_thanh_toan",
        "ngay_dat",
    )
    list_filter = ("trang_thai", "trang_thai_thanh_toan", "phuong_thuc_thanh_toan", "tinh_thanh__vung_mien")
    search_fields = ("ma_dh", "ho_ten_nguoi_nhan", "sdt_nguoi_nhan", "khach_hang__ho_ten")
    date_hierarchy = "ngay_dat"
    raw_id_fields = ("khach_hang", "nhan_vien_xac_nhan")
    # Lấy kèm bảng liên quan trong một truy vấn, tránh mỗi dòng danh sách hỏi CSDL một lần
    list_select_related = ("khach_hang", "tinh_thanh", "phuong_thuc_thanh_toan")

    # Trạng thái và các mốc thời gian chỉ được đổi qua services.py
    readonly_fields = (
        "trang_thai",
        "trang_thai_thanh_toan",
        "trang_thai_hau_mai",
        "thoi_diem_xac_nhan",
        "thoi_diem_bat_dau_chuan_bi",
        "thoi_diem_hen_cung_cap",
        "trang_thai_truoc_cho_bo_sung",
        "so_lan_giao_lai",
        "thoi_diem_ban_giao",
        "thoi_diem_giao_thanh_cong",
        "thoi_diem_xac_nhan_nhan_hang",
        "xac_nhan_tu_dong",
        "thoi_diem_hoan_thanh",
    )

    fieldsets = (
        ("Đơn hàng", {"fields": ("ma_dh", "khach_hang", "loai_khach_hang_ap_dung", "ngay_dat", "ghi_chu")}),
        ("Giao đến", {"fields": ("ho_ten_nguoi_nhan", "sdt_nguoi_nhan", "dia_chi_giao_hang", "tinh_thanh")}),
        ("Tiền và thanh toán", {
            "fields": ("tong_tien_hang", "phi_van_chuyen", "tong_thanh_toan",
                       "phuong_thuc_thanh_toan", "trang_thai_thanh_toan"),
        }),
        ("Trạng thái và mốc thời gian", {
            "fields": ("trang_thai", "trang_thai_hau_mai", "nhan_vien_xac_nhan",
                       "thoi_diem_xac_nhan", "thoi_diem_bat_dau_chuan_bi",
                       "thoi_diem_hen_cung_cap", "trang_thai_truoc_cho_bo_sung",
                       "so_lan_giao_lai", "thoi_diem_ban_giao", "thoi_diem_giao_thanh_cong",
                       "thoi_diem_xac_nhan_nhan_hang", "xac_nhan_tu_dong", "thoi_diem_hoan_thanh"),
        }),
    )

    inlines = [ChiTietDonHangInline, GiaoDichThanhToanInline, LichSuTrangThaiInline]


# ==========================================================
# 4. Lịch sử và giao dịch: có trang riêng để tra cứu, nhưng chỉ xem
# ==========================================================
@admin.register(LichSuTrangThaiDonHang)
class LichSuTrangThaiDonHangAdmin(ChiXemMixin, admin.ModelAdmin):
    list_display = ("ma_lstt", "don_hang", "trang_thai_cu", "trang_thai", "tac_nhan", "nhan_vien", "thoi_diem")
    list_filter = ("tac_nhan", "trang_thai")
    search_fields = ("don_hang__ma_dh",)


@admin.register(GiaoDichThanhToan)
class GiaoDichThanhToanAdmin(ChiXemMixin, admin.ModelAdmin):
    list_display = ("ma_giao_dich", "don_hang", "phuong_thuc", "so_tien_phai_thu",
                    "so_tien_thuc_nhan", "trang_thai", "thoi_diem_thanh_toan")
    list_filter = ("trang_thai", "phuong_thuc")
    search_fields = ("don_hang__ma_dh", "ma_giao_dich_ngan_hang")