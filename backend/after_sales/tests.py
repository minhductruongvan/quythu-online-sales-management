# File: backend/after_sales/tests.py
# Kiểm thử tự động cho Module 4.  Chạy: python manage.py test after_sales
# Dữ liệu đơn hàng dựng bằng hàm đặt hàng của M3 (DuLieuDatHang), sau đó ép trạng thái bằng .update()
# để mô phỏng các giai đoạn mà M3 sẽ đưa đơn tới (giao hàng, giao thành công...).

from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
import tempfile

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from orders.models import (
    DonHang, GiaoDichThanhToan, GiaoHang, HinhThucGiao, KetQuaGiao, TrangThaiDonHang as T, TrangThaiThanhToan,
)
from orders.tests import DuLieuDatHang, tao_khach_hang, tao_nhan_vien

from .models import (
    AnhMinhChung, BienDongKho, DongDoiTra, GiaoDichHoanTien, LichSuHauMai, LichSuNguyenNhan, NguyenNhan,
    NguonHoanTien, ThongBaoHauMai, TrangThaiDoiTra, TrangThaiHoanTien, TrangThaiYeuCauHuy, XuLyGiaoThatBai,
    YeuCauDoiTra, YeuCauHuy,
)
from .services import (
    DichVuDoiTra, DichVuGiaoThatBai, DichVuHoanTien, DichVuHuyDon, DichVuLichSu, DichVuNguyenNhan, DichVuThongKe,
    LoiNghiepVuHauMai, LoiQuyenHauMai, che_bot, giai_ma, ma_hoa,
)

# Mã nguyên nhân tạo sẵn trong migration 0002
NN_HUY, NN_HUY_KHAC = "NN001", "NN004"
NN_GIAO, NN_DOI_LOI, NN_DOI_KHONG_NHU_CAU = "NN005", "NN009", "NN012"


class NenHauMai(DuLieuDatHang):
    """Dữ liệu chung: một khách (sỉ), một đơn DH001 đang Chờ xác nhận, một nhân viên."""

    def setUp(self):
        super().setUp()
        self.nv = tao_nhan_vien("NV_M4")
        self.don = self.dat()

    def dat_trang_thai(self, trang_thai, **them):
        DonHang.objects.filter(pk=self.don.pk).update(trang_thai=trang_thai, **them)
        self.don.refresh_from_db()

    def da_thanh_toan(self):
        DonHang.objects.filter(pk=self.don.pk).update(trang_thai_thanh_toan=TrangThaiThanhToan.DA_THANH_TOAN)
        self.don.refresh_from_db()

    def dang_giao(self, lan=1):
        self.dat_trang_thai(T.DANG_GIAO)
        return GiaoHang.objects.create(
            ma_giao_hang=f"GH_M4{lan}", don_hang=self.don, lan_giao=lan, hinh_thuc_giao=HinhThucGiao.SHIPPER,
            don_vi_van_chuyen="GHN")

    def da_giao_thanh_cong(self, cach_day=timedelta(days=1)):
        self.dat_trang_thai(T.GIAO_THANH_CONG, thoi_diem_giao_thanh_cong=timezone.now() - cach_day)

    def dong_dau(self):
        return self.don.chi_tiet.order_by("ma_ctdh").first()

    def gui_doi_tra(self, hinh_thuc="TRA", nn=NN_DOI_KHONG_NHU_CAU, so_luong=1, anh=None, ghi_chu=""):
        ct = self.dong_dau()
        return DichVuDoiTra.gui_yeu_cau(
            self.don.ma_dh, self.kh, hinh_thuc, nn, ghi_chu, [{"ma_ctdh": ct.ma_ctdh, "so_luong": so_luong}], anh=anh)


