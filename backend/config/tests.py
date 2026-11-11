from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from customers.models import (
    KhachHang,
    LichSuKhachHang,
    LoaiKhachHang,
    NhanVien,
    TaiKhoan,
)
from products.models import (
    BienTheSanPham,
    DanhMucSanPham,
    HinhAnhSanPham,
    SanPham,
)


class M1CustomerManagementTests(TestCase):
    def setUp(self):
        self.customer_type = LoaiKhachHang.objects.get(ma_loai_kh="LKH001")
        self.customer_account = self.create_account(
            "customer@m1.test",
            TaiKhoan.VaiTro.CUSTOMER,
            "TST001",
        )
        self.customer = KhachHang.objects.create(
            ma_kh="KH0001",
            tai_khoan=self.customer_account,
            loai_khach_hang=self.customer_type,
            ho_ten="Khách hàng M1",
            email=self.customer_account.email,
            so_dien_thoai="0901111111",
        )
        self.employee = self.create_staff(
            "employee@m1.test",
            TaiKhoan.VaiTro.EMPLOYEE,
            "TST002",
            "NV0001",
        )
        self.manager = self.create_staff(
            "manager@m1.test",
            TaiKhoan.VaiTro.MANAGER,
            "TST003",
            "NV0002",
        )

    def create_account(self, email, role, account_code):
        account = TaiKhoan.objects.create(
            email=email,
            ma_tk=account_code,
            vai_tro=role,
            trang_thai=TaiKhoan.TrangThai.ACTIVE,
            is_active=True,
        )
        account.set_password("TestPassword123")
        account.save()
        return account

    def create_staff(self, email, role, account_code, employee_code):
        account = self.create_account(email, role, account_code)
        NhanVien.objects.create(
            ma_nv=employee_code,
            tai_khoan=account,
            ho_ten=email.split("@")[0],
        )
        return account

    def test_staff_can_create_and_update_persisted_customer_profile(self):
        self.client.force_login(self.employee)
        response = self.client.post(
            reverse("employee-customer-add"),
            {
                "ho_ten": "Nguyễn An",
                "email": "an@example.com",
                "so_dien_thoai": "0902222222",
                "loai_khach_hang": "Khách sỉ",
            },
        )
        customer = KhachHang.objects.get(email="an@example.com")
        self.assertRedirects(
            response,
            reverse(
                "employee-customer-detail",
                kwargs={"ma_kh": customer.ma_kh},
            ),
        )
        self.assertEqual(
            customer.lich_su_thay_doi.first().loai_thay_doi,
            LichSuKhachHang.LoaiThayDoi.PROFILE_CREATE,
        )

        response = self.client.post(
            reverse(
                "employee-customer-detail",
                kwargs={"ma_kh": customer.ma_kh},
            ),
            {
                "action": "update",
                "ho_ten": "Nguyễn An mới",
                "email": "an@example.com",
                "so_dien_thoai": "0902222222",
                "loai_khach_hang": "Khách sỉ",
            },
        )
        customer.refresh_from_db()
        self.assertRedirects(
            response,
            reverse(
                "employee-customer-detail",
                kwargs={"ma_kh": customer.ma_kh},
            ),
        )
        self.assertEqual(customer.ho_ten, "Nguyễn An mới")
        self.assertTrue(
            customer.lich_su_thay_doi.filter(
                loai_thay_doi=LichSuKhachHang.LoaiThayDoi.PROFILE_UPDATE
            ).exists()
        )

    def test_status_change_requires_reason_and_is_audited(self):
        self.client.force_login(self.employee)
        url = reverse(
            "employee-customer-detail",
            kwargs={"ma_kh": self.customer.ma_kh},
        )
        self.client.post(
            url,
            {"action": "status", "trang_thai": "INACTIVE"},
        )
        self.customer.refresh_from_db()
        self.assertEqual(
            self.customer.trang_thai,
            KhachHang.TrangThai.ACTIVE,
        )

        self.client.post(
            url,
            {
                "action": "status",
                "trang_thai": "INACTIVE",
                "ly_do": "Yêu cầu ngừng giao dịch",
            },
        )
        self.customer.refresh_from_db()
        self.assertEqual(
            self.customer.trang_thai,
            KhachHang.TrangThai.INACTIVE,
        )
        event = self.customer.lich_su_thay_doi.get(
            loai_thay_doi=LichSuKhachHang.LoaiThayDoi.STATUS,
        )
        self.assertIn("Yêu cầu ngừng giao dịch", event.noi_dung_moi)

    def test_only_manager_can_lock_customer_account(self):
        detail_url = reverse(
            "employee-customer-detail",
            kwargs={"ma_kh": self.customer.ma_kh},
        )
        self.client.force_login(self.employee)
        denied = self.client.post(
            detail_url,
            {"action": "account_status", "hanh_dong": "LOCK"},
        )
        self.assertEqual(denied.status_code, 403)

        api_url = reverse(
            "customer-account-status",
            kwargs={"ma_kh": self.customer.ma_kh},
        )
        denied_api = self.client.patch(
            api_url,
            {"hanh_dong": "LOCK"},
            content_type="application/json",
        )
        self.assertEqual(denied_api.status_code, 403)

        self.client.force_login(self.manager)
        allowed = self.client.patch(
            api_url,
            {"hanh_dong": "LOCK"},
            content_type="application/json",
        )
        self.assertEqual(allowed.status_code, 200)
        self.customer_account.refresh_from_db()
        self.assertEqual(
            self.customer_account.trang_thai,
            TaiKhoan.TrangThai.LOCKED,
        )
        self.client.logout()
        login = self.client.post(
            reverse("dang-nhap"),
            {
                "email": self.customer_account.email,
                "mat_khau": "TestPassword123",
            },
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 403)

    def test_internal_note_is_visible_to_staff_only(self):
        detail_url = reverse(
            "employee-customer-detail",
            kwargs={"ma_kh": self.customer.ma_kh},
        )
        self.client.force_login(self.employee)
        response = self.client.post(
            detail_url,
            {"action": "note", "noi_dung": "Gọi lại khách hàng."},
        )
        self.assertRedirects(response, detail_url)
        self.assertEqual(
            self.customer.ghi_chu_noi_bo.get().noi_dung,
            "Gọi lại khách hàng.",
        )

        self.client.force_login(self.customer_account)
        self.assertEqual(self.client.get(detail_url).status_code, 403)
        profile_response = self.client.get(
            reverse("customer-profile-page")
        )
        self.assertEqual(profile_response.status_code, 200)
        self.assertNotContains(profile_response, "Gọi lại khách hàng.")

    def test_csv_import_requires_validation_and_confirmation(self):
        self.client.force_login(self.employee)
        upload = SimpleUploadedFile(
            "customers.csv",
            (
                "ho_ten,email,so_dien_thoai,loai_khach_hang,trang_thai\n"
                "Khách mới,new@example.com,0903333333,Khách lẻ,ACTIVE\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )
        response = self.client.post(
            reverse("employee-customer-import"),
            {"file": upload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["preview_ready"])
        self.assertEqual(response.context["imported_count"], 0)
        self.assertContains(response, "Chưa có dữ liệu nào được nhập")
        self.assertContains(response, "Xác nhận nhập 1 hồ sơ")
        self.assertFalse(KhachHang.objects.filter(email="new@example.com").exists())

        response = self.client.post(
            reverse("employee-customer-import"),
            {
                "action": "confirm",
                "stage_id": response.context["preview_stage_id"],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["imported_count"], 1)
        self.assertTrue(
            KhachHang.objects.filter(email="new@example.com").exists()
        )
        imported_customer = KhachHang.objects.get(email="new@example.com")
        self.assertIsNone(imported_customer.tai_khoan_id)

        export = self.client.get(
            reverse("employee-customer-export"),
            {"q": "new@example.com"},
        )
        self.assertEqual(export.status_code, 200)
        self.assertIn("new@example.com", export.content.decode("utf-8-sig"))
        self.assertNotIn(
            "customer@m1.test",
            export.content.decode("utf-8-sig"),
        )

    def test_csv_import_rejects_all_rows_when_any_row_is_invalid(self):
        self.client.force_login(self.employee)
        upload = SimpleUploadedFile(
            "customers.csv",
            (
                "ho_ten,email,so_dien_thoai,loai_khach_hang,trang_thai\n"
                "Khách mới,new@example.com,0903333333,Khách lẻ,ACTIVE\n"
                "Khách trùng,customer@m1.test,0904444444,Khách sỉ,ACTIVE\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )
        response = self.client.post(
            reverse("employee-customer-import"),
            {"file": upload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["preview_ready"])
        self.assertEqual(response.context["imported_count"], 0)
        self.assertContains(response, "Dòng 3")
        self.assertFalse(
            KhachHang.objects.filter(email="new@example.com").exists()
        )

    def test_customer_import_page_hides_column_guide_and_offers_test_csv(self):
        self.client.force_login(self.employee)
        response = self.client.get(reverse("employee-customer-import"))
        self.assertNotContains(response, "Cột dữ liệu")
        self.assertContains(response, "khach-hang-nhap-thu.csv")

    def test_staff_and_manager_customer_and_after_sales_layouts_render(self):
        detail_url = reverse(
            "employee-customer-detail",
            kwargs={"ma_kh": self.customer.ma_kh},
        )
        self.client.force_login(self.employee)
        employee_detail = self.client.get(detail_url)
        self.assertEqual(employee_detail.status_code, 200)
        self.assertContains(employee_detail, "customer-detail-layout")
        employee_after_sales = self.client.get(reverse("staff-after-sales"))
        employee_html = employee_after_sales.content.decode()
        self.assertEqual(employee_after_sales.status_code, 200)
        self.assertLess(
            employee_html.index("Hậu mãi"),
            employee_html.index("Danh sách khách hàng"),
        )
        self.assertLess(
            employee_html.index('data-section="notifications"'),
            employee_html.index('data-section="cancel"'),
        )

        self.client.force_login(self.manager)
        manager_detail = self.client.get(detail_url)
        self.assertEqual(manager_detail.status_code, 200)
        self.assertContains(manager_detail, "Tài khoản đăng nhập")
        manager_after_sales = self.client.get(reverse("manager-after-sales"))
        manager_html = manager_after_sales.content.decode()
        self.assertEqual(manager_after_sales.status_code, 200)
        self.assertLess(manager_html.index("Hậu mãi"), manager_html.index("Khách hàng"))

    def test_manager_can_manage_staff_roles_but_employee_cannot(self):
        url = reverse("manager-role-permissions")
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.manager)
        response = self.client.post(
            url,
            {
                "tai_khoan_id": self.employee.pk,
                "vai_tro": TaiKhoan.VaiTro.MANAGER,
            },
        )
        self.assertRedirects(response, url)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.vai_tro, TaiKhoan.VaiTro.MANAGER)
        self.assertTrue(self.employee.is_staff)

    def test_customer_pages_show_only_database_purchase_history(self):
        self.client.force_login(self.customer_account)
        response = self.client.get(
            reverse("customer-purchase-history-page")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_orders"], 0)
        self.assertNotContains(response, "DH2026001")

    def test_storefront_home_displays_only_active_catalog_data(self):
        self.client.force_login(self.customer_account)
        category = DanhMucSanPham.objects.create(
            ma_dm="DM001",
            ten_dm="Bánh dừa nướng",
            mo_ta="Đặc sản Quý Thu",
        )
        product = SanPham.objects.create(
            ma_sp="SP_HOME",
            danh_muc=category,
            ten_sp="Bánh dừa nướng truyền thống",
            mo_ta="Hương vị truyền thống",
        )
        BienTheSanPham.objects.create(
            ma_bien_the="BT_HOME",
            san_pham=product,
            huong_vi="Truyền thống",
            quy_cach="120g",
            barcode="8930000000001",
            gia_ban_le=45000,
        )
        HinhAnhSanPham.objects.create(
            ma_hinh_anh="HA_HOME",
            san_pham=product,
            duong_dan="/media/catalog/bánh-dừa.jpg",
            anh_chinh=True,
        )
        inactive_category = DanhMucSanPham.objects.create(
            ma_dm="DM_OFF",
            ten_dm="Danh mục ngừng hoạt động",
            trang_thai="INACTIVE",
        )

        response = self.client.get(reverse("storefront-home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["categories"]),
            [category],
        )
        self.assertEqual(
            list(response.context["products"]),
            [product],
        )
        self.assertContains(response, "Bánh dừa nướng truyền thống")
        self.assertContains(
            response,
            "/static/images/d%E1%BB%ABa%20n%C6%B0%E1%BB%9Bng.webp",
        )
        self.assertContains(response, "45.000 ₫")
        self.assertContains(response, "/media/catalog/")
        self.assertNotContains(response, "Thời trang")
        self.assertNotIn(
            inactive_category,
            response.context["categories"],
        )

    def test_storefront_home_search_filters_products_and_preserves_query(self):
        self.client.force_login(self.customer_account)
        category = DanhMucSanPham.objects.create(
            ma_dm="DM_FIND",
            ten_dm="Bánh dừa",
        )
        matching = SanPham.objects.create(
            ma_sp="SP_FIND",
            danh_muc=category,
            ten_sp="Bánh dừa nướng Mè đen",
        )
        BienTheSanPham.objects.create(
            ma_bien_the="BT_FIND",
            san_pham=matching,
            huong_vi="Mè đen",
            quy_cach="120g",
            barcode="8930000000002",
            gia_ban_le=50000,
        )
        unrelated = SanPham.objects.create(
            ma_sp="SP_NOISE",
            danh_muc=category,
            ten_sp="Túi quà sum vầy",
            mo_ta="Mè đen thơm bùi trong hộp quà.",
        )
        BienTheSanPham.objects.create(
            ma_bien_the="BT_NOISE",
            san_pham=unrelated,
            huong_vi="Thập cẩm",
            quy_cach="3 gói",
            barcode="8930000000003",
            gia_ban_le=100000,
        )

        response = self.client.get(
            reverse("storefront-home"),
            {"q": "Mè đen"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["search_query"], "Mè đen")
        self.assertEqual(list(response.context["products"]), [matching])
        self.assertContains(response, "Mè đen")
        self.assertNotContains(response, unrelated.ten_sp)
        self.assertNotContains(response, "home-category-card")
        self.assertContains(response, 'action="/#san-pham"')

        matching.mo_ta = "Mè rang giòn, thơm bùi."
        matching.save(update_fields=["mo_ta"])
        description_match = self.client.get(
            reverse("storefront-home"),
            {"q": "Mè rang giòn"},
        )
        self.assertEqual(list(description_match.context["products"]), [])

    def test_customer_profile_update_syncs_account_and_records_audit(self):
        self.client.force_login(self.customer_account)
        response = self.client.patch(
            reverse("thong-tin-ca-nhan"),
            {
                "ho_ten": "Khách hàng đã cập nhật",
                "email": "customer-updated@m1.test",
                "so_dien_thoai": "0909999999",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.customer_account.refresh_from_db()
        self.assertEqual(self.customer.ho_ten, "Khách hàng đã cập nhật")
        self.assertEqual(self.customer.email, "customer-updated@m1.test")
        self.assertEqual(
            self.customer_account.email,
            "customer-updated@m1.test",
        )
        self.assertTrue(
            self.customer.lich_su_thay_doi.filter(
                nguoi_thuc_hien=self.customer_account,
                loai_thay_doi=LichSuKhachHang.LoaiThayDoi.PROFILE_UPDATE,
            ).exists()
        )

    def test_customer_address_crud_keeps_a_single_default(self):
        self.client.force_login(self.customer_account)
        addresses_url = reverse("customer-address-list")
        first = self.client.post(
            addresses_url,
            {
                "ten_nguoi_nhan": "Người nhận 1",
                "so_dien_thoai": "0901111112",
                "dia_chi_chi_tiet": "1 Đường A",
                "phuong_xa": "Phường 1",
                "quan_huyen": "Hải Châu",
                "tinh_thanh": "Đà Nẵng",
                "mac_dinh": True,
            },
            content_type="application/json",
        )
        self.assertEqual(first.status_code, 201)
        first_id = first.data["data"]["ma_dia_chi"]

        second = self.client.post(
            addresses_url,
            {
                "ten_nguoi_nhan": "Người nhận 2",
                "so_dien_thoai": "0901111113",
                "dia_chi_chi_tiet": "2 Đường B",
                "phuong_xa": "Phường 2",
                "quan_huyen": "Sơn Trà",
                "tinh_thanh": "Đà Nẵng",
                "mac_dinh": True,
            },
            content_type="application/json",
        )
        self.assertEqual(second.status_code, 201)
        self.assertFalse(
            self.customer.dia_chi.get(ma_dia_chi=first_id).mac_dinh
        )
        self.assertEqual(
            self.customer.dia_chi.filter(mac_dinh=True).count(),
            1,
        )

        second_id = second.data["data"]["ma_dia_chi"]
        detail_url = reverse(
            "customer-address-detail",
            kwargs={"ma_dia_chi": second_id},
        )
        updated = self.client.patch(
            detail_url,
            {"dia_chi_chi_tiet": "2 Đường B, số 10"},
            content_type="application/json",
        )
        self.assertEqual(updated.status_code, 200)
        deleted = self.client.delete(detail_url)
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(
            self.customer.dia_chi.filter(ma_dia_chi=second_id).exists()
        )

    def test_login_remember_option_controls_session_expiry(self):
        response = self.client.post(
            reverse("dang-nhap"),
            {
                "email": self.customer_account.email,
                "mat_khau": "TestPassword123",
                "ghi_nho": True,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.client.session.get_expire_at_browser_close())

        self.client.post(reverse("dang-xuat"), content_type="application/json")
        response = self.client.post(
            reverse("dang-nhap"),
            {
                "email": self.customer_account.email,
                "mat_khau": "TestPassword123",
                "ghi_nho": False,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.client.session.get_expire_at_browser_close())
