from datetime import timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone

from customers.models import KhachHang, LoaiKhachHang, NhanVien, TaiKhoan
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
        self.now = timezone.localtime()
        
        # 1. Setup LoaiKhachHang & TaiKhoan
        self.loai_le = LoaiKhachHang.objects.get(
            ma_loai_kh="LKH001"
        )
        self.loai_si = LoaiKhachHang.objects.get(
            ma_loai_kh="LKH002"
        )
        
        self.user_manager = TaiKhoan.objects.create(
            ma_tk="TK001",
            email="manager@quythu.vn",
            vai_tro=TaiKhoan.VaiTro.MANAGER,
        )
        NhanVien.objects.create(
            ma_nv="NV001",
            tai_khoan=self.user_manager,
            ho_ten="Quản lý kiểm thử",
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
        self.tinh_danang = TinhThanh.objects.get(
            ma_tinh="TT021"
        )
        self.pttt = PhuongThucThanhToan.objects.get(
            ma_pttt="PT001"
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

    def test_empty_period_displays_zero_counts_and_undefined_ratios(self):
        date_range = services.parse_date_range(
            preset="custom", start_date_str="2020-01-01", end_date_str="2020-01-05"
        )
        kpis = services.get_dashboard_kpis(date_range)
        timeline = services.get_revenue_timeline(date_range)

        self.assertEqual(kpis["revenue"]["value"], 0)
        self.assertEqual(kpis["orders"]["value"], 0)
        self.assertEqual(kpis["avg_order_value"]["formatted"], "—")
        self.assertEqual(kpis["conversion_rate"]["formatted"], "—")
        self.assertEqual(kpis["revenue"]["pct_change"], None)
        self.assertFalse(any(timeline["revenue_millions"]))
        self.assertFalse(any(timeline["orders_count"]))

    def test_views_status_codes(self):
        """Kiểm tra view trả về HTTP 200 OK"""
        client = Client()
        client.force_login(self.user_manager)
        resp_dashboard = client.get("/reports/dashboard/")
        self.assertEqual(resp_dashboard.status_code, 200, resp_dashboard.get("Location"))
        self.assertEqual(resp_dashboard.content.count(b'class="report-kpi"'), 4)
        self.assertContains(resp_dashboard, "Bốn chỉ số kinh doanh quan trọng")

        resp_detail = client.get("/reports/chi-tiet/?tab=revenue")
        self.assertEqual(resp_detail.status_code, 200)
        self.assertContains(resp_detail, "Cơ cấu doanh thu")

        resp_api = client.get("/reports/api/dashboard-data/")
        self.assertEqual(resp_api.status_code, 200)

    def test_revenue_composition_includes_both_customer_types_even_when_filtered(self):
        DonHang.objects.create(
            ma_dh="DH004",
            khach_hang=self.khach_hang,
            loai_khach_hang_ap_dung=self.loai_si,
            ho_ten_nguoi_nhan="Nguyễn Văn A",
            sdt_nguoi_nhan="0901234567",
            dia_chi_giao_hang="123 Hải Phòng, Đà Nẵng",
            tinh_thanh=self.tinh_danang,
            tong_tien_hang=Decimal("200000"),
            phi_van_chuyen=Decimal("0"),
            tong_thanh_toan=Decimal("200000"),
            phuong_thuc_thanh_toan=self.pttt,
            trang_thai_thanh_toan=TrangThaiThanhToan.DA_THANH_TOAN,
            trang_thai=TrangThaiDonHang.HOAN_THANH,
            ngay_dat=self.now,
            thoi_diem_hoan_thanh=self.now,
        )
        client = Client()
        client.force_login(self.user_manager)

        dashboard = client.get(
            "/reports/dashboard/",
            {"customer_type": self.loai_le.ma_loai_kh},
        )
        detail = client.get(
            "/reports/chi-tiet/",
            {"tab": "revenue", "customer_type": self.loai_le.ma_loai_kh},
        )

        for response in (dashboard, detail):
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.context["customer_ratio"]["values"],
                [200000, 100000],
            )
            self.assertEqual(
                response.context["customer_ratio"]["percentages"],
                [66.7, 33.3],
            )

    def test_product_and_revenue_filters_apply_to_reports(self):
        client = Client()
        client.force_login(self.user_manager)

        dashboard = client.get(
            "/reports/dashboard/",
            {"product": "SP01", "amount_min": "50000", "amount_max": "100000"},
        )
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.context["kpis"]["revenue"]["value"], 80000)
        self.assertEqual(dashboard.context["kpis"]["orders"]["value"], 1)

        detail = client.get(
            "/reports/chi-tiet/",
            {
                "tab": "revenue",
                "product": "SP01",
                "amount_min": "50000",
                "q": "DH001",
            },
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.context["order_details"]["total_records"], 1)
        self.assertEqual(detail.context["order_details"]["items"][0]["line_items"][0]["product_name"], self.san_pham.ten_sp)
        self.assertContains(detail, "q=DH001")
        self.assertNotContains(detail, "category=None")
        self.assertNotContains(detail, "product=None")
        self.assertContains(detail, 'action="/reports/chi-tiet/"')
        self.assertContains(detail, 'name="amount_min" min="0" step="1"')
        self.assertNotContains(detail, "Số dòng / trang")
        self.assertContains(detail, "Tổng cộng")
        self.assertContains(detail, "Sản phẩm bán chạy")
        self.assertContains(detail, "Áp dụng bộ lọc")
        self.assertNotContains(detail, "<details class=\"report-extra-filters\">")

        for tab in ("products", "recent", "area"):
            no_filter_response = client.get("/reports/chi-tiet/", {"tab": tab})
            self.assertEqual(no_filter_response.status_code, 200, tab)
            response = client.get(
                "/reports/chi-tiet/",
                {"tab": tab, "product": "SP01", "pttt": "PT001"},
            )
            self.assertEqual(response.status_code, 200, tab)

        self.san_pham.trang_thai = "INACTIVE"
        self.san_pham.save(update_fields=["trang_thai"])
        historical_product_report = client.get(
            "/reports/chi-tiet/",
            {"tab": "revenue", "product": self.san_pham.ma_sp},
        )
        self.assertEqual(historical_product_report.status_code, 200)
        self.assertEqual(historical_product_report.context["active_tab"], "revenue")
        self.assertContains(historical_product_report, 'name="product"')

        export = client.get(
            "/reports/export/csv/",
            {"tab": "products", "product": "SP01", "pttt": "PT001"},
        )
        self.assertEqual(export.status_code, 200)
        self.assertIn("text/csv", export["Content-Type"])

        no_match = client.get(
            "/reports/chi-tiet/",
            {"tab": "revenue", "product": "SP01", "amount_min": "100001"},
        )
        self.assertEqual(no_match.status_code, 200)
        self.assertEqual(no_match.context["order_details"]["total_records"], 0)

        invalid_range = client.get(
            "/reports/dashboard/",
            {"amount_min": "100000", "amount_max": "50000"},
        )
        self.assertEqual(invalid_range.status_code, 400)
        self.assertContains(invalid_range, "Không thể áp dụng bộ lọc", status_code=400)

        invalid_product = client.get(
            "/reports/chi-tiet/",
            {"product": "DOES_NOT_EXIST"},
        )
        self.assertEqual(invalid_product.status_code, 400)
        self.assertContains(invalid_product, "Quay lại báo cáo chi tiết", status_code=400)

        api_error = client.get(
            "/reports/api/detail-data/",
            {"product": "DOES_NOT_EXIST"},
        )
        self.assertEqual(api_error.status_code, 400)
        self.assertEqual(api_error.json()["status"], "error")

        invalid_dates = client.get(
            "/reports/chi-tiet/",
            {"preset": "custom", "start_date": "2026-11-06", "end_date": "2026-11-01"},
        )
        self.assertEqual(invalid_dates.status_code, 400)
        self.assertContains(invalid_dates, "Ngày bắt đầu không được sau ngày kết thúc.", status_code=400)
