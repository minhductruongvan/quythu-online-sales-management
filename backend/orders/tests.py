# File: backend/orders/tests.py
# Kiểm thử tự động cho Module 3.
# Chạy: python manage.py test orders
#
# Mỗi lần chạy, Django tạo một CSDL test trống, chạy toàn bộ migration
# (nên có sẵn 34 tỉnh, 2 PTTT, 2 loại khách), chạy test rồi xóa CSDL đó.
# db.sqlite3 thật trên máy không bị đụng tới.

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.db import DatabaseError, IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from customers.models import DiaChiKH, KhachHang, LoaiKhachHang, NhanVien, TaiKhoan
from products.models import BienTheSanPham, DanhMucSanPham, SanPham

from .models import (
    ChiTietDonHang,
    ChiTietGioHang,
    DonHang,
    GiaoDichThanhToan,
    GiaoHang,
    GioHang,
    HinhThucGiao,
    KetQuaGiao,
    KetQuaKiemTra,
    LichSuTrangThaiDonHang,
    LoaiGia,
    PhuongThucThanhToan,
    TacNhan,
    TinhThanh,
    TrangThaiDonHang,
    TrangThaiThanhToan,
)
from .permissions import KhachHangCoHoSo
from .serializers import (
    CapNhatSoLuongSerializer,
    GioHangSerializer,
    ThemVaoGioSerializer,
)
from .services import (
    CAC_CANH_HOP_LE,
    MA_HAU_MAI_CHO_DOI_TRA,
    MA_HAU_MAI_CHO_HUY,
    TRANG_THAI_CUOI,
    DichVuDatHang,
    DichVuDiaChiGiaoHang,
    DichVuGiaoHang,
    DichVuGioHang,
    DichVuThanhToan,
    DichVuTinhTien,
    DichVuTrangThai,
    DichVuXuLyDon,
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


def tao_nhan_vien(ma_nv="NV_T1"):
    tai_khoan = TaiKhoan.objects.create(
        ma_tk=f"TK_{ma_nv}", email=f"{ma_nv.lower()}@test.vn", vai_tro=TaiKhoan.VaiTro.EMPLOYEE
    )
    return NhanVien.objects.create(ma_nv=ma_nv, tai_khoan=tai_khoan, ho_ten=f"Nhân viên {ma_nv}")


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
    def test_chuan_hoa_khoang_trang_va_chu_hoa(self):
        self.assertEqual(chuan_hoa_ten_tinh("  ĐÀ   Nẵng "), "đà nẵng")

    def test_tim_thay_tinh(self):
        self.assertEqual(tim_tinh_thanh("Đà Nẵng").ma_tinh, "TT021")
        self.assertEqual(tim_tinh_thanh(" tp. hồ chí minh ").ma_tinh, "TT027")

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
        for so_luong in [0, -1]:
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


# ==========================================================
# Phần 3: địa chỉ giao hàng (M3-UC04)
# ==========================================================
def tao_dia_chi(ma_dia_chi, khach_hang, tinh_thanh="Đà Nẵng", mac_dinh=False,
                so_dien_thoai="0905123456"):
    return DiaChiKH.objects.create(
        ma_dia_chi=ma_dia_chi,
        khach_hang=khach_hang,
        ten_nguoi_nhan="Người nhận test",
        so_dien_thoai=so_dien_thoai,
        dia_chi_chi_tiet="12 Lê Lợi",
        tinh_thanh=tinh_thanh,
        mac_dinh=mac_dinh,
    )


class KiemThuDiaChiGiaoHang(TestCase):
    def setUp(self):
        self.kh = tao_khach_hang("KH_D", "d@test.vn")
        self.kh_khac = tao_khach_hang("KH_E", "e@test.vn")

    def dat_ngay_cap_nhat(self, ma_dia_chi, so_ngay_truoc):
        # .update() ghi thẳng xuống CSDL nên không bị auto_now ghi đè
        DiaChiKH.objects.filter(ma_dia_chi=ma_dia_chi).update(
            ngay_cap_nhat=timezone.now() - timedelta(days=so_ngay_truoc)
        )

    # ----- lay_dia_chi_hien_thi_san (UC04 bước 1, M3-BR08) -----
    def test_uu_tien_dia_chi_mac_dinh(self):
        tao_dia_chi("DC_T1", self.kh, mac_dinh=True)
        tao_dia_chi("DC_T2", self.kh)
        self.dat_ngay_cap_nhat("DC_T1", 5)   # mặc định nhưng cũ hơn
        self.dat_ngay_cap_nhat("DC_T2", 1)

        dia_chi = DichVuDiaChiGiaoHang.lay_dia_chi_hien_thi_san(self.kh)
        self.assertEqual(dia_chi.ma_dia_chi, "DC_T1")

    def test_khong_co_mac_dinh_thi_lay_cap_nhat_gan_nhat(self):
        tao_dia_chi("DC_T1", self.kh)
        tao_dia_chi("DC_T2", self.kh)
        self.dat_ngay_cap_nhat("DC_T1", 1)
        self.dat_ngay_cap_nhat("DC_T2", 5)

        dia_chi = DichVuDiaChiGiaoHang.lay_dia_chi_hien_thi_san(self.kh)
        self.assertEqual(dia_chi.ma_dia_chi, "DC_T1")

    def test_so_dia_chi_trong(self):  # UC04-E1, UC03-E3
        with self.assertRaises(LoiNghiepVuDonHang):
            DichVuDiaChiGiaoHang.lay_dia_chi_hien_thi_san(self.kh)

    # ----- chon_dia_chi (UC04 bước 3) -----
    def test_chon_dia_chi_tra_ve_tinh_va_phi(self):
        tao_dia_chi("DC_T1", self.kh, tinh_thanh="Đà Nẵng")
        ket_qua = DichVuDiaChiGiaoHang.chon_dia_chi(self.kh, "DC_T1")
        self.assertEqual(ket_qua["tinh_thanh"].ma_tinh, "TT021")
        self.assertEqual(ket_qua["phi_van_chuyen"], Decimal("30000"))

    def test_dia_chi_cua_khach_khac(self):  # UC04 NFR
        tao_dia_chi("DC_T1", self.kh_khac)
        with self.assertRaises(LoiQuyenDonHang):
            DichVuDiaChiGiaoHang.chon_dia_chi(self.kh, "DC_T1")

    def test_dia_chi_thieu_so_dien_thoai(self):  # UC04-E2
        tao_dia_chi("DC_T1", self.kh, so_dien_thoai="  ")
        with self.assertRaises(LoiNghiepVuDonHang):
            DichVuDiaChiGiaoHang.chon_dia_chi(self.kh, "DC_T1")

    def test_tinh_khong_co_trong_bang_phi(self):  # UC04-E3, UC03-E4
        tao_dia_chi("DC_T1", self.kh, tinh_thanh="Bình Dương")
        with self.assertRaises(LoiNghiepVuDonHang):
            DichVuDiaChiGiaoHang.chon_dia_chi(self.kh, "DC_T1")


# ==========================================================
# Phần 4: tính giá (M3-UC02 hiển thị, M3-BR04), tổng tiền (M3-UC03 bước 1)
# ==========================================================
class KiemThuTinhGia(TestCase):
    def setUp(self):
        self.kh_le = tao_khach_hang("KH_LE", "le@test.vn")                      # LKH001
        self.kh_si = tao_khach_hang("KH_SI", "si@test.vn", ma_loai="LKH002")    # đã duyệt sỉ
        danh_muc = DanhMucSanPham.objects.create(ma_dm="DM_G", ten_dm="Bánh test")
        self.san_pham = SanPham.objects.create(
            ma_sp="SP_G", danh_muc=danh_muc, ten_sp="Bánh dừa test"
        )
        # Biến thể có giá sỉ 40.000, mức tối thiểu 10
        self.bt_si = tao_bien_the("BT_G1", self.san_pham, gia_le=50000, gia_si=40000)
        # Biến thể chưa có giá sỉ
        self.bt_le = tao_bien_the("BT_G2", self.san_pham, gia_le=30000, gia_si=None)

    # ----- tinh_gia_dong (M3-BR04) -----
    def test_khach_le_luon_gia_le(self):
        loai, don_gia, thanh_tien = DichVuTinhTien.tinh_gia_dong(self.kh_le, self.bt_si, 20)
        self.assertEqual(loai, LoaiGia.GIA_LE)
        self.assertEqual(don_gia, Decimal("50000"))
        self.assertEqual(thanh_tien, Decimal("1000000"))

    def test_khach_si_dat_dung_muc_toi_thieu_thi_gia_si(self):
        loai, don_gia, thanh_tien = DichVuTinhTien.tinh_gia_dong(self.kh_si, self.bt_si, 10)
        self.assertEqual(loai, LoaiGia.GIA_SI)
        self.assertEqual(thanh_tien, Decimal("400000"))

    def test_khach_si_chua_du_muc_thi_gia_le(self):
        loai, don_gia, thanh_tien = DichVuTinhTien.tinh_gia_dong(self.kh_si, self.bt_si, 9)
        self.assertEqual(loai, LoaiGia.GIA_LE)
        self.assertEqual(thanh_tien, Decimal("450000"))

    def test_bien_the_khong_co_gia_si_thi_gia_le(self):
        loai, don_gia, thanh_tien = DichVuTinhTien.tinh_gia_dong(self.kh_si, self.bt_le, 100)
        self.assertEqual(loai, LoaiGia.GIA_LE)
        self.assertEqual(don_gia, Decimal("30000"))

    # ----- xem_gio_hang (UC02 bước 1–2) -----
    def test_gio_trong(self):  # UC02-A2
        ket_qua = DichVuTinhTien.xem_gio_hang(self.kh_le)
        self.assertEqual(ket_qua["cac_dong"], [])
        self.assertEqual(ket_qua["tam_tinh"], Decimal("0"))

    def test_tam_tinh_chi_cong_dong_da_chon_va_con_ban(self):
        d1 = DichVuGioHang.them_vao_gio(self.kh_si, self.bt_si, 10)  # sỉ: 400.000
        DichVuGioHang.them_vao_gio(self.kh_si, self.bt_le, 2)        # không chọn
        bt_ngung = tao_bien_the("BT_G3", self.san_pham)
        d3 = DichVuGioHang.them_vao_gio(self.kh_si, bt_ngung, 1)
        bt_ngung.trang_thai = "INACTIVE"
        bt_ngung.save()

        ket_qua = DichVuTinhTien.xem_gio_hang(self.kh_si, [d1.ma_ctgh, d3.ma_ctgh])

        self.assertEqual(len(ket_qua["cac_dong"]), 3)        # vẫn hiện đủ 3 dòng
        self.assertEqual(ket_qua["tam_tinh"], Decimal("400000"))
        dong_ngung = ket_qua["cac_dong"][2]
        self.assertFalse(dong_ngung["con_ban"])               # UC02-E3: bị đánh dấu
        self.assertFalse(dong_ngung["da_chon"])               # và không được chọn

    def test_doi_so_luong_thi_doi_loai_gia(self):  # UC02 bước 2
        dong = DichVuGioHang.them_vao_gio(self.kh_si, self.bt_si, 9)
        ket_qua = DichVuTinhTien.xem_gio_hang(self.kh_si, [dong.ma_ctgh])
        self.assertEqual(ket_qua["cac_dong"][0]["loai_gia"], LoaiGia.GIA_LE)

        DichVuGioHang.cap_nhat_so_luong(self.kh_si, dong.ma_ctgh, 10)
        ket_qua = DichVuTinhTien.xem_gio_hang(self.kh_si, [dong.ma_ctgh])
        self.assertEqual(ket_qua["cac_dong"][0]["loai_gia"], LoaiGia.GIA_SI)

    # ----- lay_cac_dong_da_chon (UC02 bước 3) -----
    def test_mua_hang_chua_chon_dong(self):  # UC02-E1
        with self.assertRaises(LoiNghiepVuDonHang):
            DichVuTinhTien.lay_cac_dong_da_chon(self.kh_le, [])

    def test_mua_hang_co_dong_ngung_ban(self):  # UC02-E3
        dong = DichVuGioHang.them_vao_gio(self.kh_le, self.bt_si, 1)
        self.bt_si.trang_thai = "INACTIVE"
        self.bt_si.save()
        with self.assertRaises(LoiNghiepVuDonHang):
            DichVuTinhTien.lay_cac_dong_da_chon(self.kh_le, [dong.ma_ctgh])

    def test_mua_hang_bang_dong_cua_khach_khac(self):  # M3-BR24
        dong = DichVuGioHang.them_vao_gio(self.kh_le, self.bt_si, 1)
        with self.assertRaises(LoiQuyenDonHang):
            DichVuTinhTien.lay_cac_dong_da_chon(self.kh_si, [dong.ma_ctgh])

    # ----- tinh_tong_tien (UC03 bước 1, M3-BR06) -----
    def test_tong_thanh_toan_don_co_ca_dong_si_va_dong_le(self):
        d1 = DichVuGioHang.them_vao_gio(self.kh_si, self.bt_si, 10)  # sỉ: 10 x 40.000
        d2 = DichVuGioHang.them_vao_gio(self.kh_si, self.bt_le, 2)   # lẻ:  2 x 30.000
        tao_dia_chi("DC_G1", self.kh_si, tinh_thanh="Huế")          # miền Trung: 35.000

        ket_qua = DichVuTinhTien.tinh_tong_tien(self.kh_si, [d1.ma_ctgh, d2.ma_ctgh], "DC_G1")

        self.assertEqual(ket_qua["tong_tien_hang"], Decimal("460000"))
        self.assertEqual(ket_qua["phi_van_chuyen"], Decimal("35000"))
        self.assertEqual(ket_qua["tong_thanh_toan"], Decimal("495000"))
        self.assertEqual(ket_qua["tinh_thanh"].ma_tinh, "TT020")


# ==========================================================
# Phần 5: đặt hàng (M3-UC03)
# ==========================================================
class DuLieuDatHang:
    """
    Dữ liệu chung cho các lớp test đặt hàng. Không kế thừa TestCase nên
    Django không tự chạy lớp này; lớp test nào cần thì kế thừa nó cùng TestCase.
    """

    def setUp(self):
        self.kh = tao_khach_hang("KH_DH", "dh@test.vn", ma_loai="LKH002")  # khách sỉ
        danh_muc = DanhMucSanPham.objects.create(ma_dm="DM_D", ten_dm="Bánh test")
        self.san_pham = SanPham.objects.create(
            ma_sp="SP_D", danh_muc=danh_muc, ten_sp="Bánh dừa đặt hàng"
        )
        self.bt_si = tao_bien_the("BT_D1", self.san_pham, gia_le=50000, gia_si=40000)  # mức sỉ 10
        self.bt_le = tao_bien_the("BT_D2", self.san_pham, gia_le=30000)
        self.bt_khac = tao_bien_the("BT_D3", self.san_pham, gia_le=20000)

        self.d1 = DichVuGioHang.them_vao_gio(self.kh, self.bt_si, 10)   # sỉ: 10 x 40.000
        self.d2 = DichVuGioHang.them_vao_gio(self.kh, self.bt_le, 2)    # lẻ:  2 x 30.000
        self.d3 = DichVuGioHang.them_vao_gio(self.kh, self.bt_khac, 1)  # không chọn mua

        self.dia_chi = tao_dia_chi("DC_D1", self.kh, tinh_thanh="Huế")  # phí 35.000
        DiaChiKH.objects.filter(ma_dia_chi="DC_D1").update(phuong_xa="Phường Thuận Hòa")

    def dat(self, ma_pttt=PhuongThucThanhToan.MA_COD):
        """Đặt hai dòng d1, d2 về địa chỉ DC_D1."""
        return DichVuDatHang.dat_hang(
            self.kh, [self.d1.ma_ctgh, self.d2.ma_ctgh], "DC_D1", ma_pttt
        )


class KiemThuDatHang(DuLieuDatHang, TestCase):

    def test_tao_don_cho_xac_nhan_voi_tien_va_nguoi_nhan_chot_luc_dat(self):  # UC03 bước 4
        don = self.dat()

        self.assertEqual(don.ma_dh, "DH001")
        self.assertEqual(don.trang_thai, TrangThaiDonHang.CHO_XAC_NHAN)
        self.assertEqual(don.trang_thai_thanh_toan, TrangThaiThanhToan.CHUA_THANH_TOAN)
        self.assertEqual(don.loai_khach_hang_ap_dung_id, "LKH002")          # M3-BR02
        self.assertEqual(don.phuong_thuc_thanh_toan_id, PhuongThucThanhToan.MA_COD)
        self.assertEqual(don.ho_ten_nguoi_nhan, "Người nhận test")          # M3-BR08
        self.assertEqual(don.dia_chi_giao_hang, "12 Lê Lợi, Phường Thuận Hòa")
        self.assertEqual(don.tinh_thanh_id, "TT020")
        self.assertEqual(don.tong_tien_hang, Decimal("460000"))             # M3-BR06
        self.assertEqual(don.phi_van_chuyen, Decimal("35000"))
        self.assertEqual(don.tong_thanh_toan, Decimal("495000"))

    def test_dong_don_luu_dung_loai_gia(self):  # M3-BR04, M3-BR07
        don = self.dat()
        cac_dong = {d.bien_the_id: d for d in don.chi_tiet.all()}

        self.assertEqual(len(cac_dong), 2)
        self.assertEqual(cac_dong["BT_D1"].loai_gia_ap_dung, LoaiGia.GIA_SI)
        self.assertEqual(cac_dong["BT_D1"].don_gia, Decimal("40000"))
        self.assertEqual(cac_dong["BT_D1"].thanh_tien, Decimal("400000"))
        self.assertEqual(cac_dong["BT_D2"].loai_gia_ap_dung, LoaiGia.GIA_LE)
        self.assertEqual(cac_dong["BT_D2"].thanh_tien, Decimal("60000"))

    def test_ghi_dong_lich_su_dau_tien(self):  # M3-BR15
        don = self.dat()
        lich_su = LichSuTrangThaiDonHang.objects.filter(don_hang=don)

        self.assertEqual(lich_su.count(), 1)
        dong = lich_su.first()
        self.assertIsNone(dong.trang_thai_cu)
        self.assertEqual(dong.trang_thai, TrangThaiDonHang.CHO_XAC_NHAN)
        self.assertEqual(dong.tac_nhan, TacNhan.KHACH_HANG)
        self.assertIsNone(dong.nhan_vien)
        self.assertEqual(dong.thoi_diem, don.ngay_dat)

    def test_tao_giao_dich_chua_thanh_toan(self):  # M3-BR16
        don = self.dat(ma_pttt=PhuongThucThanhToan.MA_CHUYEN_KHOAN)
        giao_dich = GiaoDichThanhToan.objects.filter(don_hang=don)

        self.assertEqual(giao_dich.count(), 1)
        gd = giao_dich.first()
        self.assertEqual(gd.phuong_thuc_id, PhuongThucThanhToan.MA_CHUYEN_KHOAN)
        self.assertEqual(gd.so_tien_phai_thu, Decimal("495000"))
        self.assertEqual(gd.trang_thai, TrangThaiThanhToan.CHUA_THANH_TOAN)
        self.assertIsNone(gd.so_tien_thuc_nhan)

    def test_gio_chi_con_dong_khong_chon(self):  # M3-BR03
        self.dat()
        con_lai = list(
            ChiTietGioHang.objects.filter(gio_hang__khach_hang=self.kh)
            .values_list("ma_ctgh", flat=True)
        )
        self.assertEqual(con_lai, [self.d3.ma_ctgh])

    def test_chua_chon_phuong_thuc_thanh_toan(self):  # UC03-E1
        for ma in ("", None):
            with self.assertRaisesMessage(LoiNghiepVuDonHang, "Vui lòng chọn phương thức thanh toán"):
                self.dat(ma_pttt=ma)

        self.assertEqual(DonHang.objects.count(), 0)
        self.assertEqual(DichVuGioHang.dem_so_dong(self.kh), 3)  # giỏ giữ nguyên

    def test_phuong_thuc_khong_ton_tai(self):  # UC03-E1
        with self.assertRaises(LoiNghiepVuDonHang):
            self.dat(ma_pttt="PT999")
        self.assertEqual(DonHang.objects.count(), 0)

# ==========================================================
# Phần 6: đặt hàng – các trường hợp ngoại lệ (M3-UC03 E1–E6, M3-BR02, M3-BR07)
# ==========================================================
class KiemThuDatHangNgoaiLe(DuLieuDatHang, TestCase):

    def khong_co_gi_duoc_luu(self):
        """Không có đơn, dòng đơn, lịch sử, giao dịch; giỏ còn đủ 3 dòng."""
        self.assertEqual(DonHang.objects.count(), 0)
        self.assertEqual(ChiTietDonHang.objects.count(), 0)
        self.assertEqual(LichSuTrangThaiDonHang.objects.count(), 0)
        self.assertEqual(GiaoDichThanhToan.objects.count(), 0)
        self.assertEqual(DichVuGioHang.dem_so_dong(self.kh), 3)

    # ----- Dữ liệu chốt tại lúc đặt -----
    def test_doi_gia_va_phi_sau_khi_dat_khong_doi_don(self):  # M3-BR07
        don = self.dat()

        BienTheSanPham.objects.filter(ma_bien_the="BT_D1").update(gia_ban_le=99000, gia_ban_si=88000)
        TinhThanh.objects.filter(ma_tinh="TT020").update(phi_van_chuyen=99000)

        don.refresh_from_db()
        dong_si = don.chi_tiet.get(bien_the_id="BT_D1")
        self.assertEqual(dong_si.don_gia, Decimal("40000"))
        self.assertEqual(don.phi_van_chuyen, Decimal("35000"))
        self.assertEqual(don.tong_thanh_toan, Decimal("495000"))

    def test_doi_loai_khach_sau_khi_dat_khong_doi_don(self):  # M3-BR02
        don = self.dat()

        self.kh.loai_khach_hang = LoaiKhachHang.objects.get(ma_loai_kh="LKH001")
        self.kh.save()

        don.refresh_from_db()
        self.assertEqual(don.loai_khach_hang_ap_dung_id, "LKH002")

    # ----- Kiểm tra trước khi ghi: lỗi thì không lưu gì -----
    def test_phuong_thuc_da_tat(self):  # UC03-E1
        PhuongThucThanhToan.objects.filter(
            ma_pttt=PhuongThucThanhToan.MA_CHUYEN_KHOAN
        ).update(dang_kich_hoat=False)

        with self.assertRaisesMessage(LoiNghiepVuDonHang, "không hợp lệ"):
            self.dat(ma_pttt=PhuongThucThanhToan.MA_CHUYEN_KHOAN)
        self.khong_co_gi_duoc_luu()

    def test_co_dong_ngung_ban(self):  # UC03-E2
        self.bt_le.trang_thai = "INACTIVE"
        self.bt_le.save()

        with self.assertRaisesMessage(LoiNghiepVuDonHang, "không được bán"):
            self.dat()
        self.khong_co_gi_duoc_luu()

    def test_tinh_khong_co_trong_bang_phi(self):  # UC03-E4
        DiaChiKH.objects.filter(ma_dia_chi="DC_D1").update(tinh_thanh="Bình Dương")

        with self.assertRaises(LoiNghiepVuDonHang):
            self.dat()
        self.khong_co_gi_duoc_luu()

    def test_dia_chi_cua_khach_khac(self):  # M3-BR24, UC04 NFR
        kh_khac = tao_khach_hang("KH_KHAC", "khac@test.vn")
        tao_dia_chi("DC_KHAC", kh_khac)

        with self.assertRaises(LoiQuyenDonHang):
            DichVuDatHang.dat_hang(
                self.kh, [self.d1.ma_ctgh], "DC_KHAC", PhuongThucThanhToan.MA_COD
            )
        self.khong_co_gi_duoc_luu()

    def test_khach_ngung_hoat_dong(self):  # M3-BR01
        self.kh.trang_thai = KhachHang.TrangThai.INACTIVE
        self.kh.save()

        with self.assertRaises(LoiQuyenDonHang):
            self.dat()
        self.khong_co_gi_duoc_luu()

    # ----- Lỗi xảy ra giữa lúc ghi: phải hoàn tác toàn bộ -----
    def test_loi_giua_chung_hoan_tac_toan_bo(self):  # UC03-E5, M3-BR10
        # Thay tạm hàm tạo giao dịch bằng hàm ném lỗi CSDL. Lúc đó đơn, dòng đơn,
        # lịch sử đã được tạo trong transaction; tất cả phải bị hoàn tác.
        with patch.object(
            DichVuDatHang, "tao_giao_dich_thanh_toan", side_effect=DatabaseError("giả lập")
        ):
            with self.assertRaisesMessage(LoiNghiepVuDonHang, "Không thể đặt hàng"):
                self.dat()

        self.khong_co_gi_duoc_luu()

    def test_bam_dat_hang_lan_hai_bi_tu_choi(self):  # UC03-E6
        self.dat()

        with self.assertRaises(LoiNghiepVuDonHang):
            self.dat()  # các dòng d1, d2 đã rời khỏi giỏ

        self.assertEqual(DonHang.objects.count(), 1)

    def test_dong_bi_xoa_giua_chung_thi_hoan_tac(self):  # UC03-E6, chốt chặn ở loai_dong_khoi_gio
        ham_that = DichVuDatHang.tao_giao_dich_thanh_toan

        def yeu_cau_khac_chen_vao(don, thoi_diem):
            # Giả lập một yêu cầu khác vừa xóa dòng d2 khỏi giỏ
            ChiTietGioHang.objects.filter(ma_ctgh=self.d2.ma_ctgh).delete()
            return ham_that(don, thoi_diem)

        with patch.object(
            DichVuDatHang, "tao_giao_dich_thanh_toan", side_effect=yeu_cau_khac_chen_vao
        ):
            with self.assertRaisesMessage(LoiNghiepVuDonHang, "Giỏ hàng vừa thay đổi"):
                self.dat()

        # Lệnh xóa d2 cũng nằm trong transaction nên được hoàn tác theo
        self.khong_co_gi_duoc_luu()

    # ----- Sinh mã khi có nhiều đơn -----
    def test_hai_don_lien_tiep_co_ma_rieng(self):
        don_1 = self.dat()
        d4 = DichVuGioHang.them_vao_gio(self.kh, self.bt_si, 1)
        don_2 = DichVuDatHang.dat_hang(
            self.kh, [d4.ma_ctgh, self.d3.ma_ctgh], "DC_D1", PhuongThucThanhToan.MA_COD
        )

        self.assertEqual((don_1.ma_dh, don_2.ma_dh), ("DH001", "DH002"))
        self.assertEqual(
            sorted(ChiTietDonHang.objects.values_list("ma_ctdh", flat=True)),
            ["CT001", "CT002", "CT003", "CT004"],
        )
        self.assertEqual(GiaoDichThanhToan.objects.count(), 2)
        self.assertEqual(DichVuGioHang.dem_so_dong(self.kh), 0)


# ==========================================================
# Phần 7: phân quyền API phía khách hàng (orders/permissions.py)
# Gọi thẳng has_permission, chưa cần view: request giả chỉ cần thuộc tính .user
# ==========================================================
class KiemThuPhanQuyen(TestCase):

    def setUp(self):
        self.quyen = KhachHangCoHoSo()
        self.kh = tao_khach_hang("KH_PQ", "pq@test.vn")

    def kiem_tra(self, nguoi_dung):
        request_gia = SimpleNamespace(user=nguoi_dung)
        return self.quyen.has_permission(request_gia, None)

    def test_khach_co_ho_so_duoc_phep(self):
        self.assertTrue(self.kiem_tra(self.kh.tai_khoan))

    def test_chua_dang_nhap_bi_chan(self):
        self.assertFalse(self.kiem_tra(AnonymousUser()))

    def test_nhan_vien_bi_chan_du_co_ho_so_khach(self):
        # Đổi vai trò tài khoản của khách thành nhân viên: vẫn còn hồ sơ KhachHang,
        # nên chỉ bước kiểm tra vai trò (của M1) mới chặn được
        tai_khoan = self.kh.tai_khoan
        tai_khoan.vai_tro = TaiKhoan.VaiTro.EMPLOYEE
        tai_khoan.save()
        self.assertFalse(self.kiem_tra(tai_khoan))

    def test_tai_khoan_khach_chua_co_ho_so_bi_chan(self):
        tai_khoan = TaiKhoan.objects.create(ma_tk="TK_TRONG", email="trong@test.vn")
        self.assertFalse(self.kiem_tra(tai_khoan))
        self.assertEqual(self.quyen.message, "Tài khoản không có hồ sơ khách hàng.")

# ==========================================================
# Phần 8: serializer giỏ hàng (orders/serializers.py)
# ==========================================================
class KiemThuSerializerGioHang(TestCase):

    def setUp(self):
        self.kh = tao_khach_hang("KH_SR", "sr@test.vn", ma_loai="LKH002")  # khách sỉ
        danh_muc = DanhMucSanPham.objects.create(ma_dm="DM_S", ten_dm="Bánh test")
        self.san_pham = SanPham.objects.create(
            ma_sp="SP_S", danh_muc=danh_muc, ten_sp="Bánh dừa serializer"
        )
        self.bt = tao_bien_the("BT_S1", self.san_pham, gia_le=50000, gia_si=40000)  # mức sỉ 10

    def loi_cua(self, serializer, ten_truong):
        """Kiểm tra dữ liệu không hợp lệ và trả câu báo lỗi đầu tiên của trường."""
        self.assertFalse(serializer.is_valid())
        return str(serializer.errors[ten_truong][0])

    # ---------- Đầu vào: thêm vào giỏ ----------
    def test_them_hop_le_doi_ma_thanh_doi_tuong(self):
        sr = ThemVaoGioSerializer(data={"ma_bien_the": "BT_S1", "so_luong": "3"})
        self.assertTrue(sr.is_valid(), sr.errors)
        self.assertEqual(sr.validated_data["bien_the"], self.bt)
        self.assertEqual(sr.validated_data["so_luong"], 3)  # chuỗi "3" -> số 3

    def test_ma_bien_the_khong_ton_tai(self):
        sr = ThemVaoGioSerializer(data={"ma_bien_the": "BT_KHONG", "so_luong": 1})
        self.assertEqual(self.loi_cua(sr, "ma_bien_the"), "Không tìm thấy sản phẩm.")

    def test_thieu_ma_bien_the(self):
        sr = ThemVaoGioSerializer(data={"so_luong": 1})
        self.assertEqual(self.loi_cua(sr, "ma_bien_the"), "Vui lòng chọn sản phẩm.")

    def test_so_luong_khong_phai_so(self):
        for gia_tri in ["abc", "1.5", True]:
            with self.subTest(so_luong=gia_tri):
                sr = ThemVaoGioSerializer(data={"ma_bien_the": "BT_S1", "so_luong": gia_tri})
                self.assertEqual(
                    self.loi_cua(sr, "so_luong"), "Số lượng phải là số nguyên lớn hơn 0."
                )

    def test_so_luong_0_de_service_bao_loi(self):
        # Serializer chỉ kiểm định dạng; quy tắc "> 0" do service quyết định
        sr = ThemVaoGioSerializer(data={"ma_bien_the": "BT_S1", "so_luong": 0})
        self.assertTrue(sr.is_valid(), sr.errors)

    # ---------- Đầu vào: sửa số lượng ----------
    def test_cap_nhat_thieu_so_luong(self):
        sr = CapNhatSoLuongSerializer(data={})
        self.assertEqual(self.loi_cua(sr, "so_luong"), "Vui lòng nhập số lượng.")

    # ---------- Đầu ra: giỏ hàng ----------
    def test_dau_ra_gio_hang(self):
        dong = DichVuGioHang.them_vao_gio(self.kh, self.bt, 10)
        gio = DichVuTinhTien.xem_gio_hang(self.kh, [dong.ma_ctgh])

        du_lieu = GioHangSerializer(gio).data

        self.assertEqual(du_lieu["so_dong"], 1)
        self.assertEqual(du_lieu["tam_tinh"], 400000)  # số, không phải chuỗi
        dong_ra = du_lieu["cac_dong"][0]
        self.assertEqual(dong_ra["ma_ctgh"], dong.ma_ctgh)
        self.assertEqual(dong_ra["ma_bien_the"], "BT_S1")
        self.assertEqual(dong_ra["ten_sp"], "Bánh dừa serializer")
        self.assertEqual(dong_ra["loai_gia"], "GIA_SI")
        self.assertEqual(dong_ra["ten_loai_gia"], "Giá sỉ")
        self.assertEqual(dong_ra["don_gia"], 40000)
        self.assertEqual(dong_ra["thanh_tien"], 400000)
        self.assertTrue(dong_ra["da_chon"])

    def test_dau_ra_gio_trong(self):
        du_lieu = GioHangSerializer(DichVuTinhTien.xem_gio_hang(self.kh)).data
        self.assertEqual(du_lieu["so_dong"], 0)
        self.assertEqual(du_lieu["cac_dong"], [])
        self.assertEqual(du_lieu["tam_tinh"], 0)

# ==========================================================
# Phần 9: API giỏ hàng (views.py, urls.py) – gọi như trình duyệt gọi
# APIClient gửi request thật qua config/urls.py -> orders/urls.py -> view.
# force_authenticate: coi như đã đăng nhập bằng tài khoản này (M1 cũng dùng).
# ==========================================================
URL_GIO = "/api/orders/cart/"


class KiemThuApiGioHang(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.kh = tao_khach_hang("KH_API", "api@test.vn", ma_loai="LKH002")  # khách sỉ
        danh_muc = DanhMucSanPham.objects.create(ma_dm="DM_A", ten_dm="Bánh test")
        self.san_pham = SanPham.objects.create(
            ma_sp="SP_A", danh_muc=danh_muc, ten_sp="Bánh dừa API"
        )
        self.bt = tao_bien_the("BT_A1", self.san_pham, gia_le=50000, gia_si=40000)  # mức sỉ 10
        self.client.force_authenticate(user=self.kh.tai_khoan)

    def them(self, ma_bien_the="BT_A1", so_luong=2):
        return self.client.post(
            URL_GIO, {"ma_bien_the": ma_bien_the, "so_luong": so_luong}, format="json"
        )

    def url_dong(self, ma_ctgh):
        return f"{URL_GIO}{ma_ctgh}/"

    # ---------- Phân quyền ----------
    def test_chua_dang_nhap_bi_403(self):
        self.client.force_authenticate(user=None)  # đăng xuất
        self.assertEqual(self.client.get(URL_GIO).status_code, 403)

    def test_khach_ngung_hoat_dong_bi_403(self):
        # Sửa qua chính đối tượng self.kh rồi save(), không dùng .update():
        # force_authenticate giữ đúng đối tượng tài khoản này, và
        # tai_khoan.khach_hang trỏ tới self.kh đã nạp sẵn trong bộ nhớ
        self.kh.trang_thai = KhachHang.TrangThai.INACTIVE
        self.kh.save()
        phan_hoi = self.client.get(URL_GIO)
        self.assertEqual(phan_hoi.status_code, 403)
        self.assertIn("ngừng hoạt động", phan_hoi.data["message"])

    # ---------- UC01: thêm vào giỏ ----------
    def test_them_thanh_cong_tra_ca_gio(self):
        phan_hoi = self.them()
        self.assertEqual(phan_hoi.status_code, 200)
        self.assertEqual(phan_hoi.data["message"], "Đã thêm sản phẩm vào giỏ hàng.")
        self.assertEqual(phan_hoi.data["data"]["so_dong"], 1)
        self.assertEqual(phan_hoi.data["data"]["cac_dong"][0]["so_luong"], 2)

    def test_them_lai_cong_don(self):
        self.them(so_luong=2)
        phan_hoi = self.them(so_luong=3)
        self.assertEqual(phan_hoi.data["data"]["so_dong"], 1)
        self.assertEqual(phan_hoi.data["data"]["cac_dong"][0]["so_luong"], 5)

    def test_them_sai_dinh_dang_400_kem_loi_tung_truong(self):
        phan_hoi = self.them(so_luong="abc")
        self.assertEqual(phan_hoi.status_code, 400)
        self.assertEqual(phan_hoi.data["message"], "Dữ liệu không hợp lệ.")
        self.assertIn("so_luong", phan_hoi.data["errors"])
        self.assertEqual(ChiTietGioHang.objects.count(), 0)

    def test_them_bien_the_ngung_ban_400(self):
        BienTheSanPham.objects.filter(ma_bien_the="BT_A1").update(trang_thai="INACTIVE")
        phan_hoi = self.them()
        self.assertEqual(phan_hoi.status_code, 400)
        self.assertEqual(phan_hoi.data["message"], "Sản phẩm hiện không được bán.")

    # ---------- UC02: xem, sửa, xóa ----------
    def test_xem_gio_tinh_tam_tinh_theo_dong_chon(self):
        ma_ctgh = self.them(so_luong=2).data["data"]["cac_dong"][0]["ma_ctgh"]

        khong_chon = self.client.get(URL_GIO)
        co_chon = self.client.get(f"{URL_GIO}?chon={ma_ctgh}")

        self.assertEqual(khong_chon.data["data"]["tam_tinh"], 0)
        self.assertEqual(co_chon.data["data"]["tam_tinh"], 100000)  # 2 x 50.000

    def test_sua_so_luong_doi_sang_gia_si(self):
        ma_ctgh = self.them(so_luong=2).data["data"]["cac_dong"][0]["ma_ctgh"]

        phan_hoi = self.client.patch(
            f"{self.url_dong(ma_ctgh)}?chon={ma_ctgh}", {"so_luong": 10}, format="json"
        )

        self.assertEqual(phan_hoi.status_code, 200)
        dong = phan_hoi.data["data"]["cac_dong"][0]
        self.assertEqual(dong["loai_gia"], "GIA_SI")
        self.assertEqual(dong["don_gia"], 40000)
        self.assertEqual(phan_hoi.data["data"]["tam_tinh"], 400000)

    def test_sua_so_luong_0_bi_service_chan(self):
        ma_ctgh = self.them(so_luong=2).data["data"]["cac_dong"][0]["ma_ctgh"]
        phan_hoi = self.client.patch(self.url_dong(ma_ctgh), {"so_luong": 0}, format="json")
        self.assertEqual(phan_hoi.status_code, 400)
        self.assertEqual(phan_hoi.data["message"], "Số lượng phải là số nguyên lớn hơn 0.")

    def test_sua_dong_cua_khach_khac_bi_403(self):
        khach_khac = tao_khach_hang("KH_API2", "api2@test.vn")
        dong_khac = DichVuGioHang.them_vao_gio(khach_khac, self.bt, 1)

        phan_hoi = self.client.patch(
            self.url_dong(dong_khac.ma_ctgh), {"so_luong": 9}, format="json"
        )

        self.assertEqual(phan_hoi.status_code, 403)
        dong_khac.refresh_from_db()
        self.assertEqual(dong_khac.so_luong, 1)  # giỏ của khách kia không bị đổi

    def test_xoa_dong(self):
        ma_ctgh = self.them().data["data"]["cac_dong"][0]["ma_ctgh"]
        phan_hoi = self.client.delete(self.url_dong(ma_ctgh))
        self.assertEqual(phan_hoi.status_code, 200)
        self.assertEqual(phan_hoi.data["data"]["so_dong"], 0)

    def test_xoa_ma_khong_ton_tai_400(self):
        phan_hoi = self.client.delete(self.url_dong("CG999"))
        self.assertEqual(phan_hoi.status_code, 400)
        self.assertEqual(phan_hoi.data["message"], "Không tìm thấy dòng hàng trong giỏ.")

# ==========================================================
# Phần 10: API trang thanh toán và đặt hàng (M3-UC03, M3-UC04)
# Dùng lại DuLieuDatHang (phần 5): khách sỉ KH_DH; giỏ d1 BT_D1 x10 (sỉ 40.000),
# d2 BT_D2 x2 (lẻ 30.000), d3 BT_D3 x1 (không chọn); địa chỉ DC_D1 ở Huế (phí 35.000).
# Chọn d1, d2: tiền hàng 460.000 + phí 35.000 = 495.000.
# ==========================================================
URL_THANH_TOAN = "/api/orders/checkout/"
URL_DON_HANG = "/api/orders/"


class KiemThuApiThanhToanDatHang(DuLieuDatHang, TestCase):

    def setUp(self):
        super().setUp()  # chạy setUp của DuLieuDatHang để có khách, giỏ, địa chỉ
        self.client = APIClient()
        self.client.force_authenticate(user=self.kh.tai_khoan)

    def url_thanh_toan(self, *cac_ma, ma_dia_chi=None):
        url = URL_THANH_TOAN + "?" + "&".join(f"chon={ma}" for ma in cac_ma)
        if ma_dia_chi:
            url += f"&ma_dia_chi={ma_dia_chi}"
        return url

    def dat_qua_api(self, **thay_doi):
        du_lieu = {
            "chon": [self.d1.ma_ctgh, self.d2.ma_ctgh],
            "ma_dia_chi": "DC_D1",
            "ma_pttt": PhuongThucThanhToan.MA_COD,
        }
        du_lieu.update(thay_doi)
        return self.client.post(URL_DON_HANG, du_lieu, format="json")

    # ---------- Phân quyền ----------
    def test_chua_dang_nhap_bi_403(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.url_thanh_toan(self.d1.ma_ctgh)).status_code, 403)
        self.assertEqual(self.dat_qua_api().status_code, 403)

    # ---------- Trang thanh toán (GET checkout/) ----------
    def test_thanh_toan_dung_dia_chi_hien_thi_san(self):
        phan_hoi = self.client.get(self.url_thanh_toan(self.d1.ma_ctgh, self.d2.ma_ctgh))

        self.assertEqual(phan_hoi.status_code, 200)
        trang = phan_hoi.data["data"]
        self.assertEqual(trang["dia_chi"]["ma_dia_chi"], "DC_D1")
        self.assertEqual(trang["ten_tinh"], "Huế")
        self.assertEqual(len(trang["cac_dong"]), 2)
        self.assertEqual(trang["tong_tien_hang"], 460000)
        self.assertEqual(trang["phi_van_chuyen"], 35000)
        self.assertEqual(trang["tong_thanh_toan"], 495000)
        self.assertEqual(
            [pt["ma_pttt"] for pt in trang["cac_phuong_thuc"]],
            [PhuongThucThanhToan.MA_CHUYEN_KHOAN, PhuongThucThanhToan.MA_COD],
        )

    def test_doi_dia_chi_tinh_lai_phi(self):
        tao_dia_chi("DC_D2", self.kh, tinh_thanh="Đà Nẵng")  # phí 30.000
        phan_hoi = self.client.get(
            self.url_thanh_toan(self.d1.ma_ctgh, self.d2.ma_ctgh, ma_dia_chi="DC_D2")
        )
        self.assertEqual(phan_hoi.data["data"]["phi_van_chuyen"], 30000)
        self.assertEqual(phan_hoi.data["data"]["tong_thanh_toan"], 490000)

    def test_thanh_toan_khong_doi_gio(self):
        self.client.get(self.url_thanh_toan(self.d1.ma_ctgh, self.d2.ma_ctgh))
        self.assertEqual(DichVuGioHang.dem_so_dong(self.kh), 3)
        self.assertEqual(DonHang.objects.count(), 0)

    def test_chua_chon_dong_bao_truoc_ca_khi_chua_co_dia_chi(self):
        DiaChiKH.objects.filter(khach_hang=self.kh).delete()
        phan_hoi = self.client.get(URL_THANH_TOAN)
        self.assertEqual(phan_hoi.status_code, 400)
        self.assertEqual(phan_hoi.data["message"], "Vui lòng chọn sản phẩm cần mua.")

    def test_so_dia_chi_trong(self):
        DiaChiKH.objects.filter(khach_hang=self.kh).delete()
        phan_hoi = self.client.get(self.url_thanh_toan(self.d1.ma_ctgh))
        self.assertEqual(phan_hoi.status_code, 400)
        self.assertIn("chưa có địa chỉ giao hàng", phan_hoi.data["message"])

    def test_dia_chi_cua_khach_khac_403(self):
        khach_khac = tao_khach_hang("KH_KHAC", "khac@test.vn")
        tao_dia_chi("DC_KHAC", khach_khac)
        phan_hoi = self.client.get(self.url_thanh_toan(self.d1.ma_ctgh, ma_dia_chi="DC_KHAC"))
        self.assertEqual(phan_hoi.status_code, 403)

    def test_pttt_ngung_kich_hoat_khong_hien(self):
        PhuongThucThanhToan.objects.filter(
            ma_pttt=PhuongThucThanhToan.MA_CHUYEN_KHOAN
        ).update(dang_kich_hoat=False)
        phan_hoi = self.client.get(self.url_thanh_toan(self.d1.ma_ctgh))
        self.assertEqual(
            [pt["ma_pttt"] for pt in phan_hoi.data["data"]["cac_phuong_thuc"]],
            [PhuongThucThanhToan.MA_COD],
        )

    # ---------- Đặt hàng (POST /api/orders/) ----------
    def test_dat_hang_cod_thanh_cong(self):
        phan_hoi = self.dat_qua_api()

        self.assertEqual(phan_hoi.status_code, 201)
        don = phan_hoi.data["data"]
        self.assertEqual(phan_hoi.data["message"], f"Đặt hàng thành công. Mã đơn hàng: {don['ma_dh']}.")
        self.assertEqual(don["trang_thai"], "CHO_XAC_NHAN")
        self.assertEqual(don["ten_trang_thai"], "Chờ xác nhận")
        self.assertEqual(don["ten_trang_thai_thanh_toan"], "Chưa thanh toán")
        self.assertEqual(don["tong_thanh_toan"], 495000)
        self.assertEqual(don["ten_tinh"], "Huế")
        self.assertEqual(len(don["chi_tiet"]), 2)
        dong_si = next(d for d in don["chi_tiet"] if d["ma_bien_the"] == "BT_D1")
        self.assertEqual(dong_si["ten_loai_gia"], "Giá sỉ")
        self.assertEqual(dong_si["thanh_tien"], 400000)
        # Dòng d3 không chọn vẫn còn trong giỏ
        self.assertEqual(DichVuGioHang.dem_so_dong(self.kh), 1)

    def test_dat_hang_chuyen_khoan_bao_thanh_toan_sau(self):
        phan_hoi = self.dat_qua_api(ma_pttt=PhuongThucThanhToan.MA_CHUYEN_KHOAN)
        self.assertEqual(phan_hoi.status_code, 201)
        self.assertIn("sau khi đơn hàng được nhân viên xác nhận", phan_hoi.data["message"])

    def test_thieu_dia_chi_400_tu_serializer(self):
        phan_hoi = self.dat_qua_api(ma_dia_chi="")
        self.assertEqual(phan_hoi.status_code, 400)
        self.assertEqual(str(phan_hoi.data["errors"]["ma_dia_chi"][0]), "Vui lòng chọn địa chỉ giao hàng.")
        self.assertEqual(DonHang.objects.count(), 0)

    def test_thieu_pttt_400_tu_service(self):
        phan_hoi = self.dat_qua_api(ma_pttt="")
        self.assertEqual(phan_hoi.status_code, 400)
        self.assertEqual(phan_hoi.data["message"], "Vui lòng chọn phương thức thanh toán.")
        self.assertEqual(DonHang.objects.count(), 0)

    def test_chon_khong_phai_danh_sach(self):
        phan_hoi = self.dat_qua_api(chon=self.d1.ma_ctgh)  # chuỗi, không phải danh sách
        self.assertEqual(phan_hoi.status_code, 400)
        self.assertIn("chon", phan_hoi.data["errors"])

    def test_bam_dat_hang_hai_lan_chi_mot_don(self):
        self.assertEqual(self.dat_qua_api().status_code, 201)
        lan_hai = self.dat_qua_api()
        self.assertEqual(lan_hai.status_code, 400)
        self.assertEqual(DonHang.objects.count(), 1)

# ==========================================================
# 11. MODEL GIAOHANG (giai đoạn 4A) – ràng buộc ở mức CSDL
#     Service chưa có; test tạo thẳng bằng objects.create để chứng minh
#     CSDL tự chặn dữ liệu sai dù code service sau này có lỗi.
# ==========================================================
class KiemThuModelGiaoHang(DuLieuDatHang, TestCase):
    def setUp(self):
        super().setUp()
        self.don = self.dat()

    def tao_giao(self, ma, **thay_doi):
        du_lieu = {
            "ma_giao_hang": ma,
            "don_hang": self.don,
            "lan_giao": 1,
            "hinh_thuc_giao": HinhThucGiao.SHIPPER,
            "don_vi_van_chuyen": "Giao Hàng Nhanh",
        }
        du_lieu.update(thay_doi)
        return GiaoHang.objects.create(**du_lieu)

    def test_gia_tri_mac_dinh(self):
        giao = self.tao_giao("GH001")
        giao.refresh_from_db()
        self.assertEqual(giao.ket_qua_giao, KetQuaGiao.DANG_GIAO)
        self.assertEqual(giao.phi_phat_sinh, Decimal("0"))
        self.assertIsNotNone(giao.thoi_diem_ban_giao)
        self.assertEqual(list(self.don.giao_hang.all()), [giao])  # related_name="giao_hang"

    def test_ba_lan_giao_tren_cung_don(self):
        for lan in (1, 2, 3):
            self.tao_giao(f"GH00{lan}", lan_giao=lan)
        self.assertEqual(self.don.giao_hang.count(), 3)

    def test_trung_lan_giao_tren_cung_don_bi_chan(self):
        self.tao_giao("GH001", lan_giao=1)
        with self.assertRaises(IntegrityError):
            self.tao_giao("GH002", lan_giao=1)

    def test_ca_gia_tri_sai_bi_chan(self):
        cac_truong_hop = [
            {"lan_giao": 0},
            {"lan_giao": 4},
            {"phi_phat_sinh": Decimal("-1")},
            {"hinh_thuc_giao": "XE_MAY"},
            {"ket_qua_giao": "MAT_HANG"},
        ]
        for thay_doi in cac_truong_hop:
            with self.subTest(thay_doi=thay_doi):
                # Mỗi lần lỗi CSDL làm hỏng transaction hiện tại; bọc atomic
                # để lỗi chỉ hoàn tác lần thử này, test vẫn chạy tiếp được
                with self.assertRaises(IntegrityError), transaction.atomic():
                    self.tao_giao("GH009", **thay_doi)
        self.assertEqual(GiaoHang.objects.count(), 0)

# ==========================================================
# 12. MÁY TRẠNG THÁI (giai đoạn 4B) – M3-BR14, BR15, BR22, UC08 E1
#     Kiểm tra trên toàn bộ 10 x 10 cặp trạng thái: cạnh có trong bảng
#     thì đi được và ghi đúng một dòng lịch sử; cặp nào không có thì bị
#     từ chối và không để lại dấu vết.
# ==========================================================
class KiemThuMayTrangThai(DuLieuDatHang, TestCase):
    def setUp(self):
        super().setUp()
        self.don = self.dat()  # đơn COD ở "Chờ xác nhận", đã có 1 dòng lịch sử

    def dat_trang_thai(self, trang_thai):
        """Đặt thẳng trạng thái trong CSDL (bỏ qua máy trạng thái) để dựng tình huống test."""
        DonHang.objects.filter(pk=self.don.pk).update(trang_thai=trang_thai)
        self.don.refresh_from_db()

    def so_lich_su(self):
        return LichSuTrangThaiDonHang.objects.filter(don_hang=self.don).count()

    # ----- Bảng cạnh -----
    def test_bang_canh_co_du_10_trang_thai(self):
        # Thêm trạng thái mới vào models.py mà quên khai báo cạnh thì test này báo
        self.assertEqual(set(CAC_CANH_HOP_LE), set(TrangThaiDonHang.values))
        for dich in CAC_CANH_HOP_LE.values():
            self.assertTrue(dich <= set(TrangThaiDonHang.values))

    def test_trang_thai_cuoi_khong_co_canh_ra(self):
        self.assertEqual(TRANG_THAI_CUOI, {TrangThaiDonHang.HOAN_THANH, TrangThaiDonHang.DA_HUY})
        for trang_thai in TRANG_THAI_CUOI:
            self.assertEqual(CAC_CANH_HOP_LE[trang_thai], set())

    # ----- chuyen_trang_thai: cạnh hợp lệ -----
    def test_moi_canh_hop_le_deu_di_duoc_va_ghi_lich_su(self):
        for cu, cac_moi in CAC_CANH_HOP_LE.items():
            for moi in cac_moi:
                with self.subTest(canh=f"{cu} -> {moi}"):
                    self.dat_trang_thai(cu)
                    truoc = self.so_lich_su()
                    DichVuTrangThai.chuyen_trang_thai(self.don, moi, TacNhan.HE_THONG)
                    self.assertEqual(DonHang.objects.get(pk=self.don.pk).trang_thai, moi)
                    self.assertEqual(self.so_lich_su(), truoc + 1)
                    # Mỗi cạnh chỉ đi một lần trong vòng lặp nên đúng một dòng khớp
                    self.assertTrue(LichSuTrangThaiDonHang.objects.filter(
                        don_hang=self.don, trang_thai_cu=cu, trang_thai=moi
                    ).exists())

    # ----- chuyen_trang_thai: mọi cặp ngoài bảng bị từ chối -----
    def test_moi_cap_ngoai_bang_bi_tu_choi(self):
        for cu in TrangThaiDonHang.values:
            for moi in TrangThaiDonHang.values:
                if moi in CAC_CANH_HOP_LE[cu]:
                    continue
                with self.subTest(cap=f"{cu} -> {moi}"):
                    self.dat_trang_thai(cu)
                    truoc = self.so_lich_su()
                    with self.assertRaises(LoiNghiepVuDonHang):
                        DichVuTrangThai.chuyen_trang_thai(self.don, moi, TacNhan.HE_THONG)
                    self.assertEqual(DonHang.objects.get(pk=self.don.pk).trang_thai, cu)
                    self.assertEqual(self.so_lich_su(), truoc)

    def test_cau_bao_nhay_coc_va_trang_thai_cuoi(self):
        with self.assertRaisesMessage(
            LoiNghiepVuDonHang, 'Không thể chuyển đơn hàng từ "Chờ xác nhận" sang "Hoàn thành".'
        ):
            DichVuTrangThai.chuyen_trang_thai(self.don, TrangThaiDonHang.HOAN_THANH, TacNhan.NHAN_VIEN)

        self.dat_trang_thai(TrangThaiDonHang.DA_HUY)
        with self.assertRaisesMessage(LoiNghiepVuDonHang, 'đã ở trạng thái "Đã hủy"'):
            DichVuTrangThai.chuyen_trang_thai(self.don, TrangThaiDonHang.CHO_XAC_NHAN, TacNhan.NHAN_VIEN)

    # ----- Ghi lịch sử và cột đi kèm -----
    def test_ghi_lich_su_day_du_va_cot_di_kem(self):
        moc = timezone.now() - timedelta(minutes=5)
        DichVuTrangThai.chuyen_trang_thai(
            self.don, TrangThaiDonHang.DA_XAC_NHAN, TacNhan.NHAN_VIEN,
            ghi_chu="Đủ hàng", thoi_diem=moc,
            cap_nhat_them={"thoi_diem_xac_nhan": moc},
        )
        # Đối tượng trong bộ nhớ đã được gán lại
        self.assertEqual(self.don.trang_thai, TrangThaiDonHang.DA_XAC_NHAN)
        self.assertEqual(self.don.thoi_diem_xac_nhan, moc)
        # CSDL cũng đúng
        trong_csdl = DonHang.objects.get(pk=self.don.pk)
        self.assertEqual(trong_csdl.thoi_diem_xac_nhan, moc)
        dong = LichSuTrangThaiDonHang.objects.filter(
            don_hang=self.don, trang_thai=TrangThaiDonHang.DA_XAC_NHAN
        ).get()
        self.assertEqual(dong.trang_thai_cu, TrangThaiDonHang.CHO_XAC_NHAN)
        self.assertEqual(dong.tac_nhan, TacNhan.NHAN_VIEN)
        self.assertEqual(dong.thoi_diem, moc)
        self.assertEqual(dong.ghi_chu, "Đủ hàng")

    def test_hai_buoc_lien_tiep_tren_cung_doi_tuong(self):
        # Kiểu xác nhận đơn chuyển khoản ở bước 4C: hai lần chuyển liền nhau
        DichVuTrangThai.chuyen_trang_thai(self.don, TrangThaiDonHang.DA_XAC_NHAN, TacNhan.NHAN_VIEN)
        DichVuTrangThai.chuyen_trang_thai(self.don, TrangThaiDonHang.CHO_THANH_TOAN, TacNhan.HE_THONG)
        self.assertEqual(DonHang.objects.get(pk=self.don.pk).trang_thai, TrangThaiDonHang.CHO_THANH_TOAN)
        self.assertEqual(self.so_lich_su(), 3)  # đặt hàng + 2 lần chuyển

    def test_dong_lich_su_giu_nguyen_trang_thai(self):
        # UC09, UC10-A1: ghi lịch sử mà không đổi trạng thái
        DichVuTrangThai.ghi_lich_su(
            self.don, TrangThaiDonHang.CHO_XAC_NHAN, TrangThaiDonHang.CHO_XAC_NHAN,
            TacNhan.NHAN_VIEN, ghi_chu="Kiểm tra hàng: đủ",
        )
        self.assertEqual(self.so_lich_su(), 2)
        self.assertEqual(DonHang.objects.get(pk=self.don.pk).trang_thai, TrangThaiDonHang.CHO_XAC_NHAN)

    # ----- Compare-and-set: hai người cùng thao tác (UC08 E1) -----
    def test_nguoi_thu_hai_bi_tu_choi_khi_don_vua_doi(self):
        ban_cua_a = DonHang.objects.get(pk=self.don.pk)
        ban_cua_b = DonHang.objects.get(pk=self.don.pk)  # cả hai cùng đọc "Chờ xác nhận"
        DichVuTrangThai.chuyen_trang_thai(ban_cua_a, TrangThaiDonHang.DA_XAC_NHAN, TacNhan.NHAN_VIEN)
        with self.assertRaisesMessage(LoiNghiepVuDonHang, "vừa được người khác xử lý"):
            DichVuTrangThai.chuyen_trang_thai(ban_cua_b, TrangThaiDonHang.CHO_BO_SUNG, TacNhan.NHAN_VIEN)
        self.assertEqual(DonHang.objects.get(pk=self.don.pk).trang_thai, TrangThaiDonHang.DA_XAC_NHAN)
        self.assertEqual(self.so_lich_su(), 2)

    # ----- Transaction: lỗi khi ghi lịch sử thì trạng thái cũng hoàn tác -----
    def test_loi_ghi_lich_su_hoan_tac_trang_thai(self):
        with patch.object(DichVuTrangThai, "ghi_lich_su", side_effect=DatabaseError("giả lập")):
            with self.assertRaises(DatabaseError):
                DichVuTrangThai.chuyen_trang_thai(self.don, TrangThaiDonHang.DA_XAC_NHAN, TacNhan.NHAN_VIEN)
        self.assertEqual(DonHang.objects.get(pk=self.don.pk).trang_thai, TrangThaiDonHang.CHO_XAC_NHAN)
        self.assertEqual(self.so_lich_su(), 1)


# ==========================================================
# 13. XỬ LÝ ĐƠN PHÍA NHÂN VIÊN (giai đoạn 4C)
#     M3-UC09 kiểm tra hàng, M3-UC08 xác nhận đơn, M3-UC10 thiếu hàng.
#     Đơn mẫu: d1 (10 cái) và d2 (2 cái), COD, đang "Chờ xác nhận".
# ==========================================================
class KiemThuXuLyDonNhanVien(DuLieuDatHang, TestCase):
    def setUp(self):
        super().setUp()
        self.nv = tao_nhan_vien()
        self.don = self.dat()
        self.dong_1, self.dong_2 = self.don.chi_tiet.order_by("ma_ctdh")
        self.ngay_mai = timezone.now() + timedelta(days=1)

    def kiem_tra(self, thieu_dong_1=0, thieu_dong_2=0):
        return DichVuXuLyDon.kiem_tra_kha_nang_cung_ung(
            self.don, self.nv, {self.dong_1.ma_ctdh: thieu_dong_1, self.dong_2.ma_ctdh: thieu_dong_2}
        )

    def trang_thai_csdl(self):
        return DonHang.objects.get(pk=self.don.pk).trang_thai

    def so_lich_su(self):
        return LichSuTrangThaiDonHang.objects.filter(don_hang=self.don).count()

    # ----- UC09 -----
    def test_kiem_tra_du_hang_ghi_tung_dong_va_lich_su(self):
        self.assertTrue(self.kiem_tra())
        self.dong_1.refresh_from_db()
        self.assertEqual(self.dong_1.ket_qua_kiem_tra, KetQuaKiemTra.DU)
        dong_ls = LichSuTrangThaiDonHang.objects.filter(don_hang=self.don).order_by("-ma_lstt").first()
        self.assertEqual(dong_ls.trang_thai_cu, dong_ls.trang_thai)  # giữ nguyên trạng thái
        self.assertEqual(dong_ls.nhan_vien, self.nv)
        self.assertIn("đủ hàng", dong_ls.ghi_chu)

    def test_kiem_tra_thieu_mot_phan_so_luong(self):
        # A1: thiếu 3 trên 10 cái vẫn tính là thiếu hàng
        self.assertFalse(self.kiem_tra(thieu_dong_1=3))
        self.dong_1.refresh_from_db()
        self.assertEqual(self.dong_1.ket_qua_kiem_tra, KetQuaKiemTra.THIEU)
        self.assertEqual(self.dong_1.so_luong_thieu, 3)

    def test_kiem_tra_con_dong_chua_danh_dau(self):
        # E1: chỉ gửi kết quả một dòng
        with self.assertRaisesMessage(LoiNghiepVuDonHang, "Còn dòng hàng chưa được đánh dấu"):
            DichVuXuLyDon.kiem_tra_kha_nang_cung_ung(self.don, self.nv, {self.dong_1.ma_ctdh: 0})
        self.dong_1.refresh_from_db()
        self.assertEqual(self.dong_1.ket_qua_kiem_tra, KetQuaKiemTra.CHUA_KIEM_TRA)
        self.assertEqual(self.so_lich_su(), 1)

    # ----- UC08 -----
    def test_xac_nhan_don_cod_dung_o_da_xac_nhan(self):
        self.kiem_tra()
        DichVuXuLyDon.xac_nhan_don(self.don, self.nv)
        don = DonHang.objects.get(pk=self.don.pk)
        self.assertEqual(don.trang_thai, TrangThaiDonHang.DA_XAC_NHAN)
        self.assertEqual(don.nhan_vien_xac_nhan, self.nv)
        self.assertIsNotNone(don.thoi_diem_xac_nhan)
        self.assertEqual(self.so_lich_su(), 3)  # đặt hàng + kiểm tra + xác nhận

    def test_xac_nhan_don_chuyen_khoan_sang_cho_thanh_toan(self):
        DonHang.objects.filter(pk=self.don.pk).update(
            phuong_thuc_thanh_toan_id=PhuongThucThanhToan.MA_CHUYEN_KHOAN
        )
        self.don.refresh_from_db()
        self.kiem_tra()
        DichVuXuLyDon.xac_nhan_don(self.don, self.nv)
        self.assertEqual(self.trang_thai_csdl(), TrangThaiDonHang.CHO_THANH_TOAN)
        hai_dong_cuoi = LichSuTrangThaiDonHang.objects.filter(don_hang=self.don).order_by("-ma_lstt")[:2]
        self.assertEqual(
            [(d.trang_thai, d.tac_nhan) for d in hai_dong_cuoi],
            [(TrangThaiDonHang.CHO_THANH_TOAN, TacNhan.HE_THONG),
             (TrangThaiDonHang.DA_XAC_NHAN, TacNhan.NHAN_VIEN)],
        )

    def test_xac_nhan_khi_chua_kiem_tra_hoac_thieu_bi_tu_choi(self):
        with self.assertRaisesMessage(LoiNghiepVuDonHang, "đủ hàng ở mọi dòng"):
            DichVuXuLyDon.xac_nhan_don(self.don, self.nv)
        self.kiem_tra(thieu_dong_2=1)
        with self.assertRaisesMessage(LoiNghiepVuDonHang, "đủ hàng ở mọi dòng"):
            DichVuXuLyDon.xac_nhan_don(self.don, self.nv)
        self.assertEqual(self.trang_thai_csdl(), TrangThaiDonHang.CHO_XAC_NHAN)

    def test_xac_nhan_khi_co_yeu_cau_huy_bi_tu_choi(self):
        # E2 / BR19: M4 đã ghi CHO_HUY
        self.kiem_tra()
        DonHang.objects.filter(pk=self.don.pk).update(trang_thai_hau_mai=MA_HAU_MAI_CHO_HUY)
        self.don.refresh_from_db()
        with self.assertRaisesMessage(LoiNghiepVuDonHang, "yêu cầu hủy chờ xử lý"):
            DichVuXuLyDon.xac_nhan_don(self.don, self.nv)
        self.assertEqual(self.trang_thai_csdl(), TrangThaiDonHang.CHO_XAC_NHAN)

    def test_loi_khi_luu_bao_loi_va_giu_nguyen(self):
        # E4: lỗi CSDL giữa chừng -> báo câu tiếng Việt, đơn không đổi
        self.kiem_tra()
        with patch.object(DichVuTrangThai, "ghi_lich_su", side_effect=DatabaseError("giả lập")):
            with self.assertRaisesMessage(LoiNghiepVuDonHang, "Không thể lưu thao tác"):
                DichVuXuLyDon.xac_nhan_don(self.don, self.nv)
        don = DonHang.objects.get(pk=self.don.pk)
        self.assertEqual(don.trang_thai, TrangThaiDonHang.CHO_XAC_NHAN)
        self.assertIsNone(don.nhan_vien_xac_nhan)

    # ----- UC10 -----
    def test_chuyen_cho_bo_sung_luu_buoc_truoc_va_hen(self):
        self.kiem_tra(thieu_dong_1=3)
        DichVuXuLyDon.chuyen_cho_bo_sung(self.don, self.nv, self.ngay_mai, "Chờ lô mới")
        don = DonHang.objects.get(pk=self.don.pk)
        self.assertEqual(don.trang_thai, TrangThaiDonHang.CHO_BO_SUNG)
        self.assertEqual(don.trang_thai_truoc_cho_bo_sung, TrangThaiDonHang.CHO_XAC_NHAN)
        self.assertEqual(don.thoi_diem_hen_cung_cap, self.ngay_mai)

    def test_hen_o_qua_khu_bi_tu_choi(self):
        # E1
        self.kiem_tra(thieu_dong_1=3)
        with self.assertRaisesMessage(LoiNghiepVuDonHang, "phải ở tương lai"):
            DichVuXuLyDon.chuyen_cho_bo_sung(self.don, self.nv, timezone.now() - timedelta(hours=1))
        self.assertEqual(self.trang_thai_csdl(), TrangThaiDonHang.CHO_XAC_NHAN)

    def test_gia_han_doi_hen_giu_nguyen_trang_thai(self):
        # A1
        self.kiem_tra(thieu_dong_1=3)
        DichVuXuLyDon.chuyen_cho_bo_sung(self.don, self.nv, self.ngay_mai)
        hen_moi = self.ngay_mai + timedelta(days=1)
        truoc = self.so_lich_su()
        DichVuXuLyDon.gia_han_hen(self.don, self.nv, hen_moi)
        don = DonHang.objects.get(pk=self.don.pk)
        self.assertEqual(don.trang_thai, TrangThaiDonHang.CHO_BO_SUNG)
        self.assertEqual(don.thoi_diem_hen_cung_cap, hen_moi)
        self.assertEqual(self.so_lich_su(), truoc + 1)

    def test_da_du_hang_quay_ve_dung_buoc_truoc(self):
        for buoc_truoc in (TrangThaiDonHang.CHO_XAC_NHAN, TrangThaiDonHang.DANG_CHUAN_BI):
            with self.subTest(buoc_truoc=buoc_truoc):
                DonHang.objects.filter(pk=self.don.pk).update(trang_thai=buoc_truoc)
                self.don.refresh_from_db()
                self.kiem_tra(thieu_dong_1=3)
                DichVuXuLyDon.chuyen_cho_bo_sung(self.don, self.nv, self.ngay_mai)
                DichVuXuLyDon.da_du_hang(self.don, self.nv)

                don = DonHang.objects.get(pk=self.don.pk)
                self.assertEqual(don.trang_thai, buoc_truoc)
                self.assertIsNone(don.trang_thai_truoc_cho_bo_sung)
                self.dong_1.refresh_from_db()
                self.assertEqual(self.dong_1.ket_qua_kiem_tra, KetQuaKiemTra.DU)
                self.assertEqual(self.dong_1.so_luong_thieu, 0)

        # Quay về Chờ xác nhận với mọi dòng đủ thì xác nhận được ngay
        DonHang.objects.filter(pk=self.don.pk).update(trang_thai=TrangThaiDonHang.CHO_XAC_NHAN)
        self.don.refresh_from_db()
        DichVuXuLyDon.xac_nhan_don(self.don, self.nv)
        self.assertEqual(self.trang_thai_csdl(), TrangThaiDonHang.DA_XAC_NHAN)


# ==========================================================
# 14. THANH TOÁN (giai đoạn 4D) – M3-UC11, M3-BR17, BR18, BR22
#     Cổng giả lập chuyển khoản, thu tiền COD, hủy đơn quá hạn 24 giờ,
#     xét hoàn thành đơn.
# ==========================================================
class KiemThuThanhToan(DuLieuDatHang, TestCase):
    def setUp(self):
        super().setUp()
        self.nv = tao_nhan_vien()

    def qua_kiem_tra_va_xac_nhan(self, don):
        cac_dong = {ma: 0 for ma in don.chi_tiet.values_list("ma_ctdh", flat=True)}
        DichVuXuLyDon.kiem_tra_kha_nang_cung_ung(don, self.nv, cac_dong)
        return DichVuXuLyDon.xac_nhan_don(don, self.nv)

    def don_cho_thanh_toan(self):
        """Đơn chuyển khoản d1 + d2 đã xác nhận, đang "Chờ thanh toán"."""
        return self.qua_kiem_tra_va_xac_nhan(self.dat(ma_pttt=PhuongThucThanhToan.MA_CHUYEN_KHOAN))

    def don_cod_giao_thanh_cong(self, cua_so_da_dong=True):
        """Đơn COD đặt thẳng về "Giao thành công" để test UC11 phần COD."""
        don = self.dat()
        DonHang.objects.filter(pk=don.pk).update(
            trang_thai=TrangThaiDonHang.GIAO_THANH_CONG,
            thoi_diem_giao_thanh_cong=timezone.now() - timedelta(days=1),
            thoi_diem_xac_nhan_nhan_hang=timezone.now() if cua_so_da_dong else None,
        )
        don.refresh_from_db()
        return don

    def lui_gio_xac_nhan(self, don, so_gio):
        DonHang.objects.filter(pk=don.pk).update(thoi_diem_xac_nhan=timezone.now() - timedelta(hours=so_gio))
        don.refresh_from_db()

    def so_lich_su(self, don):
        return LichSuTrangThaiDonHang.objects.filter(don_hang=don).count()

    # ----- Chuyển khoản qua cổng giả lập -----
    def test_gia_lap_thanh_cong(self):
        don = self.don_cho_thanh_toan()
        truoc = self.so_lich_su(don)
        DichVuThanhToan.thanh_toan_gia_lap(don, self.kh, thanh_cong=True)

        don.refresh_from_db()
        self.assertEqual(don.trang_thai_thanh_toan, TrangThaiThanhToan.DA_THANH_TOAN)
        self.assertEqual(don.trang_thai, TrangThaiDonHang.CHO_THANH_TOAN)  # trạng thái xử lý không đổi
        self.assertEqual(self.so_lich_su(don), truoc)
        giao_dich = DichVuThanhToan.lay_giao_dich(don)
        self.assertEqual(giao_dich.trang_thai, TrangThaiThanhToan.DA_THANH_TOAN)
        self.assertEqual(giao_dich.so_tien_thuc_nhan, Decimal("495000"))
        self.assertIsNotNone(giao_dich.ma_giao_dich_ngan_hang)
        self.assertIsNone(giao_dich.nhan_vien_ghi_nhan)

    def test_gia_lap_that_bai_roi_thu_lai(self):
        don = self.don_cho_thanh_toan()
        DichVuThanhToan.thanh_toan_gia_lap(don, self.kh, thanh_cong=False)
        don.refresh_from_db()
        self.assertEqual(don.trang_thai_thanh_toan, TrangThaiThanhToan.THAT_BAI)
        self.assertEqual(DichVuThanhToan.lay_giao_dich(don).trang_thai, TrangThaiThanhToan.CHUA_THANH_TOAN)

        DichVuThanhToan.thanh_toan_gia_lap(don, self.kh, thanh_cong=True)
        don.refresh_from_db()
        self.assertEqual(don.trang_thai_thanh_toan, TrangThaiThanhToan.DA_THANH_TOAN)

    def test_gia_lap_don_cua_nguoi_khac_bi_chan(self):
        don = self.don_cho_thanh_toan()
        khach_khac = tao_khach_hang("KH_KHAC", "khac@test.vn")
        with self.assertRaises(LoiQuyenDonHang):
            DichVuThanhToan.thanh_toan_gia_lap(don, khach_khac, thanh_cong=True)

    def test_gia_lap_khong_ghi_trung(self):
        # E3
        don = self.don_cho_thanh_toan()
        DichVuThanhToan.thanh_toan_gia_lap(don, self.kh, thanh_cong=True)
        self.lui_gio_xac_nhan(don, 25)  # đã trả rồi thì quá 24 giờ cũng không bị hủy
        with self.assertRaisesMessage(LoiNghiepVuDonHang, "đã được thanh toán trước đó"):
            DichVuThanhToan.thanh_toan_gia_lap(don, self.kh, thanh_cong=True)
        self.assertEqual(DonHang.objects.get(pk=don.pk).trang_thai, TrangThaiDonHang.CHO_THANH_TOAN)

    def test_gia_lap_qua_han_thi_huy_va_tu_choi(self):
        don = self.don_cho_thanh_toan()
        self.lui_gio_xac_nhan(don, 25)
        with self.assertRaisesMessage(LoiNghiepVuDonHang, "quá hạn thanh toán"):
            DichVuThanhToan.thanh_toan_gia_lap(don, self.kh, thanh_cong=True)
        self.assertEqual(DonHang.objects.get(pk=don.pk).trang_thai, TrangThaiDonHang.DA_HUY)

    # ----- Hủy đơn quá hạn (tác vụ định kỳ) -----
    def test_huy_qua_han_chi_huy_don_chua_tra_va_chay_lai_khong_doi(self):
        don_qua_han = self.don_cho_thanh_toan()  # d1 + d2
        don_da_tra = self.qua_kiem_tra_va_xac_nhan(DichVuDatHang.dat_hang(
            self.kh, [self.d3.ma_ctgh], "DC_D1", PhuongThucThanhToan.MA_CHUYEN_KHOAN
        ))
        DichVuThanhToan.thanh_toan_gia_lap(don_da_tra, self.kh, thanh_cong=True)
        self.lui_gio_xac_nhan(don_qua_han, 25)
        self.lui_gio_xac_nhan(don_da_tra, 25)

        self.assertEqual(DichVuThanhToan.huy_don_qua_han_thanh_toan(), 1)
        self.assertEqual(DichVuThanhToan.huy_don_qua_han_thanh_toan(), 0)  # chạy lại không đổi
        self.assertEqual(DonHang.objects.get(pk=don_qua_han.pk).trang_thai, TrangThaiDonHang.DA_HUY)
        self.assertEqual(DonHang.objects.get(pk=don_da_tra.pk).trang_thai, TrangThaiDonHang.CHO_THANH_TOAN)
        dong_huy = LichSuTrangThaiDonHang.objects.get(don_hang=don_qua_han, trang_thai=TrangThaiDonHang.DA_HUY)
        self.assertEqual(dong_huy.tac_nhan, TacNhan.HE_THONG)

    def test_chua_qua_han_khong_huy(self):
        don = self.don_cho_thanh_toan()
        self.lui_gio_xac_nhan(don, 23)
        self.assertEqual(DichVuThanhToan.huy_don_qua_han_thanh_toan(), 0)

    # ----- COD -----
    def test_cod_thu_du_va_hoan_thanh(self):
        don = self.don_cod_giao_thanh_cong()
        DichVuThanhToan.ghi_nhan_thu_cod(don, self.nv, Decimal("495000"))

        don = DonHang.objects.get(pk=don.pk)
        self.assertEqual(don.trang_thai_thanh_toan, TrangThaiThanhToan.DA_THANH_TOAN)
        self.assertEqual(don.trang_thai, TrangThaiDonHang.HOAN_THANH)
        self.assertIsNotNone(don.thoi_diem_hoan_thanh)
        self.assertEqual(DichVuThanhToan.lay_giao_dich(don).nhan_vien_ghi_nhan, self.nv)

    def test_cod_cua_so_con_mo_thi_chua_hoan_thanh(self):
        don = self.don_cod_giao_thanh_cong(cua_so_da_dong=False)
        DichVuThanhToan.ghi_nhan_thu_cod(don, self.nv, Decimal("495000"))
        don = DonHang.objects.get(pk=don.pk)
        self.assertEqual(don.trang_thai_thanh_toan, TrangThaiThanhToan.DA_THANH_TOAN)
        self.assertEqual(don.trang_thai, TrangThaiDonHang.GIAO_THANH_CONG)

    def test_cod_thieu_tien_tu_choi_thua_tien_ghi_chu(self):
        # E2
        don = self.don_cod_giao_thanh_cong(cua_so_da_dong=False)
        with self.assertRaisesMessage(LoiNghiepVuDonHang, "ít hơn số tiền phải thu"):
            DichVuThanhToan.ghi_nhan_thu_cod(don, self.nv, Decimal("490000"))
        self.assertEqual(DonHang.objects.get(pk=don.pk).trang_thai_thanh_toan, TrangThaiThanhToan.CHUA_THANH_TOAN)

        DichVuThanhToan.ghi_nhan_thu_cod(don, self.nv, Decimal("500000"))
        giao_dich = DichVuThanhToan.lay_giao_dich(don)
        self.assertEqual(giao_dich.so_tien_thuc_nhan, Decimal("500000"))
        self.assertIn("Nhận thừa 5000", giao_dich.ghi_chu)

    def test_cod_khi_chua_giao_thanh_cong_bi_tu_choi(self):
        # E1, BR18
        don = self.dat()
        with self.assertRaisesMessage(LoiNghiepVuDonHang, "ghi nhận thu tiền COD"):
            DichVuThanhToan.ghi_nhan_thu_cod(don, self.nv, Decimal("495000"))

    def test_con_doi_tra_dang_mo_thi_chua_hoan_thanh(self):
        # BR22: M4 đang xử lý đổi/trả
        don = self.don_cod_giao_thanh_cong()
        DonHang.objects.filter(pk=don.pk).update(trang_thai_hau_mai=MA_HAU_MAI_CHO_DOI_TRA)
        don.refresh_from_db()
        DichVuThanhToan.ghi_nhan_thu_cod(don, self.nv, Decimal("495000"))
        self.assertEqual(DonHang.objects.get(pk=don.pk).trang_thai, TrangThaiDonHang.GIAO_THANH_CONG)


# ==========================================================
# 15. CHUẨN BỊ VÀ BÀN GIAO HÀNG (giai đoạn 4E) – M3-UC12, BR19, BR20
# ==========================================================
class KiemThuChuanBiBanGiao(DuLieuDatHang, TestCase):
    def setUp(self):
        super().setUp()
        self.nv = tao_nhan_vien()

    def don_da_xac_nhan(self, ma_pttt=PhuongThucThanhToan.MA_COD):
        """Đơn d1 + d2 đã kiểm tra đủ hàng và xác nhận (COD: Đã xác nhận; CK: Chờ thanh toán)."""
        don = self.dat(ma_pttt=ma_pttt)
        cac_dong = {ma: 0 for ma in don.chi_tiet.values_list("ma_ctdh", flat=True)}
        DichVuXuLyDon.kiem_tra_kha_nang_cung_ung(don, self.nv, cac_dong)
        return DichVuXuLyDon.xac_nhan_don(don, self.nv)

    def don_san_sang_giao(self):
        don = self.don_da_xac_nhan()
        DichVuGiaoHang.bat_dau_chuan_bi(don, self.nv)
        return DichVuGiaoHang.san_sang_giao(don, self.nv)

    def don_dang_giao(self):
        return DichVuGiaoHang.ban_giao(self.don_san_sang_giao(), self.nv, HinhThucGiao.SHIPPER, "Giao nhanh A")

    def dat_cho_huy(self, don):
        DonHang.objects.filter(pk=don.pk).update(trang_thai_hau_mai=MA_HAU_MAI_CHO_HUY)
        don.refresh_from_db()

    # ----- Bước 1: bắt đầu chuẩn bị -----
    def test_bat_dau_chuan_bi_cod_ghi_moc(self):
        don = DichVuGiaoHang.bat_dau_chuan_bi(self.don_da_xac_nhan(), self.nv)
        trong_csdl = DonHang.objects.get(pk=don.pk)
        self.assertEqual(trong_csdl.trang_thai, TrangThaiDonHang.DANG_CHUAN_BI)
        self.assertIsNotNone(trong_csdl.thoi_diem_bat_dau_chuan_bi)

    def test_moc_bat_dau_chuan_bi_chi_ghi_mot_lan(self):
        don = self.don_da_xac_nhan()
        moc_cu = timezone.now() - timedelta(hours=3)
        DonHang.objects.filter(pk=don.pk).update(thoi_diem_bat_dau_chuan_bi=moc_cu)
        don.refresh_from_db()
        DichVuGiaoHang.bat_dau_chuan_bi(don, self.nv)
        self.assertEqual(DonHang.objects.get(pk=don.pk).thoi_diem_bat_dau_chuan_bi, moc_cu)

    def test_chuyen_khoan_phai_thanh_toan_truoc(self):
        # E1
        don = self.don_da_xac_nhan(ma_pttt=PhuongThucThanhToan.MA_CHUYEN_KHOAN)
        with self.assertRaisesMessage(LoiNghiepVuDonHang, "chưa được thanh toán"):
            DichVuGiaoHang.bat_dau_chuan_bi(don, self.nv)
        DichVuThanhToan.thanh_toan_gia_lap(don, self.kh, thanh_cong=True)
        DichVuGiaoHang.bat_dau_chuan_bi(don, self.nv)
        self.assertEqual(DonHang.objects.get(pk=don.pk).trang_thai, TrangThaiDonHang.DANG_CHUAN_BI)

    def test_co_yeu_cau_huy_khong_cho_chuan_bi(self):
        # E2
        don = self.don_da_xac_nhan()
        self.dat_cho_huy(don)
        with self.assertRaisesMessage(LoiNghiepVuDonHang, "yêu cầu hủy chờ xử lý"):
            DichVuGiaoHang.bat_dau_chuan_bi(don, self.nv)

    # ----- Bước 2 -----
    def test_san_sang_giao_khong_nhay_coc(self):
        # E4: chưa bắt đầu chuẩn bị thì chưa sẵn sàng giao được
        don = self.don_da_xac_nhan()
        with self.assertRaisesMessage(LoiNghiepVuDonHang, "Không thể chuyển sẵn sàng giao"):
            DichVuGiaoHang.san_sang_giao(don, self.nv)
        DichVuGiaoHang.bat_dau_chuan_bi(don, self.nv)
        DichVuGiaoHang.san_sang_giao(don, self.nv)
        self.assertEqual(DonHang.objects.get(pk=don.pk).trang_thai, TrangThaiDonHang.SAN_SANG_GIAO)

    # ----- Bước 3–4: bàn giao -----
    def test_goi_y_hinh_thuc_theo_loai_khach(self):
        don = self.dat()  # khách sỉ
        self.assertEqual(DichVuGiaoHang.goi_y_hinh_thuc_giao(don), HinhThucGiao.XE_TAI)
        DonHang.objects.filter(pk=don.pk).update(loai_khach_hang_ap_dung_id="LKH001")
        don.refresh_from_db()
        self.assertEqual(DichVuGiaoHang.goi_y_hinh_thuc_giao(don), HinhThucGiao.SHIPPER)

    def test_ban_giao_tao_lan_giao_dau_tien(self):
        don = self.don_dang_giao()
        trong_csdl = DonHang.objects.get(pk=don.pk)
        self.assertEqual(trong_csdl.trang_thai, TrangThaiDonHang.DANG_GIAO)
        self.assertIsNotNone(trong_csdl.thoi_diem_ban_giao)
        giao = GiaoHang.objects.get(don_hang=don)
        self.assertEqual((giao.ma_giao_hang, giao.lan_giao), ("GH001", 1))
        self.assertEqual(giao.ket_qua_giao, KetQuaGiao.DANG_GIAO)
        self.assertEqual(giao.don_vi_van_chuyen, "Giao nhanh A")
        self.assertEqual(giao.thoi_diem_ban_giao, trong_csdl.thoi_diem_ban_giao)

    def test_ban_giao_chua_chon_hinh_thuc_va_xe_tai_tu_dien_don_vi(self):
        don = self.don_san_sang_giao()
        with self.assertRaisesMessage(LoiNghiepVuDonHang, "chọn hình thức giao"):  # E3
            DichVuGiaoHang.ban_giao(don, self.nv, "")
        DichVuGiaoHang.ban_giao(don, self.nv, HinhThucGiao.XE_TAI)
        self.assertEqual(GiaoHang.objects.get(don_hang=don).don_vi_van_chuyen, "Xe nội bộ Quý Thu")

    def test_ban_giao_khi_co_yeu_cau_huy_bi_tu_choi(self):
        # E2
        don = self.don_san_sang_giao()
        self.dat_cho_huy(don)
        with self.assertRaisesMessage(LoiNghiepVuDonHang, "yêu cầu hủy chờ xử lý"):
            DichVuGiaoHang.ban_giao(don, self.nv, HinhThucGiao.SHIPPER, "Giao nhanh A")
        self.assertFalse(GiaoHang.objects.filter(don_hang=don).exists())

    def test_loi_luu_ban_giao_hoan_tac_ca_trang_thai(self):
        # E5: tạo bản ghi giao lỗi thì đơn vẫn "Sẵn sàng giao"
        don = self.don_san_sang_giao()
        with patch.object(GiaoHang.objects, "create", side_effect=DatabaseError("giả lập")):
            with self.assertRaisesMessage(LoiNghiepVuDonHang, "Không thể lưu thao tác"):
                DichVuGiaoHang.ban_giao(don, self.nv, HinhThucGiao.SHIPPER, "Giao nhanh A")
        trong_csdl = DonHang.objects.get(pk=don.pk)
        self.assertEqual(trong_csdl.trang_thai, TrangThaiDonHang.SAN_SANG_GIAO)
        self.assertIsNone(trong_csdl.thoi_diem_ban_giao)

    # ----- A2: giao lại cho M4 -----
    def test_giao_lai_dong_lan_cu_tao_lan_moi(self):
        don = self.don_dang_giao()
        moc_ban_giao_dau = DonHang.objects.get(pk=don.pk).thoi_diem_ban_giao
        DichVuGiaoHang.tao_lan_giao_lai(
            don, self.nv, KetQuaGiao.KHACH_TU_CHOI, "Khách không nghe máy", HinhThucGiao.SHIPPER, "Giao nhanh B"
        )
        lan_1, lan_2 = GiaoHang.objects.filter(don_hang=don).order_by("lan_giao")
        self.assertEqual(lan_1.ket_qua_giao, KetQuaGiao.KHACH_TU_CHOI)
        self.assertEqual(lan_1.ly_do_that_bai, "Khách không nghe máy")
        self.assertEqual((lan_2.lan_giao, lan_2.ket_qua_giao), (2, KetQuaGiao.DANG_GIAO))
        trong_csdl = DonHang.objects.get(pk=don.pk)
        self.assertEqual(trong_csdl.trang_thai, TrangThaiDonHang.DANG_GIAO)
        self.assertEqual(trong_csdl.so_lan_giao_lai, 1)
        self.assertEqual(trong_csdl.thoi_diem_ban_giao, moc_ban_giao_dau)

    def test_giao_lai_toi_da_hai_lan(self):
        don = self.don_dang_giao()
        for _ in range(2):
            DichVuGiaoHang.tao_lan_giao_lai(don, self.nv, KetQuaGiao.THAT_BAI, "Sai địa chỉ",
                                            HinhThucGiao.SHIPPER, "Giao nhanh A")
        with self.assertRaisesMessage(LoiNghiepVuDonHang, "giao lại tối đa 2 lần"):
            DichVuGiaoHang.tao_lan_giao_lai(don, self.nv, KetQuaGiao.THAT_BAI, "Sai địa chỉ",
                                            HinhThucGiao.SHIPPER, "Giao nhanh A")
        self.assertEqual(GiaoHang.objects.filter(don_hang=don).count(), 3)