# ==========================================================
# UC01 – Hủy đơn (BR01, BR03, BR04, BR08)
# ==========================================================
class KiemThuHuyDon(NenHauMai, TestCase):

    def test_gui_yeu_cau_dat_hau_mai_cho_huy(self):
        yc = DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)
        self.don.refresh_from_db()
        self.assertEqual(yc.trang_thai, TrangThaiYeuCauHuy.CHO_XU_LY)
        self.assertEqual(self.don.trang_thai, T.CHO_XAC_NHAN)  # chưa hủy, chờ nhân viên
        self.assertEqual(self.don.trang_thai_hau_mai, "CHO_HUY")
        self.assertTrue(ThongBaoHauMai.objects.exists())

    def test_khong_gui_hai_yeu_cau_cung_luc(self):  # BR03
        DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)
        self.assertEqual(YeuCauHuy.objects.count(), 1)

    def test_db_chan_hai_yeu_cau_cho_xu_ly(self):  # BR03 ở mức CSDL
        yc = DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)
        with self.assertRaises(IntegrityError), transaction.atomic():
            YeuCauHuy.objects.create(ma_yc_huy="YH999", don_hang=self.don, nguyen_nhan=yc.nguyen_nhan,
                                     trang_thai=TrangThaiYeuCauHuy.CHO_XU_LY)

    def test_don_dang_giao_khong_duoc_huy(self):  # BR01
        self.dang_giao()
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)

    def test_phai_chon_nguyen_nhan_va_ghi_chu_khi_bat_buoc(self):
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, "")
        with self.assertRaises(LoiNghiepVuHauMai):  # "Khác" bắt buộc ghi chú
            DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY_KHAC, "")
        DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY_KHAC, "Lý do riêng")

    def test_khach_khac_khong_huy_duoc_don(self):
        khac = tao_khach_hang("KH_X", "x@test.vn")
        with self.assertRaises(LoiQuyenHauMai):
            DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, khac, NN_HUY)

    def test_thu_hoi_tra_hau_mai_ve_cu(self):
        yc = DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)
        DichVuHuyDon.thu_hoi(yc.ma_yc_huy, self.kh)
        self.don.refresh_from_db()
        yc.refresh_from_db()
        self.assertEqual(yc.trang_thai, TrangThaiYeuCauHuy.THU_HOI)
        self.assertIsNone(self.don.trang_thai_hau_mai)

    def test_duyet_huy_don_chua_thanh_toan_khong_hoan_tien(self):  # BR08
        yc = DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)
        DichVuHuyDon.xu_ly(yc.ma_yc_huy, self.nv, "DUYET")
        self.don.refresh_from_db()
        self.assertEqual(self.don.trang_thai, T.DA_HUY)
        self.assertFalse(GiaoDichHoanTien.objects.exists())

    def test_duyet_huy_don_da_thanh_toan_tao_khoan_hoan(self):  # BR08, BR09
        self.da_thanh_toan()
        yc = DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)
        DichVuHuyDon.xu_ly(yc.ma_yc_huy, self.nv, "DUYET")
        khoan = GiaoDichHoanTien.objects.get()
        self.assertEqual(khoan.nguon, NguonHoanTien.HUY_DON)
        self.assertEqual(khoan.trang_thai, TrangThaiHoanTien.CHO_HOAN)
        self.assertEqual(khoan.so_tien_de_xuat, self.don.tong_thanh_toan)

    def test_duyet_huy_hoan_lai_ton_kho(self):  # BR04
        yc = DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)
        DichVuHuyDon.xu_ly(yc.ma_yc_huy, self.nv, "DUYET")
        self.assertTrue(BienDongKho.objects.filter(don_hang=self.don).exists())

    def test_tu_choi_can_ly_do_va_khoi_phuc_hau_mai(self):
        yc = DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuHuyDon.xu_ly(yc.ma_yc_huy, self.nv, "TU_CHOI", "")
        DichVuHuyDon.xu_ly(yc.ma_yc_huy, self.nv, "TU_CHOI", "Hàng đã đóng gói", "ghi chú nội bộ")
        self.don.refresh_from_db()
        self.assertEqual(self.don.trang_thai, T.CHO_XAC_NHAN)
        self.assertIsNone(self.don.trang_thai_hau_mai)

    def test_xu_ly_lan_hai_bi_chan(self):
        yc = DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)
        DichVuHuyDon.xu_ly(yc.ma_yc_huy, self.nv, "DUYET")
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuHuyDon.xu_ly(yc.ma_yc_huy, self.nv, "DUYET")

    def test_don_da_sang_van_chuyen_luc_duyet_thi_hoan_tac(self):  # UC02 E2
        yc = DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)
        self.dat_trang_thai(T.DANG_GIAO)
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuHuyDon.xu_ly(yc.ma_yc_huy, self.nv, "DUYET")
        yc.refresh_from_db()
        self.assertEqual(yc.trang_thai, TrangThaiYeuCauHuy.CHO_XU_LY)  # transaction đã hoàn tác

    def test_xu_ly_hang_loat_bao_ket_qua_tung_yeu_cau(self):
        yc = DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)
        kq = DichVuHuyDon.xu_ly_hang_loat([yc.ma_yc_huy, "YH_KHONG_CO"], self.nv)
        self.assertTrue(kq[0]["thanh_cong"])
        self.assertFalse(kq[1]["thanh_cong"])

    def test_timeline_bat_bien_va_co_moc(self):  # BR13
        yc = DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)
        moc = LichSuHauMai.objects.filter(ma_yeu_cau=yc.ma_yc_huy).first()
        self.assertIsNotNone(moc)
        moc.ghi_chu = "sửa"
        with self.assertRaises(Exception):
            moc.save()
        with self.assertRaises(Exception):
            moc.delete()


