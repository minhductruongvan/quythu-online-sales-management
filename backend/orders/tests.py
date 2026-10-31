# File: backend/orders/tests.py
# Kiểm thử tự động cho Module 3.
# Chạy: python manage.py test orders
#
# Mỗi lần chạy, Django tạo một CSDL test trống, chạy toàn bộ migration
# (nên có sẵn 34 tỉnh, 2 PTTT, 2 loại khách), chạy test rồi xóa CSDL đó.
# db.sqlite3 thật trên máy không bị đụng tới.

from django.test import TestCase

from customers.models import KhachHang, LoaiKhachHang, TaiKhoan
from products.models import BienTheSanPham, DanhMucSanPham, SanPham

from .models import ChiTietGioHang, DonHang, GioHang, TinhThanh
from .services import (
    DichVuGioHang,
    LoiNghiepVuDonHang,
    LoiQuyenDonHang,
    chuan_hoa_ten_tinh,
    sinh_ma,
    tim_tinh_thanh,
)


# ==========================================================
# Hàm tạo dữ liệu mẫu dùng chung
# (M2 chưa có test nên M3 tự tạo BienTheSanPham: model M2 đổi tên trường
#  thì các test này báo lỗi ngay)
# ==========================================================
def tao_khach_hang(ma_kh, email, ma_loai="LKH001"):
    tai_khoan = TaiKhoan.objects.create(ma_tk=f"TK_{ma_kh}", email=email)
    return KhachHang.objects.create(
        ma_kh=ma_kh,
        tai_khoan=tai_khoan,
        loai_khach_hang=LoaiKhachHang.objects.get(ma_loai_kh=ma_loai),
        ho_ten=f"Khách {ma_kh}",
    )


def tao_bien_the(ma_bien_the, san_pham, gia_le=50000, gia_si=None, toi_thieu_si=10):
    return BienTheSanPham.objects.create(
        ma_bien_the=ma_bien_the,
        san_pham=san_pham,
        huong_vi="Truyền thống",
        quy_cach="150g",
        barcode=f"BC_{ma_bien_the}",
        gia_ban_le=gia_le,
        gia_ban_si=gia_si,
        so_luong_toi_thieu_si=toi_thieu_si,
    )


# ==========================================================
# Phần 1: sinh mã, tra tỉnh/thành
# ==========================================================
class KiemThuSinhMa(TestCase):
    def test_bang_trong_thi_bat_dau_tu_001(self):
        self.assertEqual(sinh_ma(DonHang), "DH001")
        self.assertEqual(sinh_ma(GioHang), "CART001")

    def test_ma_trung_thi_tang_tiep(self):
        # Có 1 giỏ mang mã CART002 -> đếm + 1 = 2 -> trùng -> phải ra CART003
        kh = tao_khach_hang("KH_T1", "t1@test.vn")
        GioHang.objects.create(ma_gio_hang="CART002", khach_hang=kh)
        self.assertEqual(sinh_ma(GioHang), "CART003")


class KiemThuTinhThanh(TestCase):
    def test_chuan_hoa_cac_cach_viet(self):
        self.assertEqual(chuan_hoa_ten_tinh("  Thành phố  ĐÀ NẴNG "), "da nang")
        self.assertEqual(chuan_hoa_ten_tinh("Khánh Hoà"), chuan_hoa_ten_tinh("Khánh Hòa"))
        self.assertEqual(chuan_hoa_ten_tinh("TP.HCM"), "ho chi minh")

    def test_tim_thay_tinh(self):
        self.assertEqual(tim_tinh_thanh("Đà Nẵng").ma_tinh, "TT021")
        self.assertEqual(tim_tinh_thanh("Thừa Thiên Huế").ma_tinh, "TT020")

    def test_khong_co_trong_bang_phi(self):  # M3-UC03 E4
        with self.assertRaises(LoiNghiepVuDonHang):
            tim_tinh_thanh("Bình Dương")

    def test_dia_chi_khong_co_tinh(self):
        with self.assertRaises(LoiNghiepVuDonHang):
            tim_tinh_thanh("")

    def test_tinh_ngung_phuc_vu(self):
        TinhThanh.objects.filter(ma_tinh="TT021").update(dang_hoat_dong=False)
        with self.assertRaises(LoiNghiepVuDonHang):
            tim_tinh_thanh("Đà Nẵng")


