# File: backend/orders/tests.py
# Kiểm thử tự động cho Module 3.
# Chạy: python manage.py test orders
#
# Mỗi lần chạy, Django tạo một CSDL test trống, chạy toàn bộ migration
# (nên có sẵn 34 tỉnh, 2 PTTT, 2 loại khách), chạy test rồi xóa CSDL đó.
# db.sqlite3 thật trên máy không bị đụng tới.

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from customers.models import DiaChiKH, KhachHang, LoaiKhachHang, TaiKhoan
from products.models import BienTheSanPham, DanhMucSanPham, SanPham

from .models import (
    ChiTietGioHang,
    DonHang,
    GiaoDichThanhToan,
    GioHang,
    LichSuTrangThaiDonHang,
    LoaiGia,
    PhuongThucThanhToan,
    TacNhan,
    TinhThanh,
    TrangThaiDonHang,
    TrangThaiThanhToan,
)
from .services import (
    DichVuDatHang,
    DichVuDiaChiGiaoHang,
    DichVuGioHang,
    DichVuTinhTien,
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
        tao_dia_chi("DC_T1", self.kh, tinh_thanh="Thành phố Đà Nẵng")
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
# Phần 4: đặt hàng (M3-UC03)
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