# ==========================================================
# UC03 – Giao không thành công (BR02, BR04, BR05, BR08)
# ==========================================================
class KiemThuGiaoThatBai(NenHauMai, TestCase):

    def test_giao_lai_can_ngay_giao_lai(self):
        self.dang_giao()
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuGiaoThatBai.xu_ly(self.don.ma_dh, self.nv, NN_GIAO, "GIAO_LAI")
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuGiaoThatBai.xu_ly(self.don.ma_dh, self.nv, NN_GIAO, "GIAO_LAI",
                                   ngay_giao_lai=timezone.localdate() - timedelta(days=1))

    def test_giao_lai_tao_lan_giao_moi_va_giu_dang_giao(self):  # BR02
        self.dang_giao()
        xl = DichVuGiaoThatBai.xu_ly(self.don.ma_dh, self.nv, NN_GIAO, "GIAO_LAI",
                                    ngay_giao_lai=timezone.localdate() + timedelta(days=1))
        self.don.refresh_from_db()
        self.assertEqual(self.don.trang_thai, T.DANG_GIAO)
        self.assertEqual(self.don.giao_hang.count(), 2)
        self.assertEqual(xl.lan_giao, 1)
        self.assertEqual(self.don.giao_hang.get(lan_giao=1).ket_qua_giao, KetQuaGiao.THAT_BAI)

    def test_khong_xu_ly_hai_lan_cung_lan_giao(self):
        self.dang_giao()
        DichVuGiaoThatBai.xu_ly(self.don.ma_dh, self.nv, NN_GIAO, "HOAN_VE_KHO")
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuGiaoThatBai.xu_ly(self.don.ma_dh, self.nv, NN_GIAO, "HOAN_VE_KHO")

    def test_lan_giao_thu_ba_bat_buoc_hoan_ve_kho(self):  # BR05
        self.dang_giao(lan=3)
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuGiaoThatBai.xu_ly(self.don.ma_dh, self.nv, NN_GIAO, "GIAO_LAI",
                                   ngay_giao_lai=timezone.localdate() + timedelta(days=1))
        DichVuGiaoThatBai.xu_ly(self.don.ma_dh, self.nv, NN_GIAO, "HOAN_VE_KHO")

    def test_hoan_ve_kho_huy_don_roi_nhap_kho_hoan_ton_va_tien(self):  # BR04, BR08
        self.da_thanh_toan()
        gh = self.dang_giao()
        xl = DichVuGiaoThatBai.xu_ly(self.don.ma_dh, self.nv, NN_GIAO, "HOAN_VE_KHO", khach_tu_choi=True)
        self.don.refresh_from_db()
        gh.refresh_from_db()
        self.assertEqual(self.don.trang_thai, T.DA_HUY)
        self.assertEqual(gh.ket_qua_giao, KetQuaGiao.KHACH_TU_CHOI)
        self.assertEqual(self.don.trang_thai_hau_mai, "DANG_HOAN_VE_KHO")
        DichVuGiaoThatBai.xac_nhan_nhap_kho(xl.ma_xu_ly, self.nv)
        xl.refresh_from_db()
        self.assertTrue(xl.da_nhap_kho)
        self.assertTrue(BienDongKho.objects.filter(don_hang=self.don).exists())
        self.assertTrue(GiaoDichHoanTien.objects.filter(don_hang=self.don).exists())
        with self.assertRaises(LoiNghiepVuHauMai):  # không nhập kho hai lần
            DichVuGiaoThatBai.xac_nhan_nhap_kho(xl.ma_xu_ly, self.nv)

    def test_don_khong_dang_giao_bi_chan(self):
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuGiaoThatBai.xu_ly(self.don.ma_dh, self.nv, NN_GIAO, "HOAN_VE_KHO")