# ==========================================================
# Phần 2: giỏ hàng (M3-UC01, M3-UC02)
# ==========================================================
class KiemThuGioHang(TestCase):
    def setUp(self):
        # setUp chạy lại trước MỖI test, nên test nào cũng bắt đầu từ cùng dữ liệu
        self.kh = tao_khach_hang("KH_A", "a@test.vn")
        self.kh_khac = tao_khach_hang("KH_B", "b@test.vn")
        danh_muc = DanhMucSanPham.objects.create(ma_dm="DM_T", ten_dm="Bánh test")
        self.san_pham = SanPham.objects.create(
            ma_sp="SP_T", danh_muc=danh_muc, ten_sp="Bánh dừa test"
        )
        self.bt1 = tao_bien_the("BT_T1", self.san_pham)
        self.bt2 = tao_bien_the("BT_T2", self.san_pham)

    # ----- UC01 -----
    def test_them_lan_dau_tao_gio_va_dong(self):
        dong = DichVuGioHang.them_vao_gio(self.kh, self.bt1, 2)

        self.assertEqual(dong.so_luong, 2)
        self.assertEqual(GioHang.objects.filter(khach_hang=self.kh).count(), 1)
        self.assertEqual(DichVuGioHang.dem_so_dong(self.kh), 1)

    def test_them_lai_cung_bien_the_thi_cong_don(self):
        DichVuGioHang.them_vao_gio(self.kh, self.bt1, 2)
        dong = DichVuGioHang.them_vao_gio(self.kh, self.bt1, 3)

        self.assertEqual(dong.so_luong, 5)
        self.assertEqual(DichVuGioHang.dem_so_dong(self.kh), 1)  # vẫn 1 dòng

    def test_bien_the_khac_thi_them_dong_moi(self):
        DichVuGioHang.them_vao_gio(self.kh, self.bt1, 1)
        DichVuGioHang.them_vao_gio(self.kh, self.bt2, 1)
        self.assertEqual(DichVuGioHang.dem_so_dong(self.kh), 2)

    def test_bien_the_ngung_ban_bi_chan(self):  # UC01-E1
        self.bt1.trang_thai = "INACTIVE"
        self.bt1.save()
        with self.assertRaises(LoiNghiepVuDonHang):
            DichVuGioHang.them_vao_gio(self.kh, self.bt1, 1)

    def test_san_pham_cha_ngung_ban_bi_chan(self):  # UC01-E1
        self.san_pham.trang_thai = "INACTIVE"
        self.san_pham.save()
        with self.assertRaises(LoiNghiepVuDonHang):
            DichVuGioHang.them_vao_gio(self.kh, self.bt1, 1)

    def test_so_luong_khong_hop_le_va_gio_giu_nguyen(self):  # UC01-E2
        for so_luong in [0, -1, 1.5, "2", True]:
            with self.assertRaises(LoiNghiepVuDonHang):
                DichVuGioHang.them_vao_gio(self.kh, self.bt1, so_luong)
        self.assertFalse(ChiTietGioHang.objects.exists())

    def test_khach_ngung_hoat_dong_bi_chan(self):  # M3-BR01
        self.kh.trang_thai = KhachHang.TrangThai.INACTIVE
        self.kh.save()
        with self.assertRaises(LoiQuyenDonHang):
            DichVuGioHang.them_vao_gio(self.kh, self.bt1, 1)

    # ----- UC02 -----
    def test_cap_nhat_so_luong(self):
        dong = DichVuGioHang.them_vao_gio(self.kh, self.bt1, 2)
        DichVuGioHang.cap_nhat_so_luong(self.kh, dong.ma_ctgh, 12)

        dong.refresh_from_db()  # đọc lại từ CSDL, không tin bản trong bộ nhớ
        self.assertEqual(dong.so_luong, 12)

    def test_khong_sua_duoc_gio_cua_khach_khac(self):  # M3-BR24
        dong = DichVuGioHang.them_vao_gio(self.kh, self.bt1, 2)
        with self.assertRaises(LoiQuyenDonHang):
            DichVuGioHang.cap_nhat_so_luong(self.kh_khac, dong.ma_ctgh, 5)
        with self.assertRaises(LoiQuyenDonHang):
            DichVuGioHang.xoa_dong(self.kh_khac, dong.ma_ctgh)

    def test_dong_ngung_ban_chi_duoc_xoa(self):  # UC02-E3
        dong = DichVuGioHang.them_vao_gio(self.kh, self.bt1, 2)
        self.bt1.trang_thai = "INACTIVE"
        self.bt1.save()

        with self.assertRaises(LoiNghiepVuDonHang):
            DichVuGioHang.cap_nhat_so_luong(self.kh, dong.ma_ctgh, 5)

        DichVuGioHang.xoa_dong(self.kh, dong.ma_ctgh)
        self.assertEqual(DichVuGioHang.dem_so_dong(self.kh), 0)

    def test_xoa_dong_khong_ton_tai(self):
        with self.assertRaises(LoiNghiepVuDonHang):
            DichVuGioHang.xoa_dong(self.kh, "CG999")