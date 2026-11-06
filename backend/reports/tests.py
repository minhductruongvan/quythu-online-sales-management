from datetime import timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone

from customers.models import TaiKhoan, KhachHang, LoaiKhachHang
from orders.models import (
    DonHang,
    ChiTietDonHang,
    TrangThaiDonHang,
    TrangThaiThanhToan,
    TinhThanh,
    PhuongThucThanhToan,
)
from products.models import DanhMucSanPham, SanPham, BienTheSanPham
from reports import services


class Module5ReportsTestCase(TestCase):
    def setUp(self):
        self.now = timezone.now()
        
        # 1. Setup LoaiKhachHang & TaiKhoan
        self.loai_le = LoaiKhachHang.objects.create(ma_loai_kh="LE", ten_loai_kh="Khách lẻ")
        self.loai_si = LoaiKhachHang.objects.create(ma_loai_kh="SI", ten_loai_kh="Khách sỉ")
        
        self.user_manager = TaiKhoan.objects.create(
            ma_tk="TK001",
            email="manager@quythu.vn",
            vai_tro=TaiKhoan.VaiTro.MANAGER,
        )
        self.user_cust = TaiKhoan.objects.create(
            ma_tk="TK002",
            email="cust1@gmail.com",
            vai_tro=TaiKhoan.VaiTro.CUSTOMER,
        )
        self.khach_hang = KhachHang.objects.create(
            ma_kh="KH001",
            tai_khoan=self.user_cust,
            loai_khach_hang=self.loai_le,
            ho_ten="Nguyễn Văn A",
            so_dien_thoai="0901234567",
        )

        # 2. Setup TinhThanh & PTTT
        self.tinh_danang = TinhThanh.objects.create(
            ma_tinh="DN",
            ten_tinh="Đà Nẵng",
            vung_mien=TinhThanh.VungMien.TRUNG,
            phi_van_chuyen=Decimal("20000"),
        )
        self.pttt = PhuongThucThanhToan.objects.create(
            ma_pttt="PT001",
            ten_pttt="Chuyển khoản ngân hàng",
        )

        # 3. Setup Products & Variants
        self.danh_muc = DanhMucSanPham.objects.create(ma_dm="DM01", ten_dm="Bánh dừa nướng")
        self.san_pham = SanPham.objects.create(ma_sp="SP01", danh_muc=self.danh_muc, ten_sp="Bánh dừa nướng Quý Thu")
        
        self.bt1 = BienTheSanPham.objects.create(
            ma_bien_the="BT01",
            san_pham=self.san_pham,
            huong_vi="Truyền thống",
            quy_cach="120g",
            barcode="89300001",
            gia_ban_le=Decimal("15000"),
        )
        self.bt2 = BienTheSanPham.objects.create(
            ma_bien_the="BT02",
            san_pham=self.san_pham,
            huong_vi="Mè đen",
            quy_cach="150g",
            barcode="89300002",
            gia_ban_le=Decimal("20000"),
        )

        # 4. Create sample orders
        # Đơn 1: HOAN_THANH, 100.000đ
        self.dh1 = DonHang.objects.create(
            ma_dh="DH001",
            khach_hang=self.khach_hang,
            loai_khach_hang_ap_dung=self.loai_le,
            ho_ten_nguoi_nhan="Nguyễn Văn A",
            sdt_nguoi_nhan="0901234567",
            dia_chi_giao_hang="123 Hải Phòng, Đà Nẵng",
            tinh_thanh=self.tinh_danang,
            tong_tien_hang=Decimal("80000"),
            phi_van_chuyen=Decimal("20000"),
            tong_thanh_toan=Decimal("100000"),
            phuong_thuc_thanh_toan=self.pttt,
            trang_thai_thanh_toan=TrangThaiThanhToan.DA_THANH_TOAN,
            trang_thai=TrangThaiDonHang.HOAN_THANH,
            ngay_dat=self.now,
            thoi_diem_hoan_thanh=self.now,
        )
        ChiTietDonHang.objects.create(
            ma_ctdh="CT001",
            don_hang=self.dh1,
            bien_the=self.bt1,
            so_luong=4,
            don_gia=Decimal("15000"),
            thanh_tien=Decimal("60000"),
            loai_gia_ap_dung="GIA_LE",
        )
        ChiTietDonHang.objects.create(
            ma_ctdh="CT002",
            don_hang=self.dh1,
            bien_the=self.bt2,
            so_luong=1,
            don_gia=Decimal("20000"),
            thanh_tien=Decimal("20000"),
            loai_gia_ap_dung="GIA_LE",
        )

        # Đơn 2: DANG_CHUAN_BI (đang xử lý), 50.000đ
        self.dh2 = DonHang.objects.create(
            ma_dh="DH002",
            khach_hang=self.khach_hang,
            loai_khach_hang_ap_dung=self.loai_le,
            ho_ten_nguoi_nhan="Nguyễn Văn A",
            sdt_nguoi_nhan="0901234567",
            dia_chi_giao_hang="123 Hải Phòng, Đà Nẵng",
            tinh_thanh=self.tinh_danang,
            tong_tien_hang=Decimal("30000"),
            phi_van_chuyen=Decimal("20000"),
            tong_thanh_toan=Decimal("50000"),
            phuong_thuc_thanh_toan=self.pttt,
            trang_thai_thanh_toan=TrangThaiThanhToan.CHUA_THANH_TOAN,
            trang_thai=TrangThaiDonHang.DANG_CHUAN_BI,
            ngay_dat=self.now,
        )

        # Đơn 3: DA_HUY (không được tính doanh thu hoặc tổng đơn đặt hợp lệ)
        self.dh3 = DonHang.objects.create(
            ma_dh="DH003",
            khach_hang=self.khach_hang,
            loai_khach_hang_ap_dung=self.loai_le,
            ho_ten_nguoi_nhan="Nguyễn Văn A",
            sdt_nguoi_nhan="0901234567",
            dia_chi_giao_hang="123 Hải Phòng, Đà Nẵng",
            tinh_thanh=self.tinh_danang,
            tong_tien_hang=Decimal("30000"),
            phi_van_chuyen=Decimal("20000"),
            tong_thanh_toan=Decimal("50000"),
            phuong_thuc_thanh_toan=self.pttt,
            trang_thai_thanh_toan=TrangThaiThanhToan.CHUA_THANH_TOAN,
            trang_thai=TrangThaiDonHang.DA_HUY,
            ngay_dat=self.now,
        )

    def test_m5_br01_revenue_calculation(self):
        """M5-BR01: Chỉ tính doanh thu đơn HOAN_THANH, loại bỏ đơn hủy và đơn chưa xong"""
        date_range = services.parse_date_range(preset="this_month")
        kpis = services.get_dashboard_kpis(date_range)
        
        # Doanh thu thuần phải bằng đúng tổng tiền của DH001 (100.000đ), không tính DH002 và DH003
        self.assertEqual(kpis["revenue"]["value"], 100000)

    def test_m5_br02_orders_count_and_processing(self):
        """M5-BR02: Tổng đơn đặt loại bỏ DA_HUY, đơn đang xử lý gồm các trạng thái vận hành"""
        date_range = services.parse_date_range(preset="this_month")
        kpis = services.get_dashboard_kpis(date_range)
        
        # Đơn đặt: DH001 + DH002 = 2 đơn (DH003 bị hủy không tính)
        self.assertEqual(kpis["orders"]["value"], 2)
        # Đơn đang xử lý: DH002 (DANG_CHUAN_BI) = 1 đơn
        self.assertEqual(kpis["processing_orders"]["value"], 1)

    def test_m5_br03_top_selling_products(self):
        """M5-BR03: Top sản phẩm bán chạy chỉ tính trên đơn HOAN_THANH"""
        date_range = services.parse_date_range(preset="this_month")
        top_prods = services.get_top_selling_products(date_range, top_n=5, sort_by="sl")
        
        self.assertTrue(len(top_prods) >= 2)
        # BT01 bán 4 cái, BT02 bán 1 cái -> BT01 phải xếp hạng 1
        self.assertEqual(top_prods[0]["code"], "BT01")
        self.assertEqual(top_prods[0]["qty"], 4)
        self.assertEqual(top_prods[1]["code"], "BT02")
        self.assertEqual(top_prods[1]["qty"], 1)

    def test_views_status_codes(self):
        """Kiểm tra view trả về HTTP 200 OK"""
        client = Client()
        resp_dashboard = client.get("/reports/dashboard/")
        self.assertEqual(resp_dashboard.status_code, 200)

        resp_detail = client.get("/reports/chi-tiet/?tab=revenue")
        self.assertEqual(resp_detail.status_code, 200)

        resp_api = client.get("/reports/api/dashboard-data/")
        self.assertEqual(resp_api.status_code, 200)