# ==========================================================
# UC04, UC05 – Đổi/trả (BR06, BR07, BR16, BR17)
# ==========================================================
class KiemThuDoiTra(NenHauMai, TestCase):

    def setUp(self):
        super().setUp()
        self.da_giao_thanh_cong()

    def test_gui_tra_hang_hop_le(self):
        yc = self.gui_doi_tra()
        self.don.refresh_from_db()
        self.assertEqual(yc.trang_thai, TrangThaiDoiTra.CHO_XU_LY)
        self.assertEqual(self.don.trang_thai_hau_mai, "CHO_DOI_TRA")
        self.assertEqual(DongDoiTra.objects.filter(yeu_cau=yc).count(), 1)

    def test_qua_han_doi_tra(self):  # BR06
        self.da_giao_thanh_cong(cach_day=timedelta(days=8))
        with self.assertRaises(LoiNghiepVuHauMai):
            self.gui_doi_tra()

    def test_don_chua_giao_thanh_cong(self):
        self.dat_trang_thai(T.DANG_GIAO)
        with self.assertRaises(LoiNghiepVuHauMai):
            self.gui_doi_tra()

    def test_so_luong_vuot_so_da_mua(self):  # BR17
        with self.assertRaises(LoiNghiepVuHauMai):
            self.gui_doi_tra(so_luong=self.dong_dau().so_luong + 1)

    def test_khong_gui_trung_dong_dang_cho(self):
        self.gui_doi_tra()
        with self.assertRaises(LoiNghiepVuHauMai):
            self.gui_doi_tra()

    def test_nguyen_nhan_loi_bat_buoc_anh(self):  # BR07, E4
        with self.assertRaises(LoiNghiepVuHauMai):
            self.gui_doi_tra(nn=NN_DOI_LOI)

    def test_doi_hang_can_chon_bien_the_thay_the(self):
        ct = self.dong_dau()
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuDoiTra.gui_yeu_cau(self.don.ma_dh, self.kh, "DOI", NN_DOI_KHONG_NHU_CAU, "",
                                     [{"ma_ctdh": ct.ma_ctdh, "so_luong": 1}])

    def test_thu_hoi(self):
        yc = self.gui_doi_tra()
        DichVuDoiTra.thu_hoi(yc.ma_yc_doi_tra, self.kh)
        yc.refresh_from_db()
        self.assertEqual(yc.trang_thai, TrangThaiDoiTra.THU_HOI)

    def test_tu_choi_can_ly_do(self):
        yc = self.gui_doi_tra()
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuDoiTra.tu_choi(yc.ma_yc_doi_tra, self.nv, "")
        DichVuDoiTra.tu_choi(yc.ma_yc_doi_tra, self.nv, "Quá điều kiện")
        yc.refresh_from_db()
        self.assertEqual(yc.trang_thai, TrangThaiDoiTra.TU_CHOI)

    def _duyet_va_nhan(self, ket_qua="DAT"):
        yc = self.gui_doi_tra()
        DichVuDoiTra.duyet(yc.ma_yc_doi_tra, self.nv)
        yc.refresh_from_db()
        self.assertEqual(yc.trang_thai, TrangThaiDoiTra.DANG_CHO_NHAN_HANG)
        dong = DongDoiTra.objects.get(yeu_cau=yc)
        return yc, DichVuDoiTra.nhan_hang(
            yc.ma_yc_doi_tra, self.nv, [{"ma_dong": dong.ma_dong, "ket_qua": ket_qua}], ghi_chu="Hàng hỏng")

    def test_tra_hang_dat_tao_khoan_hoan_va_nhap_kho(self):  # BR07, BR09
        self.da_thanh_toan()
        yc, yc2 = self._duyet_va_nhan("DAT")
        self.assertEqual(yc2.trang_thai, TrangThaiDoiTra.DA_NHAN_HANG)
        DichVuDoiTra.hoan_tat(yc.ma_yc_doi_tra, self.nv)
        yc.refresh_from_db()
        self.assertEqual(yc.trang_thai, TrangThaiDoiTra.HOAN_TAT)
        khoan = GiaoDichHoanTien.objects.get(don_hang=self.don)
        self.assertEqual(khoan.nguon, NguonHoanTien.TRA_HANG)
        ct = self.dong_dau()
        self.assertEqual(khoan.so_tien_de_xuat, ct.don_gia * 1)  # hoàn đúng 1 sản phẩm trả
        self.assertTrue(BienDongKho.objects.filter(don_hang=self.don).exists())

    def test_hang_khong_dat_bi_tu_choi_va_khong_hoan_tien(self):  # BR16
        self.da_thanh_toan()
        yc, yc2 = self._duyet_va_nhan("KHONG_DAT")
        self.assertEqual(yc2.trang_thai, TrangThaiDoiTra.TU_CHOI)
        self.assertFalse(GiaoDichHoanTien.objects.exists())

    def test_het_han_gui_hang_dong_yeu_cau_va_tra_so_luong(self):  # BR06, BR16
        yc = self.gui_doi_tra()
        DichVuDoiTra.duyet(yc.ma_yc_doi_tra, self.nv)
        YeuCauDoiTra.objects.filter(pk=yc.pk).update(han_gui_hang=timezone.now() - timedelta(days=1))
        so = DichVuDoiTra.dong_yeu_cau_het_han()
        yc.refresh_from_db()
        self.assertEqual(yc.trang_thai, TrangThaiDoiTra.HET_HAN_GUI_HANG)
        self.assertTrue(so >= 1 if so is not None else True)
        self.gui_doi_tra()  # số lượng đã được giải phóng, gửi lại được

    def test_khach_khac_khong_gui_duoc(self):
        khac = tao_khach_hang("KH_Y", "y@test.vn")
        with self.assertRaises(LoiQuyenHauMai):
            DichVuDoiTra.gui_yeu_cau(self.don.ma_dh, khac, "TRA", NN_DOI_KHONG_NHU_CAU, "",
                                     [{"ma_ctdh": self.dong_dau().ma_ctdh, "so_luong": 1}])


