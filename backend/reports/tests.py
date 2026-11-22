import csv
import io
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
from products.models import DanhMucSanPham, DonViTinh, SanPham, BienTheSanPham
from reports.models import NhatKyXuatBaoCao
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
        # Đơn 1: HOAN_THANH, tiền hàng 80.000đ + phí ship 20.000đ = 100.000đ
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

        # Doanh thu = tiền hàng của DH001 (80.000đ, không gồm phí ship), không tính DH002 và DH003
        self.assertEqual(kpis["revenue"]["value"], 80000)

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
        self.assertEqual(resp_dashboard.content.count(b'class="report-kpi"'), 8)
        self.assertContains(resp_dashboard, "Bốn chỉ số kinh doanh quan trọng")

        resp_detail = client.get("/reports/chi-tiet/?tab=revenue")
        self.assertEqual(resp_detail.status_code, 200)
        self.assertContains(resp_detail, "Chi tiết đơn hàng")

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
                [200000, 80000],
            )
            self.assertEqual(
                response.context["customer_ratio"]["percentages"],
                [71.4, 28.6],
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
        self.assertEqual(detail.context["order_details"]["items"][0]["line_items"][0]["product_name"],
                         self.san_pham.ten_sp)
        self.assertContains(detail, "q=DH001")
        self.assertNotContains(detail, "category=None")
        self.assertNotContains(detail, "product=None")
        self.assertContains(detail, 'action="/reports/chi-tiet/"')
        self.assertContains(detail, 'name="amount_min" min="0" step="1"')
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
        export_log = NhatKyXuatBaoCao.objects.get()
        self.assertEqual(export_log.nhan_vien_id, "NV001")
        self.assertEqual(export_log.loai_bao_cao, "Sản phẩm bán chạy")
        self.assertEqual(export_log.dinh_dang_file, NhatKyXuatBaoCao.DinhDang.CSV)
        self.assertIn('"product": "SP01"', export_log.bo_loc_ap_dung)

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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _make_order(
            self,
            ma_dh,
            *,
            khach_hang=None,
            loai=None,
            total="100000",
            ship="0",
            trang_thai=TrangThaiDonHang.HOAN_THANH,
            sdt="0901234567",
            ten_nguoi_nhan="Nguyễn Văn A",
    ):
        total = Decimal(total)
        ship = Decimal(ship)
        completed = trang_thai == TrangThaiDonHang.HOAN_THANH
        return DonHang.objects.create(
            ma_dh=ma_dh,
            khach_hang=khach_hang or self.khach_hang,
            loai_khach_hang_ap_dung=loai or self.loai_le,
            ho_ten_nguoi_nhan=ten_nguoi_nhan,
            sdt_nguoi_nhan=sdt,
            dia_chi_giao_hang="123 Hải Phòng, Đà Nẵng",
            tinh_thanh=self.tinh_danang,
            tong_tien_hang=total - ship,
            phi_van_chuyen=ship,
            tong_thanh_toan=total,
            phuong_thuc_thanh_toan=self.pttt,
            trang_thai_thanh_toan=(
                TrangThaiThanhToan.DA_THANH_TOAN
                if completed
                else TrangThaiThanhToan.CHUA_THANH_TOAN
            ),
            trang_thai=trang_thai,
            ngay_dat=self.now,
            thoi_diem_hoan_thanh=self.now if completed else None,
        )

    def _add_line(self, ma_ctdh, don_hang, bien_the, qty, price):
        price = Decimal(price)
        return ChiTietDonHang.objects.create(
            ma_ctdh=ma_ctdh,
            don_hang=don_hang,
            bien_the=bien_the,
            so_luong=qty,
            don_gia=price,
            thanh_tien=price * qty,
            loai_gia_ap_dung="GIA_LE",
        )

    def _custom_range(self, start, end):
        return services.parse_date_range(
            preset="custom", start_date_str=start, end_date_str=end
        )

    def _csv_rows(self, response):
        content = response.content.decode("utf-8-sig")
        return list(csv.reader(io.StringIO(content)))

    # ------------------------------------------------------------------
    # Độ chi tiết biểu đồ: hôm nay -> giờ; năm nay -> tháng; các kỳ khác -> ngày
    # ------------------------------------------------------------------
    def test_group_by_follows_report_period(self):
        resolve = services.resolve_group_by
        self.assertEqual(resolve(services.parse_date_range("today")), "hour")
        self.assertEqual(resolve(services.parse_date_range("7days")), "day")
        self.assertEqual(resolve(services.parse_date_range("this_month")), "day")
        self.assertEqual(resolve(services.parse_date_range("last_month")), "day")
        self.assertEqual(resolve(services.parse_date_range("this_quarter")), "day")
        self.assertEqual(resolve(services.parse_date_range("this_year")), "month")

        self.assertEqual(resolve(self._custom_range("2025-01-01", "2025-01-05")), "day")
        self.assertEqual(resolve(self._custom_range("2025-01-01", "2025-01-31")), "day")
        self.assertEqual(resolve(self._custom_range("2025-01-01", "2025-03-31")), "day")
        self.assertEqual(resolve(self._custom_range("2024-01-01", "2024-12-31")), "day")
        # Có thể chỉ định rõ độ chi tiết
        self.assertEqual(resolve(services.parse_date_range("this_year"), "quarter"), "quarter")

    def test_today_timeline_always_shows_all_24_hours(self):
        timeline = services.get_revenue_timeline(services.parse_date_range("today"))
        self.assertEqual(timeline["group_by"], "hour")
        self.assertEqual(timeline["labels"], [f"{h}h" for h in range(24)])
        self.assertEqual(len(timeline["revenue_exact"]), 24)
        self.assertEqual(len(timeline["orders_count"]), 24)

    def test_timeline_fills_every_period_with_proper_labels(self):
        day = services.get_revenue_timeline(
            self._custom_range("2025-01-01", "2025-01-03"), group_by="day"
        )
        self.assertEqual(day["labels"], ["01/01", "02/01", "03/01"])

        # Tuần ISO bắt đầu Thứ Hai: 30/12/2024 thuộc T01/2025, không bao giờ ra T00
        week = services.get_revenue_timeline(
            self._custom_range("2025-01-01", "2025-01-31"), group_by="week"
        )
        self.assertEqual(
            week["labels"],
            ["T01/2025", "T02/2025", "T03/2025", "T04/2025", "T05/2025"],
        )
        self.assertEqual(week["revenue_millions"], [0.0] * 5)
        self.assertEqual(week["orders_count"], [0] * 5)

        # Nhãn tháng: kỳ vắt qua 2 năm thì kèm năm, cùng năm chỉ ghi "Tháng N"
        from datetime import date

        self.assertEqual(
            [l for _, l in services._iter_periods(date(2024, 11, 15), date(2025, 1, 10), "month")],
            ["Tháng 11/2024", "Tháng 12/2024", "Tháng 1/2025"],
        )
        self.assertEqual(
            [l for _, l in services._iter_periods(date(2025, 1, 5), date(2025, 3, 20), "month")],
            ["Tháng 1", "Tháng 2", "Tháng 3"],
        )
        # Tháng không có dữ liệu vẫn hiện đủ (giá trị 0)
        empty_month = services.get_revenue_timeline(
            self._custom_range("2025-01-05", "2025-03-20"), group_by="month"
        )
        self.assertEqual(empty_month["labels"], ["Tháng 1", "Tháng 2", "Tháng 3"])
        self.assertEqual(empty_month["revenue_exact"], [0, 0, 0])
        self.assertEqual(empty_month["orders_count"], [0, 0, 0])

        quarter = services.get_revenue_timeline(
            self._custom_range("2025-02-10", "2025-08-20"), group_by="quarter"
        )
        self.assertEqual(quarter["labels"], ["Q1/2025", "Q2/2025", "Q3/2025"])
        self.assertEqual(quarter["group_by"], "quarter")

    def test_this_year_timeline_always_shows_all_12_months(self):
        today = timezone.localdate()
        timeline = services.get_revenue_timeline(services.parse_date_range("this_year"))
        self.assertEqual(timeline["group_by"], "month")
        self.assertEqual(timeline["labels"], [f"Tháng {m}" for m in range(1, 13)])
        expected_revenue = [0] * 12
        expected_revenue[today.month - 1] = 80000
        expected_orders = [0] * 12
        expected_orders[today.month - 1] = 2
        # Chỉ tháng hiện tại có dữ liệu; các tháng khác vẫn hiện với giá trị 0
        self.assertEqual(timeline["revenue_exact"], expected_revenue)
        self.assertEqual(timeline["orders_count"], expected_orders)

        # Kỳ tuỳ chọn thì chỉ chạy đến ngày kết thúc
        custom = services.get_revenue_timeline(
            self._custom_range(f"{today.year}-01-01", today.isoformat()),
            group_by="month",
        )
        self.assertEqual(
            custom["labels"], [f"Tháng {m}" for m in range(1, today.month + 1)]
        )

    def test_timeline_totals_are_the_same_for_every_granularity(self):
        date_range = services.parse_date_range("this_month")
        for group_by in ("day", "week", "month", "quarter"):
            timeline = services.get_revenue_timeline(date_range, group_by=group_by)
            self.assertEqual(sum(timeline["revenue_exact"]), 80000, group_by)
            self.assertEqual(sum(timeline["orders_count"]), 2, group_by)
            self.assertEqual(len(timeline["labels"]), len(timeline["revenue_exact"]))

    def test_dashboard_and_detail_pick_granularity_automatically(self):
        client = Client()
        client.force_login(self.user_manager)

        dashboard = client.get("/reports/dashboard/")
        self.assertEqual(dashboard.context["timeline"]["group_by"], "day")
        # Tham số group_by trên URL không được ghi đè quy tắc theo kỳ
        forced = client.get(
            "/reports/dashboard/", {"preset": "this_year", "group_by": "day"}
        )
        self.assertEqual(forced.context["timeline"]["group_by"], "month")

        detail = client.get("/reports/chi-tiet/", {"preset": "7days"})
        self.assertEqual(detail.context["rev_timeline"]["group_by"], "day")
        year = client.get("/reports/chi-tiet/", {"preset": "this_year"})
        self.assertEqual(year.context["rev_timeline"]["group_by"], "month")

    # ------------------------------------------------------------------
    # Dashboard API khớp với trang
    # ------------------------------------------------------------------
    def test_api_dashboard_top_products_match_page(self):
        # BT02 thêm 1 sản phẩm giá cao: doanh thu cao hơn BT01 nhưng số lượng thấp hơn
        dh = self._make_order("DH005", total="100000")
        self._add_line("CT005", dh, self.bt2, 1, "100000")
        client = Client()
        client.force_login(self.user_manager)

        page = client.get("/reports/dashboard/")
        api = client.get("/reports/api/dashboard-data/")
        page_codes = [p["code"] for p in page.context["top_products"]]
        api_codes = [p["code"] for p in api.json()["top_products"]]
        self.assertEqual(api_codes, page_codes)
        self.assertEqual(api_codes[0], "BT01")  # xếp theo số lượng, không theo doanh thu

    # ------------------------------------------------------------------
    # Ô tìm kiếm áp dụng đồng đều
    # ------------------------------------------------------------------
    def test_search_matches_same_orders_everywhere(self):
        date_range = services.parse_date_range("this_month")
        # DH004: cùng khách hàng nhưng SĐT người nhận khác
        dh4 = self._make_order("DH004", total="200000", loai=self.loai_si, sdt="0999999999")
        self._add_line("CT004", dh4, self.bt2, 2, "100000")

        # SĐT của khách hàng (không phải SĐT người nhận) phải khớp ở mọi nơi
        for kw, expected_orders in (("0901234567", 2), ("0999999999", 1), ("KH001", 2), ("DH004", 1)):
            details = services.get_order_details(date_range, search_kw=kw)
            ratio = services.get_customer_type_ratio(date_range, search_kw=kw)
            area = services.get_revenue_by_area(date_range, search_kw=kw)
            self.assertEqual(details["total_records"], expected_orders, kw)
            self.assertEqual(sum(a["order_count"] for a in area), expected_orders, kw)
            self.assertEqual(ratio["total"], int(sum(
                DonHang.objects.filter(
                    trang_thai=TrangThaiDonHang.HOAN_THANH,
                    ma_dh__in=[i["order_code"] for i in details["items"]],
                ).values_list("tong_tien_hang", flat=True)
            )), kw)

        # Các tab sản phẩm bán chạy / bán gần đây cũng phải theo q
        top = services.get_top_selling_products(date_range, search_kw="DH004")
        self.assertEqual([p["code"] for p in top], ["BT02"])
        self.assertEqual(top[0]["qty"], 2)
        recent = services.get_recent_products(date_range=date_range, search_kw="DH001")
        self.assertTrue(recent)
        self.assertEqual({r["order_code"] for r in recent}, {"DH001"})

    # ------------------------------------------------------------------
    # Nhận diện khách sỉ chỉ theo mã LKH002
    # ------------------------------------------------------------------
    def test_wholesale_is_detected_by_code_not_by_name(self):
        # "Khách Basic Visa" chứa chuỗi "si" nhưng không phải khách sỉ
        LoaiKhachHang.objects.filter(ma_loai_kh="LKH001").update(
            ten_loai_kh="Khách Basic Visa"
        )
        date_range = services.parse_date_range("this_month")
        ratio = services.get_customer_type_ratio(date_range)
        self.assertEqual(ratio["values"], [0, 80000])

        details = services.get_order_details(date_range)
        self.assertEqual(details["items"][0]["customer_type"], "Khách lẻ")
        self.assertFalse(details["items"][0]["is_si"])

        dh4 = self._make_order("DH004", total="200000", loai=self.loai_si)
        self._add_line("CT004", dh4, self.bt1, 1, "200000")
        ratio = services.get_customer_type_ratio(date_range)
        self.assertEqual(ratio["values"], [200000, 80000])
        recent = services.get_recent_products(date_range=date_range, search_kw="DH004")
        self.assertEqual(recent[0]["customer_type"], "Sỉ")

    # ------------------------------------------------------------------
    # Các tab: sản phẩm bán chạy / bán gần đây / khu vực
    # ------------------------------------------------------------------
    def test_top_products_expose_order_count_and_average_price(self):
        date_range = services.parse_date_range("this_month")
        top = services.get_top_selling_products(date_range, top_n=5)
        self.assertEqual(top[0]["code"], "BT01")
        self.assertEqual(top[0]["order_count"], 1)
        self.assertEqual(top[0]["price_raw"], 15000)  # Giá bán TB = 60.000 / 4
        self.assertEqual(top[0]["revenue_raw"], 60000)  # Tiền hàng, không gồm phí VC

    def test_recent_products_show_order_status_and_skip_cancelled(self):
        self._add_line("CT003", self.dh2, self.bt1, 2, "15000")  # đang chuẩn bị
        self._add_line("CT004", self.dh3, self.bt1, 1, "15000")  # đã hủy
        date_range = services.parse_date_range("this_month")
        rows = services.get_recent_products(limit=None, date_range=date_range)

        self.assertEqual({r["order_code"] for r in rows}, {"DH001", "DH002"})
        by_order = {r["order_code"]: r for r in rows}
        self.assertEqual(
            by_order["DH001"]["order_status_key"], TrangThaiDonHang.HOAN_THANH
        )
        self.assertEqual(
            by_order["DH002"]["order_status_key"], TrangThaiDonHang.DANG_CHUAN_BI
        )
        self.assertTrue(all(r["order_status"] for r in rows))
        # Cột tồn kho đã bỏ vì không có nguồn dữ liệu thật
        self.assertTrue(all("stock_status" not in r for r in rows))

    def test_area_report_counts_orders_and_customers(self):
        date_range = services.parse_date_range("this_month")
        area = services.get_revenue_by_area(date_range)
        self.assertEqual(len(area), 1)
        self.assertEqual(area[0]["province"], self.tinh_danang.ten_tinh)
        self.assertEqual(area[0]["order_count"], 1)
        self.assertEqual(area[0]["customer_count"], 1)
        # Doanh thu khu vực là tiền hàng (không gồm phí vận chuyển), khớp KPI doanh thu
        kpis = services.get_dashboard_kpis(date_range)
        self.assertEqual(area[0]["revenue"], kpis["revenue"]["value"])

        # Khi lọc theo sản phẩm chỉ tính tiền hàng của dòng khớp
        by_product = services.get_revenue_by_area(date_range, product_id="SP01")
        self.assertEqual(by_product[0]["revenue"], 80000)
        self.assertEqual(
            services.revenue_basis(product_id="SP01"), "tien_hang"
        )
        self.assertEqual(services.revenue_basis(), "tien_hang")

    # ------------------------------------------------------------------
    # Footer bảng chi tiết doanh thu
    # ------------------------------------------------------------------
    def test_order_details_footer_matches_rows(self):
        # DH004: tiền hàng 180.000 + ship 20.000 = tổng thanh toán 200.000
        self._make_order("DH004", total="200000", ship="20000")
        date_range = services.parse_date_range("this_month")
        details = services.get_order_details(date_range)
        items = details["items"]
        summary = details["summary"]

        self.assertEqual(len(items), 2)
        # "Tổng TT" ở footer phải bằng tổng cột Tổng TT của các dòng
        self.assertEqual(sum(i["total_payment_raw"] for i in items), 300000)
        self.assertEqual(summary["sum_total"], "300.000đ")
        self.assertEqual(sum(i["subtotal_raw"] for i in items), 260000)
        self.assertEqual(summary["sum_subtotal"], "260.000đ")
        self.assertEqual(summary["sum_shipping"], "40.000đ")
        # Doanh thu thuần = tiền hàng, không gồm phí vận chuyển
        self.assertEqual(summary["sum_net_revenue"], "260.000đ")

    def test_amount_filter_uses_goods_amount(self):
        # DH001: tiền hàng 80.000, tổng thanh toán 100.000 (gồm ship 20.000)
        client = Client()
        client.force_login(self.user_manager)
        below = client.get("/reports/dashboard/", {"amount_min": "90000"})
        self.assertEqual(below.status_code, 200)
        self.assertEqual(below.context["kpis"]["revenue"]["value"], 0)
        inside = client.get(
            "/reports/dashboard/", {"amount_min": "80000", "amount_max": "80000"}
        )
        self.assertEqual(inside.context["kpis"]["revenue"]["value"], 80000)

    # ------------------------------------------------------------------
    # Xuất CSV
    # ------------------------------------------------------------------
    def test_csv_export_revenue_respects_search_and_sort(self):
        self._make_order("DH004", total="200000")
        client = Client()
        client.force_login(self.user_manager)

        everything = self._csv_rows(
            client.get("/reports/export/csv/", {"tab": "revenue", "order_sort": "order_code", "order_sort_dir": "asc"})
        )
        self.assertEqual([r[0] for r in everything[1:]], ["DH001", "DH004"])
        descending = self._csv_rows(
            client.get("/reports/export/csv/", {"tab": "revenue", "order_sort": "order_code", "order_sort_dir": "desc"})
        )
        self.assertEqual([r[0] for r in descending[1:]], ["DH004", "DH001"])

        filtered_response = client.get(
            "/reports/export/csv/", {"tab": "revenue", "q": "DH004"}
        )
        self.assertTrue(filtered_response.content.startswith("\ufeff".encode("utf-8")))
        filtered = self._csv_rows(filtered_response)
        self.assertEqual([r[0] for r in filtered[1:]], ["DH004"])

        last_log = NhatKyXuatBaoCao.objects.order_by("-ma_nhat_ky_xuat").first()
        self.assertIn('"q": "DH004"', last_log.bo_loc_ap_dung)

    def test_csv_export_other_tabs_respect_search(self):
        client = Client()
        client.force_login(self.user_manager)
        for tab, header_len in (("products", 11), ("recent", 9), ("area", 7)):
            hit = self._csv_rows(client.get("/reports/export/csv/", {"tab": tab, "q": "DH001"}))
            miss = self._csv_rows(client.get("/reports/export/csv/", {"tab": tab, "q": "KHONG_TON_TAI"}))
            self.assertEqual(len(hit[0]), header_len, tab)
            self.assertGreater(len(hit), 1, tab)
            self.assertEqual(len(miss), 1, tab)  # chỉ còn dòng tiêu đề

    def test_csv_export_neutralizes_spreadsheet_formulas(self):
        tai_khoan = TaiKhoan.objects.create(
            ma_tk="TK003",
            email="evil@gmail.com",
            vai_tro=TaiKhoan.VaiTro.CUSTOMER,
        )
        evil = KhachHang.objects.create(
            ma_kh="KH002",
            tai_khoan=tai_khoan,
            loai_khach_hang=self.loai_le,
            ho_ten="=HYPERLINK(\"http://evil.test\",\"x\")",
            so_dien_thoai="0911111111",
        )
        self._make_order("DH004", khach_hang=evil, total="200000")
        client = Client()
        client.force_login(self.user_manager)

        rows = self._csv_rows(
            client.get("/reports/export/csv/", {"tab": "revenue", "q": "DH004"})
        )
        self.assertEqual(rows[1][2], "'=HYPERLINK(\"http://evil.test\",\"x\")")
        # Số liệu thuần vẫn giữ nguyên, không bị thêm dấu '
        self.assertEqual(rows[1][8], "200000")

    def test_completed_database_support_tables_are_available(self):
        self.assertEqual(
            set(DonViTinh.objects.values_list("ky_hieu", flat=True)),
            {"goi", "hop", "thung"},
        )
        self.assertEqual(
            NhatKyXuatBaoCao._meta.db_table,
            "NHATKY_XUAT_BAOCAO",
        )