from django.test import TestCase
from django.utils.html import strip_tags

from customers.models import DiaChiKH, KhachHang, LoaiKhachHang, NhanVien, TaiKhoan
from products.models import BienTheSanPham, DanhMucSanPham, SanPham


class IntegratedActorPagesTests(TestCase):
    def setUp(self):
        retail, _ = LoaiKhachHang.objects.get_or_create(
            ma_loai_kh="LKH001",
            defaults={"ten_loai_kh": "Khách lẻ"},
        )
        self.customer_account = TaiKhoan.objects.create_user(
            email="ui-customer@example.test",
            ma_tk="UITK001",
            password="Test-password-123",
            vai_tro=TaiKhoan.VaiTro.CUSTOMER,
        )
        KhachHang.objects.create(
            ma_kh="UIKH001",
            tai_khoan=self.customer_account,
            loai_khach_hang=retail,
            ho_ten="Khách giao diện",
        )
        self.employee_account = TaiKhoan.objects.create_user(
            email="ui-employee@example.test",
            ma_tk="UITK002",
            password="Test-password-123",
            vai_tro=TaiKhoan.VaiTro.EMPLOYEE,
        )
        NhanVien.objects.create(ma_nv="UINV001", tai_khoan=self.employee_account, ho_ten="Nhân viên giao diện")
        self.manager_account = TaiKhoan.objects.create_user(
            email="ui-manager@example.test",
            ma_tk="UITK003",
            password="Test-password-123",
            vai_tro=TaiKhoan.VaiTro.MANAGER,
        )
        NhanVien.objects.create(ma_nv="UINV002", tai_khoan=self.manager_account, ho_ten="Quản lý giao diện")

    def test_guest_can_browse_store_and_catalog(self):
        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertContains(home, "images/quythu-banner.png")
        visible_text = strip_tags(home.content.decode())
        for internal_label in ("M1", "M2", "M3", "M4", "M5", "Ma trận quyền"):
            self.assertNotIn(internal_label, visible_text)
        catalog = self.client.get("/products/")
        self.assertEqual(catalog.status_code, 200)
        self.assertContains(catalog, "Danh mục sản phẩm")
        self.assertContains(catalog, 'name="q"')
        self.assertContains(catalog, "catalog-layout")
        self.assertNotContains(catalog, "Quản lý sản phẩm")
        self.assertEqual(self.client.get("/tai-khoan/dang-ky/").status_code, 200)
        self.assertEqual(self.client.get("/tai-khoan/dang-nhap/").status_code, 200)

    def test_catalog_supports_multiple_filters_on_the_same_active_variant(self):
        category_one = DanhMucSanPham.objects.create(
            ma_dm="UIDM001",
            ten_dm="Đặc sản nướng",
            trang_thai="ACTIVE",
        )
        category_two = DanhMucSanPham.objects.create(
            ma_dm="UIDM002",
            ten_dm="Đặc sản quà tặng",
            trang_thai="ACTIVE",
        )
        products = []
        for code, category, name in (
            ("UISP001", category_one, "Bánh truyền thống"),
            ("UISP002", category_two, "Bánh mè đen"),
            ("UISP003", category_one, "Hộp vị phối hợp"),
        ):
            products.append(
                SanPham.objects.create(
                    ma_sp=code,
                    danh_muc=category,
                    ten_sp=name,
                    trang_thai="ACTIVE",
                )
            )

        for variant_code, product, flavor, pack, barcode in (
            ("UIBT001", products[0], "Truyền thống", "120g", "UI00000000001"),
            ("UIBT002", products[1], "Mè đen", "225g", "UI00000000002"),
            ("UIBT003", products[2], "Truyền thống", "120g", "UI00000000003"),
            ("UIBT004", products[2], "Mè đen", "225g", "UI00000000004"),
        ):
            BienTheSanPham.objects.create(
                ma_bien_the=variant_code,
                san_pham=product,
                huong_vi=flavor,
                quy_cach=pack,
                barcode=barcode,
                gia_ban_le=50000,
                trang_thai="ACTIVE",
            )

        categories = self.client.get(
            "/products/?category=UIDM001&category=UIDM002"
        )
        self.assertContains(categories, "Bánh truyền thống")
        self.assertContains(categories, "Bánh mè đen")
        self.assertContains(categories, "Hộp vị phối hợp")

        matching_variant = self.client.get(
            "/products/?flavor=Truyền+thống&pack=120g"
        )
        self.assertContains(matching_variant, "Bánh truyền thống")
        self.assertContains(matching_variant, "Hộp vị phối hợp")
        self.assertNotContains(matching_variant, "Bánh mè đen")

        no_matching_variant = self.client.get(
            "/products/?flavor=Truyền+thống&pack=225g"
        )
        self.assertNotContains(no_matching_variant, "Hộp vị phối hợp")

    def test_product_detail_uses_fallback_image_and_keeps_variant_cart_selection(self):
        category = DanhMucSanPham.objects.create(
            ma_dm="UIDM010",
            ten_dm="Đặc sản Quý Thu",
            trang_thai="ACTIVE",
        )
        product = SanPham.objects.create(
            ma_sp="UISP010",
            danh_muc=category,
            ten_sp="Bánh dừa nướng",
            mo_ta="Mô tả sản phẩm thử nghiệm.",
            trang_thai="ACTIVE",
        )
        BienTheSanPham.objects.create(
            ma_bien_the="UIBT010",
            san_pham=product,
            huong_vi="Truyền thống",
            quy_cach="120g",
            barcode="UI00000000010",
            gia_ban_le=50000,
            gia_ban_si=45000,
            so_luong_toi_thieu_si=10,
            trang_thai="ACTIVE",
        )

        guest_page = self.client.get("/products/chi-tiet/UISP010/")
        self.assertContains(guest_page, 'src="https://placehold.co/400x300?text=Banh+Dua+Quy+Thu"')
        self.assertNotContains(guest_page, "Hình ảnh sản phẩm sẽ được cập nhật")
        self.assertContains(guest_page, 'data-product-variant-picker')
        self.assertContains(guest_page, "THÔNG TIN MINH BẠCH")
        self.assertContains(guest_page, "Danh sách thành phần chi tiết chưa được cung cấp")
        self.assertContains(guest_page, 'data-product-variant-select="UIBT010"')
        self.assertContains(guest_page, "Khối lượng")
        self.assertNotContains(guest_page, "Giá sỉ")
        self.assertContains(guest_page, "Đăng nhập để mua hàng")
        self.assertNotContains(guest_page, "js-add-to-cart")

        self.client.force_login(self.customer_account)
        customer_page = self.client.get("/products/chi-tiet/UISP010/")
        self.assertContains(
            customer_page,
            'class="product-purchase-form js-add-to-cart"',
        )
        self.assertContains(customer_page, 'name="ma_bien_the"')
        self.assertContains(customer_page, "Mô tả sản phẩm thử nghiệm.")
        self.assertNotContains(customer_page, "Giá sỉ")

        wholesale_type, _ = LoaiKhachHang.objects.get_or_create(
            ma_loai_kh="LKH002",
            defaults={"ten_loai_kh": "Khách sỉ"},
        )
        customer = KhachHang.objects.get(tai_khoan=self.customer_account)
        customer.loai_khach_hang = wholesale_type
        customer.save(update_fields=["loai_khach_hang"])
        wholesale_page = self.client.get("/products/chi-tiet/UISP010/")
        self.assertContains(wholesale_page, "Giá sỉ")

        self.client.force_login(self.manager_account)
        manager_page = self.client.get("/products/chi-tiet/UISP010/")
        self.assertContains(manager_page, "Mở không gian quản lý")
        self.assertContains(manager_page, 'href="/quan-ly/"')
        self.assertNotContains(manager_page, 'class="product-purchase-form js-add-to-cart"')

    def test_customer_can_register_and_log_in_with_the_new_account(self):
        registration = self.client.post(
            "/api/customers/register/",
            {
                "ho_ten": "Khách hàng mới",
                "email": "new-customer@example.test",
                "so_dien_thoai": "0901234567",
                "mat_khau": "Test-password-123",
                "loai_khach_hang": "LKH001",
            },
            content_type="application/json",
        )
        self.assertEqual(registration.status_code, 201, registration.json())

        login = self.client.post(
            "/api/customers/login/",
            {
                "email": "new-customer@example.test",
                "mat_khau": "Test-password-123",
                "ghi_nho": False,
            },
            content_type="application/json",
        )
        self.assertEqual(login.status_code, 200, login.json())
        self.assertEqual(self.client.get("/gio-hang/").status_code, 200)
        customer = KhachHang.objects.get(tai_khoan__email="new-customer@example.test")
        self.assertEqual(customer.loai_khach_hang_id, "LKH001")

    def test_registration_ignores_self_selected_wholesale_type(self):
        registration = self.client.post(
            "/api/customers/register/",
            {
                "ho_ten": "Đại lý Quý Thu",
                "email": "wholesale@example.test",
                "so_dien_thoai": "0901234568",
                "mat_khau": "Test-password-123",
                "loai_khach_hang": "LKH002",
            },
            content_type="application/json",
        )
        self.assertEqual(registration.status_code, 201, registration.json())
        customer = KhachHang.objects.get(tai_khoan__email="wholesale@example.test")
        self.assertEqual(customer.loai_khach_hang_id, "LKH001")
        self.assertEqual(customer.tai_khoan.vai_tro, TaiKhoan.VaiTro.CUSTOMER)
        self.assertEqual(
            registration.json()["data"]["ma_loai_khach_hang"],
            "LKH001",
        )

        missing_type = self.client.post(
            "/api/customers/register/",
            {
                "ho_ten": "Chưa chọn loại",
                "email": "no-type@example.test",
                "so_dien_thoai": "0901234569",
                "mat_khau": "Test-password-123",
            },
            content_type="application/json",
        )
        self.assertEqual(missing_type.status_code, 201, missing_type.json())
        self.assertEqual(
            KhachHang.objects.get(tai_khoan__email="no-type@example.test").loai_khach_hang_id,
            "LKH001",
        )

    def test_auth_forms_use_post_and_registration_script_is_async(self):
        registration_page = self.client.get("/tai-khoan/dang-ky/")
        self.assertContains(registration_page, 'method="post"')
        self.assertContains(
            registration_page,
            'form.addEventListener("submit", async function (event)',
        )
        self.assertContains(registration_page, "/api/customers/register/")
        self.assertNotContains(registration_page, 'name="loai_khach_hang"')
        self.assertContains(registration_page, "images/quythu-auth-coconut.png")

        login_page = self.client.get("/tai-khoan/dang-nhap/")
        self.assertContains(login_page, 'method="post"')
        self.assertContains(login_page, "/api/customers/login/")
        self.assertContains(login_page, "images/quythu-auth-coconut.png")

    def test_customer_address_checkout_and_staff_filter_controls_render(self):
        self.client.force_login(self.customer_account)
        addresses = self.client.get("/tai-khoan/dia-chi/")
        self.assertContains(addresses, '<select id="province" required>')
        checkout = self.client.get("/thanh-toan/?chon=CG001")
        self.assertContains(checkout, '<select id="checkout-province"')
        cart = self.client.get("/gio-hang/")
        self.assertContains(cart, 'id="cart-select-all"')
        self.assertContains(cart, 'id="cart-selected-count"')

        self.client.force_login(self.employee_account)
        staff_orders = self.client.get("/don-hang/")
        self.assertContains(staff_orders, 'name="loai_khach"')
        self.assertContains(staff_orders, "Tất cả loại khách")

    def test_customer_workflows_render_and_remain_customer_only(self):
        self.client.force_login(self.customer_account)
        for path in (
            "/gio-hang/",
            "/thanh-toan/?chon=CG001",
            "/don-cua-toi/",
            "/don-cua-toi/DH001/",
            "/tai-khoan/hau-mai/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        checkout = self.client.get("/thanh-toan/?chon=CG001")
        self.assertContains(checkout, "checkout-add-address")
        self.assertContains(checkout, "checkout-address-dialog")
        self.assertContains(checkout, "Lưu địa chỉ và tiếp tục")
        self.assertContains(checkout, 'data-address-api="/api/customers/addresses/"')
        self.assertContains(checkout, 'data-cart-api="/api/orders/cart/"')
        self.assertContains(checkout, '<select id="checkout-province"')
        storefront = self.client.get("/products/")
        self.assertContains(storefront, 'class="qt-account-menu"')
        self.assertContains(storefront, 'aria-label="Mở menu tài khoản"')
        self.assertContains(storefront, "Cài đặt tài khoản")
        self.assertContains(storefront, "Thông tin cá nhân")
        self.assertContains(storefront, "Đăng xuất")
        self.assertNotContains(storefront, "Không gian nhân viên")
        self.assertNotContains(storefront, "Quản trị")

        address = self.client.post(
            "/api/customers/addresses/",
            {
                "ten_nguoi_nhan": "Khách giao diện",
                "so_dien_thoai": "0901234567",
                "dia_chi_chi_tiet": "1 đường Mẫu",
                "phuong_xa": "Phường Hải Châu 1",
                "quan_huyen": "Hải Châu",
                "tinh_thanh": "Đà Nẵng",
                "mac_dinh": True,
            },
            content_type="application/json",
        )
        self.assertEqual(address.status_code, 201, address.json())
        self.assertTrue(
            DiaChiKH.objects.filter(khach_hang__tai_khoan=self.customer_account).exists()
        )
        invalid_address = self.client.post(
            "/api/customers/addresses/",
            {
                "ten_nguoi_nhan": "Khách giao diện",
                "so_dien_thoai": "0901234568",
                "dia_chi_chi_tiet": "2 đường Mẫu",
                "phuong_xa": "Phường không hợp lệ",
                "quan_huyen": "Không hợp lệ",
                "tinh_thanh": "Tỉnh tự nhập",
                "mac_dinh": False,
            },
            content_type="application/json",
        )
        self.assertEqual(invalid_address.status_code, 400)
        self.assertEqual(self.client.get("/products/quan-ly/").status_code, 403)
        self.assertEqual(self.client.get("/reports/dashboard/").status_code, 403)

    def test_employee_workflows_render(self):
        self.client.force_login(self.employee_account)
        dashboard = self.client.get("/nhan-vien/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertNotContains(dashboard, "Quản lý nhân sự")
        self.assertContains(dashboard, "Khách hàng")
        self.assertContains(dashboard, "Nhập khách hàng")
        self.assertContains(dashboard, "Xuất khách hàng")
        self.assertContains(dashboard, "Thêm sản phẩm")
        self.assertContains(dashboard, "Báo cáo chi tiết")
        self.assertEqual(self.client.get("/quan-ly/phan-quyen/").status_code, 403)
        for path in (
            "/don-hang/",
            "/don-hang/DH001/",
            "/nhan-vien/hau-mai/",
            "/products/quan-ly/",
            "/reports/dashboard/",
            "/reports/chi-tiet/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_manager_workflows_render(self):
        self.client.force_login(self.manager_account)
        dashboard = self.client.get("/quan-ly/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Không gian quản lý")
        self.assertNotContains(dashboard, "Không gian làm việc nhân viên")
        self.assertContains(dashboard, "Quản lý nhân sự")
        self.assertContains(dashboard, "Báo cáo chi tiết")
        self.assertContains(dashboard, "Nhập khách hàng")
        self.assertContains(dashboard, "Thêm sản phẩm")
        staff_roles = self.client.get("/quan-ly/phan-quyen/")
        self.assertEqual(staff_roles.status_code, 200)
        self.assertNotContains(staff_roles, "Ma trận quyền")
        for path in (
            "/quan-ly/",
            "/quan-ly/hau-mai/",
            "/quan-ly/phan-quyen/",
            "/products/quan-ly/",
            "/reports/dashboard/",
            "/reports/chi-tiet/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_report_exports_and_data_require_staff_login(self):
        self.assertEqual(self.client.get("/reports/api/dashboard-data/").status_code, 302)
        self.client.force_login(self.manager_account)
        self.assertEqual(self.client.get("/reports/api/dashboard-data/").status_code, 200)
        self.assertEqual(self.client.get("/reports/export/csv/").status_code, 200)
        self.assertEqual(self.client.get("/reports/chi-tiet/?page=invalid").status_code, 400)