# ==========================================================
# UC06 – Hoàn tiền (BR09, BR10, BR11)
# ==========================================================
class KiemThuHoanTien(NenHauMai, TestCase):

    def _khoan(self):
        self.da_thanh_toan()
        yc = DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)
        DichVuHuyDon.xu_ly(yc.ma_yc_huy, self.nv, "DUYET")
        return GiaoDichHoanTien.objects.get()

    def test_xac_nhan_da_hoan_va_khoa_giao_dich(self):
        khoan = self._khoan()
        kq = DichVuHoanTien.xac_nhan_da_hoan(
            khoan.ma_hoan_tien, self.nv, so_tien=khoan.so_tien_de_xuat, phuong_thuc="CHUYEN_KHOAN",
            ma_giao_dich_hoan="MGD1", thong_tin_tai_khoan="0123456789")
        self.assertEqual(kq.trang_thai, TrangThaiHoanTien.DA_HOAN)
        with self.assertRaises(Exception):  # bất biến sau khi đã hoàn
            kq.so_tien_hoan = 1
            kq.save()
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuHoanTien.xac_nhan_da_hoan(
                khoan.ma_hoan_tien, self.nv, so_tien=khoan.so_tien_de_xuat, phuong_thuc="CHUYEN_KHOAN",
                ma_giao_dich_hoan="MGD2", thong_tin_tai_khoan="0123456789")

    def test_khong_hoan_vuot_so_da_thanh_toan(self):
        khoan = self._khoan()
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuHoanTien.xac_nhan_da_hoan(
                khoan.ma_hoan_tien, self.nv, so_tien=khoan.so_tien_de_xuat + 1, phuong_thuc="CHUYEN_KHOAN",
                ma_giao_dich_hoan="MGD3", thong_tin_tai_khoan="0123456789")

    def test_hoan_thieu_phai_co_ly_do_dieu_chinh(self):  # UC06 A1
        khoan = self._khoan()
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuHoanTien.xac_nhan_da_hoan(
                khoan.ma_hoan_tien, self.nv, "MA_GD_1", so_tien=Decimal(1000), phuong_thuc="CHUYEN_KHOAN",
                thong_tin_tai_khoan="0123456789")
        kq = DichVuHoanTien.xac_nhan_da_hoan(
            khoan.ma_hoan_tien, self.nv, "MA_GD_1", so_tien=Decimal(1000), ly_do_dieu_chinh="Khấu trừ phí",
            phuong_thuc="CHUYEN_KHOAN", thong_tin_tai_khoan="0123456789")
        self.assertEqual(kq.trang_thai, TrangThaiHoanTien.DA_HOAN)

    def test_ghi_nhan_that_bai_can_ly_do_va_con_cho_thu_lai(self):
        khoan = self._khoan()
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuHoanTien.ghi_nhan_that_bai(khoan.ma_hoan_tien, self.nv, "")
        kq = DichVuHoanTien.ghi_nhan_that_bai(khoan.ma_hoan_tien, self.nv, "Sai số tài khoản")
        self.assertEqual(kq.trang_thai, TrangThaiHoanTien.THAT_BAI)

    def test_ma_hoa_va_che_tai_khoan_nhan(self):  # NFR bảo mật
        mh = ma_hoa("0123456789")
        self.assertNotIn("0123456789", mh)
        self.assertEqual(giai_ma(mh), "0123456789")
        self.assertTrue(che_bot("0123456789").endswith("6789"))
        self.assertNotIn("012345", che_bot("0123456789"))


# ==========================================================
# UC07 – Danh mục nguyên nhân (BR10, BR13)
# ==========================================================
class KiemThuNguyenNhan(NenHauMai, TestCase):

    def test_moi_loai_co_nguyen_nhan_ap_dung(self):
        for loai in ("HUY_DON", "GIAO_THAT_BAI", "DOI_TRA"):
            self.assertTrue(NguyenNhan.objects.filter(loai_xu_ly=loai, dang_ap_dung=True).exists())

    def test_them_ghi_lich_su_va_chan_trung_ten(self):
        nn = DichVuNguyenNhan.them(self.nv.tai_khoan, "HUY_DON", "Lý do mới")
        self.assertTrue(LichSuNguyenNhan.objects.filter(ma_nguyen_nhan=nn.ma_nguyen_nhan).exists())
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuNguyenNhan.them(self.nv.tai_khoan, "HUY_DON", "lý do mới")

    def test_nguyen_nhan_da_dung_chi_duoc_ngung_khong_duoc_xoa(self):
        DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuNguyenNhan.xoa(self.nv.tai_khoan, NN_HUY)
        DichVuNguyenNhan.ngung_su_dung(self.nv.tai_khoan, NN_HUY)
        yc_cu = YeuCauHuy.objects.get()
        DichVuHuyDon.thu_hoi(yc_cu.ma_yc_huy, self.kh)
        with self.assertRaises(LoiNghiepVuHauMai):  # ngưng rồi thì khách không chọn được nữa
            DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)

    def test_khong_ngung_nguyen_nhan_cuoi_cung_cua_loai(self):
        ds = list(NguyenNhan.objects.filter(loai_xu_ly="GIAO_THAT_BAI", dang_ap_dung=True))
        for nn in ds[:-1]:
            DichVuNguyenNhan.ngung_su_dung(self.nv.tai_khoan, nn.ma_nguyen_nhan)
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuNguyenNhan.ngung_su_dung(self.nv.tai_khoan, ds[-1].ma_nguyen_nhan)


# ==========================================================
# UC08, UC09 – Thống kê, lịch sử
# ==========================================================
class KiemThuThongKeLichSu(NenHauMai, TestCase):

    def test_thong_ke_mac_dinh_va_ty_le_khong_chia_cho_0(self):
        kq = DichVuThongKe.thong_ke()
        self.assertIsNotNone(kq)

    def test_thong_ke_chan_khoang_ngay_sai(self):
        hom_nay = timezone.localdate()
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuThongKe.thong_ke(tu_ngay=hom_nay, den_ngay=hom_nay - timedelta(days=1))
        with self.assertRaises(LoiNghiepVuHauMai):
            DichVuThongKe.thong_ke(tu_ngay=hom_nay, den_ngay=hom_nay + timedelta(days=1))

    def test_lich_su_khach_chi_thay_don_cua_minh(self):
        DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)
        khac = tao_khach_hang("KH_Z", "z@test.vn")
        mine = DichVuLichSu.tra_cuu(khach_hang=self.kh)
        other = DichVuLichSu.tra_cuu(khach_hang=khac)
        self.assertEqual(len(mine.object_list), 1)
        self.assertEqual(len(other.object_list), 0)

    def test_timeline_khach_khac_bi_chan(self):  # E2
        yc = DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)
        khac = tao_khach_hang("KH_W", "w@test.vn")
        with self.assertRaises(LoiQuyenHauMai):
            DichVuLichSu.timeline("HUY_DON", yc.ma_yc_huy, khach_hang=khac)


# ==========================================================
# API – phân quyền và định dạng phản hồi
# ==========================================================
class KiemThuApi(NenHauMai, TestCase):

    def setUp(self):
        super().setUp()
        self.api = APIClient()

    def as_khach(self):
        self.api.force_authenticate(self.kh.tai_khoan)

    def as_nv(self):
        self.api.force_authenticate(self.nv.tai_khoan)

    def test_chua_dang_nhap_bi_chan(self):
        self.assertIn(self.api.post("/api/after-sales/huy/", {}, format="json").status_code, (401, 403))

    def test_khach_gui_huy_roi_nhan_vien_duyet(self):
        self.as_khach()
        r = self.api.post("/api/after-sales/huy/", {"ma_dh": self.don.ma_dh, "ma_nguyen_nhan": NN_HUY}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        ma = r.data["data"]["ma_yc_huy"]
        self.as_nv()
        r = self.api.post(f"/api/after-sales/staff/huy/{ma}/xu-ly/", {"quyet_dinh": "DUYET"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.don.refresh_from_db()
        self.assertEqual(self.don.trang_thai, T.DA_HUY)

    def test_khach_khong_vao_duoc_api_nhan_vien(self):
        self.as_khach()
        self.assertEqual(self.api.get("/api/after-sales/staff/huy/").status_code, 403)

    def test_nhan_vien_khong_gui_yeu_cau_cua_khach(self):
        self.as_nv()
        r = self.api.post("/api/after-sales/huy/", {"ma_dh": self.don.ma_dh, "ma_nguyen_nhan": NN_HUY}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_huy_don_cua_khach_khac_403(self):
        khac = tao_khach_hang("KH_Q", "q@test.vn")
        self.api.force_authenticate(khac.tai_khoan)
        r = self.api.post("/api/after-sales/huy/", {"ma_dh": self.don.ma_dh, "ma_nguyen_nhan": NN_HUY}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_thieu_truong_400(self):
        self.as_khach()
        r = self.api.post("/api/after-sales/huy/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_khach_khong_thay_ghi_chu_noi_bo(self):  # BR12
        self.as_khach()
        r = self.api.post("/api/after-sales/huy/", {"ma_dh": self.don.ma_dh, "ma_nguyen_nhan": NN_HUY}, format="json")
        ma = r.data["data"]["ma_yc_huy"]
        self.as_nv()
        self.api.post(f"/api/after-sales/staff/huy/{ma}/xu-ly/",
                      {"quyet_dinh": "TU_CHOI", "ly_do_tu_choi": "Đã đóng gói", "ghi_chu": "BI_MAT_NOI_BO"}, format="json")
        self.as_khach()
        r = self.api.get(f"/api/after-sales/lich-su/HUY_DON/{ma}/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertNotIn("BI_MAT_NOI_BO", str(r.data))
        self.as_nv()
        r = self.api.get(f"/api/after-sales/lich-su/HUY_DON/{ma}/")
        self.assertIn("BI_MAT_NOI_BO", str(r.data))

    def test_hoan_tien_danh_sach_khong_lo_tai_khoan(self):
        self.da_thanh_toan()
        yc = DichVuHuyDon.gui_yeu_cau(self.don.ma_dh, self.kh, NN_HUY)
        DichVuHuyDon.xu_ly(yc.ma_yc_huy, self.nv, "DUYET")
        khoan = GiaoDichHoanTien.objects.get()
        DichVuHoanTien.xac_nhan_da_hoan(khoan.ma_hoan_tien, self.nv, so_tien=khoan.so_tien_de_xuat, phuong_thuc="CHUYEN_KHOAN",
                                        ma_giao_dich_hoan="API1", thong_tin_tai_khoan="9876543210123")
        self.as_nv()
        r = self.api.get("/api/after-sales/staff/hoan-tien/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertNotIn("9876543210123", str(r.data))

    def test_thong_ke_csv(self):
        self.as_nv()
        r = self.api.get("/api/after-sales/staff/thong-ke/xuat/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r["Content-Type"])

    def test_danh_sach_nguyen_nhan_cho_khach(self):
        self.as_khach()
        r = self.api.get("/api/after-sales/nguyen-nhan/?loai=HUY_DON")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(r.data["data"]) >= 4)
        self.assertEqual(self.api.get("/api/after-sales/nguyen-nhan/?loai=XYZ").status_code, 400)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())  # ảnh test ghi vào thư mục tạm, không làm bẩn dự án
class KiemThuApiDoiTra(NenHauMai, TestCase):
    def setUp(self):
        super().setUp()
        self.da_giao_thanh_cong()
        self.api = APIClient()
        self.api.force_authenticate(self.kh.tai_khoan)

    def test_gui_doi_tra_kem_anh_multipart(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        anh = SimpleUploadedFile("loi.jpg", b"\xff\xd8\xff\xe0fake", content_type="image/jpeg")
        r = self.api.post("/api/after-sales/doi-tra/", {
            "ma_dh": self.don.ma_dh, "hinh_thuc": "TRA", "ma_nguyen_nhan": NN_DOI_LOI, "mo_ta": "Bánh bị hỏng",
            "dong": f'[{{"ma_ctdh": "{self.dong_dau().ma_ctdh}", "so_luong": 1}}]', "anh": anh}, format="multipart")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(AnhMinhChung.objects.count(), 1)

    def test_anh_sai_dinh_dang_400(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        tep = SimpleUploadedFile("loi.gif", b"GIF89a", content_type="image/gif")
        r = self.api.post("/api/after-sales/doi-tra/", {
            "ma_dh": self.don.ma_dh, "hinh_thuc": "TRA", "ma_nguyen_nhan": NN_DOI_LOI,
            "dong": f'[{{"ma_ctdh": "{self.dong_dau().ma_ctdh}", "so_luong": 1}}]', "anh": tep}, format="multipart")
        self.assertEqual(r.status_code, 400)

    def test_danh_sach_dong_du_dieu_kien(self):
        r = self.api.get(f"/api/after-sales/doi-tra/dong/{self.don.ma_dh}/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data["data"]), 2)
        self.assertTrue(all(dong["bien_the_thay_the"] for dong in r.data["data"]))
        self.assertTrue(all("ma_bien_the" in bien_the for dong in r.data["data"]
                            for bien_the in dong["bien_the_thay_the"]))
