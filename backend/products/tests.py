from tempfile import TemporaryDirectory
from decimal import Decimal
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from customers.models import NhanVien, TaiKhoan
from .forms import BienTheForm, DanhMucForm, SanPhamForm
from .models import (
    BienTheSanPham,
    DanhMucSanPham,
    HinhAnhSanPham,
    LichSuGiaBienThe,
    SanPham,
)
from .templatetags.money import vnd


class MoneyFormattingTests(TestCase):
	def test_vnd_uses_dots_for_thousands_and_rounds_fractional_values(self):
		self.assertEqual(vnd(35000), "35.000")
		self.assertEqual(vnd(Decimal("1234567.5")), "1.234.568")
		self.assertEqual(vnd(None), "")


class ProductCatalogTests(TestCase):
	def setUp(self):
		self.category = DanhMucSanPham.objects.create(
			ma_dm="DM001",
			ten_dm="Bánh dừa nướng",
		)
		self.product = SanPham.objects.create(
			ma_sp="SP001",
			danh_muc=self.category,
			ten_sp="Bánh dừa Quý Thu",
			mo_ta="Bánh dừa nướng truyền thống.",
		)
		self.variant = BienTheSanPham.objects.create(
			ma_bien_the="BT001",
			san_pham=self.product,
			huong_vi="Truyền thống",
			quy_cach="120g",
			barcode="8938501000001",
			gia_ban_le=35000,
			gia_ban_si=29000,
			so_luong_toi_thieu_si=10,
		)
		HinhAnhSanPham.objects.create(
			ma_hinh_anh="HA001",
			san_pham=self.product,
			duong_dan="/media/products/primary.jpg",
			anh_chinh=True,
		)
		HinhAnhSanPham.objects.create(
			ma_hinh_anh="HA002",
			san_pham=self.product,
			duong_dan="/media/products/detail.jpg",
		)
		self.manager = TaiKhoan.objects.create_user(
			email="manager@products.test",
			ma_tk="TK001",
			password="test-password",
			vai_tro=TaiKhoan.VaiTro.MANAGER,
		)
		NhanVien.objects.create(
			ma_nv="NV001",
			tai_khoan=self.manager,
			ho_ten="Quản lý kiểm thử",
		)
		self.employee = TaiKhoan.objects.create_user(
			email="employee@products.test",
			ma_tk="TK002",
			password="test-password",
			vai_tro=TaiKhoan.VaiTro.EMPLOYEE,
		)
		NhanVien.objects.create(
			ma_nv="NV002",
			tai_khoan=self.employee,
			ho_ten="Nhân viên kiểm thử",
		)

	def test_lowest_active_variant_price_uses_database_aggregate(self):
		BienTheSanPham.objects.create(
			ma_bien_the="BT002",
			san_pham=self.product,
			huong_vi="Mè đen",
			quy_cach="125g",
			barcode="8938501000002",
			gia_ban_le=Decimal("29000"),
			trang_thai="ACTIVE",
		)
		BienTheSanPham.objects.create(
			ma_bien_the="BT003",
			san_pham=self.product,
			huong_vi="Gừng",
			quy_cach="150g",
			barcode="8938501000003",
			gia_ban_le=Decimal("25000"),
			trang_thai="INACTIVE",
		)

		self.assertEqual(
			self.product.lay_gia_thap_nhat(),
			Decimal("29000"),
		)
		BienTheSanPham.objects.filter(san_pham=self.product).update(
			trang_thai="INACTIVE",
		)
		self.assertEqual(self.product.lay_gia_thap_nhat(), 0)

	def test_customer_catalog_and_detail_render_product_images(self):
		catalog_response = self.client.get(
			reverse("products:danh_sach"),
			{"category": self.category.ma_dm},
		)
		self.assertContains(catalog_response, "/media/products/primary.jpg")
		self.assertNotContains(
			catalog_response,
			"/static/images/b%C3%A1nh%20d%E1%BB%ABa%20n%C6%B0%E1%BB%9Bng.webp",
		)

		detail_response = self.client.get(
			reverse("products:chi_tiet", args=[self.product.ma_sp])
		)
		self.assertContains(detail_response, "/media/products/primary.jpg")
		self.assertContains(detail_response, "/media/products/detail.jpg")
		self.assertNotContains(
			detail_response,
			"/static/images/b%C3%A1nh%20d%E1%BB%ABa%20n%C6%B0%E1%BB%9Bng.webp",
		)

	def test_product_detail_uses_homepage_image_mapping_without_uploaded_images(self):
		product = SanPham.objects.create(
			ma_sp="SP002",
			danh_muc=self.category,
			ten_sp="Bánh dừa nướng vị gừng",
		)

		response = self.client.get(
			reverse("products:chi_tiet", args=[product.ma_sp])
		)
		catalog_response = self.client.get(reverse("products:danh_sach"))

		self.assertContains(
			response,
			"/static/images/vi-gung.webp",
		)
		self.assertContains(
			catalog_response,
			"/static/images/vi-gung.webp",
		)

	def test_cacao_and_durian_images_are_shared_across_storefront_pages(self):
		products = (
			(
				"SP006",
				"BT006",
				"Bánh dừa nướng cacao",
				"cacao",
				"/static/images/cacao.webp",
			),
			(
				"SP007",
				"BT007",
				"Bánh dừa nướng vị sầu riêng",
				"sầu riêng",
				"/static/images/s%E1%BA%A7u%20ri%C3%AAng.webp",
			),
		)

		for product_code, variant_code, name, keyword, image_url in products:
			with self.subTest(product=product_code):
				product = SanPham.objects.create(
					ma_sp=product_code,
					danh_muc=self.category,
					ten_sp=name,
				)
				BienTheSanPham.objects.create(
					ma_bien_the=variant_code,
					san_pham=product,
					huong_vi=keyword,
					quy_cach="120g",
					barcode=f"8938501{product_code[-3:]}001",
					gia_ban_le=50000,
				)

				home_response = self.client.get(
					reverse("storefront-home"),
					{"q": keyword},
				)
				catalog_response = self.client.get(
					reverse("products:danh_sach"),
					{"q": keyword},
				)
				detail_response = self.client.get(
					reverse("products:chi_tiet", args=[product_code])
				)

				self.assertContains(home_response, image_url)
				self.assertContains(catalog_response, image_url)
				self.assertContains(detail_response, image_url)

	def test_catalog_keyword_search_only_matches_product_name(self):
		self.product.mo_ta = "Mè đen và bánh vị truyền thống, gói 120g."
		self.product.save(update_fields=["mo_ta"])
		unrelated = SanPham.objects.create(
			ma_sp="SP002",
			danh_muc=self.category,
			ten_sp="Túi quà sum vầy",
			mo_ta="Bánh vị truyền thống.",
		)
		BienTheSanPham.objects.create(
			ma_bien_the="BT002",
			san_pham=unrelated,
			huong_vi="Thập cẩm",
			quy_cach="3 gói",
			barcode="8938501000002",
			gia_ban_le=100000,
		)

		for keyword in ("Mè đen", "Truyền thống", "120g"):
			with self.subTest(keyword=keyword):
				response = self.client.get(
					reverse("products:danh_sach"),
					{"q": keyword},
				)
				self.assertEqual(response.status_code, 200)
				self.assertNotContains(response, self.product.ten_sp)
				self.assertNotContains(response, unrelated.ten_sp)

		name_match = self.client.get(
			reverse("products:danh_sach"),
			{"q": "Bánh dừa"},
		)
		self.assertContains(name_match, self.product.ten_sp)

	def test_homepage_uses_local_product_image_when_no_upload_exists(self):
		HinhAnhSanPham.objects.filter(san_pham=self.product).delete()

		response = self.client.get(reverse("storefront-home"))

		self.assertContains(
			response,
			"/static/images/b%C3%A1nh%20d%E1%BB%ABa%20n%C6%B0%E1%BB%9Bng.webp",
		)

	def test_mapped_product_images_are_shared_with_employee_and_manager(self):
		product = SanPham.objects.create(
			ma_sp="SP002",
			danh_muc=self.category,
			ten_sp="Bánh dừa nướng vị gừng",
		)
		BienTheSanPham.objects.create(
			ma_bien_the="BT002",
			san_pham=product,
			huong_vi="Gừng",
			quy_cach="120g",
			barcode="8938501000002",
			gia_ban_le=39000,
		)
		expected_image = "/static/images/vi-gung.webp"
		home_response = self.client.get(reverse("storefront-home"))
		self.assertContains(home_response, expected_image)

		for account in (self.employee, self.manager):
			with self.subTest(role=account.vai_tro):
				self.client.force_login(account)
				listing_response = self.client.get(reverse("products:quan_ly"))
				self.assertContains(listing_response, expected_image)

	def test_product_and_category_image_mappings_reference_existing_assets(self):
		from .image_assets import CATEGORY_IMAGE_ASSETS, PRODUCT_IMAGE_ASSETS

		static_image_dir = Path(__file__).resolve().parent.parent / "static" / "images"
		for asset in (*PRODUCT_IMAGE_ASSETS.values(), *CATEGORY_IMAGE_ASSETS.values()):
			with self.subTest(asset=asset):
				self.assertTrue((static_image_dir / Path(asset).name).is_file())

	def test_edit_forms_keep_existing_primary_keys(self):
		product_form = SanPhamForm(
			data={
				"ma_sp": "SP999",
				"danh_muc": self.category.ma_dm,
				"ten_sp": "Tên đã cập nhật",
				"mo_ta": "Mô tả đã cập nhật",
				"trang_thai": "ACTIVE",
			},
			instance=self.product,
		)
		self.assertTrue(product_form.is_valid(), product_form.errors)
		product_form.save()
		self.assertTrue(SanPham.objects.filter(pk="SP001").exists())
		self.assertFalse(SanPham.objects.filter(pk="SP999").exists())

		variant_form = BienTheForm(
			data={
				"ma_bien_the": "BT999",
				"huong_vi": "Truyền thống",
				"quy_cach": "120g",
				"barcode": "8938501000001",
				"gia_ban_le": "35000",
				"gia_ban_si": "29000",
				"so_luong_toi_thieu_si": "10",
				"trang_thai": "ACTIVE",
			},
			instance=self.variant,
		)
		self.assertTrue(variant_form.is_valid(), variant_form.errors)
		variant_form.save()
		self.assertTrue(BienTheSanPham.objects.filter(pk="BT001").exists())
		self.assertFalse(BienTheSanPham.objects.filter(pk="BT999").exists())

		category_form = DanhMucForm(
			data={
				"ma_dm": "DM999",
				"ten_dm": "Danh mục đã sửa",
				"mo_ta": "Mô tả đã sửa",
				"trang_thai": "ACTIVE",
			},
			instance=self.category,
		)
		self.assertTrue(category_form.is_valid(), category_form.errors)
		category_form.save()
		self.assertTrue(DanhMucSanPham.objects.filter(pk="DM001").exists())
		self.assertFalse(DanhMucSanPham.objects.filter(pk="DM999").exists())

	def test_staff_product_management_pages_render(self):
		self.client.force_login(self.manager)
		urls = (
			reverse("products:quan_ly"),
			reverse("products:chi_tiet_quan_ly", args=[self.product.ma_sp]),
			reverse("products:danh_sach_bien_the", args=[self.product.ma_sp]),
			reverse("products:quan_ly_gia", args=[self.product.ma_sp]),
			reverse("products:quan_ly_danh_muc"),
			reverse("products:sua", args=[self.product.ma_sp]),
			reverse("products:sua_bien_the", args=[self.variant.ma_bien_the]),
			reverse("products:sua_danh_muc", args=[self.category.ma_dm]),
		)
		for url in urls:
			with self.subTest(url=url):
				self.assertEqual(self.client.get(url).status_code, 200)
		detail = self.client.get(reverse("products:chi_tiet_quan_ly", args=[self.product.ma_sp]))
		self.assertContains(detail, "Khối lượng / quy cách")
		self.assertContains(detail, "Mã vạch")
		self.assertContains(detail, self.variant.barcode)
		self.assertContains(detail, self.variant.quy_cach)
		self.assertContains(detail, "/media/products/primary.jpg")
		self.assertContains(detail, "/media/products/detail.jpg")
		self.assertContains(detail, reverse("products:sua_bien_the", args=[self.variant.ma_bien_the]))
		self.assertContains(detail, "Sửa thông tin sản phẩm")

		categories_page = self.client.get(reverse("products:quan_ly_danh_muc"))
		self.assertContains(
			categories_page,
			f'{reverse("products:quan_ly")}?category={self.category.ma_dm}',
		)

		listing = self.client.get(reverse("products:quan_ly"))
		self.assertContains(listing, reverse("products:chi_tiet_quan_ly", args=[self.product.ma_sp]))
		self.assertNotContains(listing, ">Hình ảnh</a>")

	def test_staff_product_list_uses_mapped_image_when_no_image_is_uploaded(self):
		product = SanPham.objects.create(
			ma_sp="SP002",
			danh_muc=self.category,
			ten_sp="Bánh dừa nướng vị gừng",
		)
		self.client.force_login(self.manager)

		response = self.client.get(reverse("products:quan_ly"))

		self.assertContains(
			response,
			"/static/images/vi-gung.webp",
		)
		self.assertContains(response, "/media/products/primary.jpg")

	def test_price_change_is_audited_and_rendered_with_actor_and_old_values(self):
		self.client.force_login(self.manager)
		url = reverse("products:quan_ly_gia", args=[self.product.ma_sp])

		response = self.client.post(
			url,
			{
				"ma_bien_the": self.variant.ma_bien_the,
				"gia_ban_le": "36000",
				"gia_ban_si": "28000",
				"so_luong_toi_thieu_si": "8",
			},
		)

		self.assertRedirects(response, url)
		event = LichSuGiaBienThe.objects.get()
		self.assertEqual(event.bien_the, self.variant)
		self.assertEqual(event.nguoi_thuc_hien, self.manager)
		self.assertEqual(event.gia_ban_le_cu, Decimal("35000"))
		self.assertEqual(event.gia_ban_le_moi, Decimal("36000"))
		self.assertEqual(event.gia_ban_si_cu, Decimal("29000"))
		self.assertEqual(event.gia_ban_si_moi, Decimal("28000"))
		self.assertEqual(event.so_luong_toi_thieu_si_cu, 10)
		self.assertEqual(event.so_luong_toi_thieu_si_moi, 8)

		page = self.client.get(url)
		self.assertContains(page, "Lịch sử chỉnh sửa giá")
		self.assertContains(page, "manager@products.test")
		self.assertContains(page, "35.000 → 36.000")

	def test_variant_edit_also_records_price_changes(self):
		self.client.force_login(self.employee)
		response = self.client.post(
			reverse("products:sua_bien_the", args=[self.variant.ma_bien_the]),
			{
				"ma_bien_the": self.variant.ma_bien_the,
				"huong_vi": self.variant.huong_vi,
				"quy_cach": self.variant.quy_cach,
				"barcode": self.variant.barcode,
				"gia_ban_le": "36000",
				"gia_ban_si": "28000",
				"so_luong_toi_thieu_si": "8",
				"trang_thai": self.variant.trang_thai,
			},
		)

		self.assertRedirects(
			response,
			reverse("products:danh_sach_bien_the", args=[self.product.ma_sp]),
		)
		event = LichSuGiaBienThe.objects.get()
		self.assertEqual(event.nguoi_thuc_hien, self.employee)
		self.assertEqual(event.gia_ban_le_cu, Decimal("35000"))
		self.assertEqual(event.gia_ban_le_moi, Decimal("36000"))

	def test_unchanged_prices_do_not_create_duplicate_history(self):
		self.client.force_login(self.manager)
		url = reverse("products:quan_ly_gia", args=[self.product.ma_sp])

		response = self.client.post(
			url,
			{
				"ma_bien_the": self.variant.ma_bien_the,
				"gia_ban_le": "35000",
				"gia_ban_si": "29000",
				"so_luong_toi_thieu_si": "10",
			},
		)

		self.assertRedirects(response, url)
		self.assertFalse(LichSuGiaBienThe.objects.exists())

	def test_price_can_be_cleared_and_invalid_price_change_is_rejected(self):
		self.client.force_login(self.manager)
		url = reverse("products:quan_ly_gia", args=[self.product.ma_sp])
		response = self.client.post(
			url,
			{
				"ma_bien_the": self.variant.ma_bien_the,
				"gia_ban_le": "35000",
				"gia_ban_si": "",
				"so_luong_toi_thieu_si": "10",
			},
		)

		self.assertRedirects(response, url)
		self.variant.refresh_from_db()
		self.assertIsNone(self.variant.gia_ban_si)
		event = LichSuGiaBienThe.objects.get()
		self.assertEqual(event.gia_ban_si_cu, Decimal("29000"))
		self.assertIsNone(event.gia_ban_si_moi)

		response = self.client.post(
			url,
			{
				"ma_bien_the": self.variant.ma_bien_the,
				"gia_ban_le": "35000",
				"gia_ban_si": "40000",
				"so_luong_toi_thieu_si": "10",
			},
		)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(LichSuGiaBienThe.objects.count(), 1)

	def test_upload_after_deleting_an_image_uses_a_new_unique_code(self):
		self.client.force_login(self.manager)
		HinhAnhSanPham.objects.filter(pk="HA001").delete()
		self.assertFalse(HinhAnhSanPham.objects.filter(pk="HA001").exists())

		with TemporaryDirectory() as media_root:
			with override_settings(MEDIA_ROOT=media_root):
				response = self.client.post(
					reverse("products:quan_ly_hinh_anh", args=[self.product.ma_sp]),
					{
						"thao_tac": "them_anh",
						"tep_anh": SimpleUploadedFile(
							"new-product.jpg",
							b"\xff\xd8\xff\xe0test image content",
							content_type="image/jpeg",
						),
					},
				)

		self.assertEqual(response.status_code, 302)
		self.assertTrue(HinhAnhSanPham.objects.filter(pk="HA002").exists())
		self.assertTrue(HinhAnhSanPham.objects.filter(pk="HA003").exists())

	def test_variant_form_validates_ean13_and_keeps_existing_values(self):
		self.variant.huong_vi = "Cacao"
		self.variant.quy_cach = "300g"
		self.variant.so_luong_toi_thieu_si = 12
		self.variant.save()

		form_edit = BienTheForm(instance=self.variant)
		rendered = form_edit.as_p()
		self.assertIn('value="12"', rendered)
		self.assertIn("Cacao", rendered)
		self.assertIn("300g", rendered)

		invalid_form = BienTheForm(
			data={
				"ma_bien_the": "BT099",
				"huong_vi": "Truyền thống",
				"quy_cach": "120g",
				"barcode": "abc123",
				"gia_ban_le": "40000",
				"gia_ban_si": "30000",
				"so_luong_toi_thieu_si": "10",
				"trang_thai": "ACTIVE",
			}
		)
		self.assertFalse(invalid_form.is_valid())
		self.assertIn("barcode", invalid_form.errors)

	def test_inactive_category_products_are_hidden_from_storefront(self):
		self.category.trang_thai = "INACTIVE"
		self.category.save(update_fields=["trang_thai"])

		home_response = self.client.get(reverse("storefront-home"))
		self.assertNotContains(home_response, self.product.ten_sp)

		catalog_response = self.client.get(reverse("products:danh_sach"))
		self.assertNotContains(catalog_response, self.product.ten_sp)

		detail_response = self.client.get(
			reverse("products:chi_tiet", args=[self.product.ma_sp])
		)
		self.assertEqual(detail_response.status_code, 404)

		new_form = SanPhamForm()
		self.assertNotIn(self.category, new_form.fields["danh_muc"].queryset)

	def test_barcode_management_rejects_variant_from_another_product(self):
		other_product = SanPham.objects.create(
			ma_sp="SP002",
			danh_muc=self.category,
			ten_sp="Sản phẩm khác",
		)
		other_variant = BienTheSanPham.objects.create(
			ma_bien_the="BT099",
			san_pham=other_product,
			huong_vi="Gừng",
			quy_cach="120g",
			barcode="8938501000099",
			gia_ban_le=40000,
		)

		self.client.force_login(self.manager)
		response = self.client.post(
			reverse("products:quan_ly_ma_vach", args=[self.product.ma_sp]),
			{
				"ma_bien_the": other_variant.ma_bien_the,
				"barcode": "8938501000088",
			},
		)
		self.assertEqual(response.status_code, 404)
		other_variant.refresh_from_db()
		self.assertEqual(other_variant.barcode, "8938501000099")

	def test_delete_variant_used_in_order_shows_error_instead_of_crashing(self):
		from customers.models import KhachHang, LoaiKhachHang
		from orders.models import ChiTietDonHang, DonHang, LoaiGia, PhuongThucThanhToan, TinhThanh

		loai_kh, _ = LoaiKhachHang.objects.get_or_create(
			ma_loai_kh="LKH001",
			defaults={"ten_loai_kh": "Khách lẻ"},
		)
		customer_account = TaiKhoan.objects.create_user(
			email="buyer@products.test",
			ma_tk="TK099",
			password="test-password",
			vai_tro=TaiKhoan.VaiTro.CUSTOMER,
		)
		khach_hang = KhachHang.objects.create(
			ma_kh="KH099",
			tai_khoan=customer_account,
			loai_khach_hang=loai_kh,
			ho_ten="Khách kiểm thử",
		)
		tinh, _ = TinhThanh.objects.get_or_create(
			ma_tinh="TT001",
			defaults={
				"ten_tinh": "Quảng Nam",
				"vung_mien": TinhThanh.VungMien.TRUNG,
				"phi_van_chuyen": Decimal("20000"),
			},
		)
		pttt, _ = PhuongThucThanhToan.objects.get_or_create(
			ma_pttt=PhuongThucThanhToan.MA_COD,
			defaults={"ten_pttt": "Thanh toán khi nhận hàng"},
		)
		don_hang = DonHang.objects.create(
			ma_dh="DH099",
			khach_hang=khach_hang,
			loai_khach_hang_ap_dung=loai_kh,
			ho_ten_nguoi_nhan="Khách kiểm thử",
			sdt_nguoi_nhan="0900000000",
			dia_chi_giao_hang="123 Đường ABC",
			tinh_thanh=tinh,
			tong_tien_hang=Decimal("35000"),
			phi_van_chuyen=Decimal("20000"),
			tong_thanh_toan=Decimal("55000"),
			phuong_thuc_thanh_toan=pttt,
		)
		ChiTietDonHang.objects.create(
			ma_ctdh="CT099",
			don_hang=don_hang,
			bien_the=self.variant,
			so_luong=1,
			loai_gia_ap_dung=LoaiGia.GIA_LE,
			don_gia=Decimal("35000"),
			thanh_tien=Decimal("35000"),
		)

		self.client.force_login(self.manager)
		response = self.client.post(
			reverse("products:xoa_bien_the", args=[self.variant.ma_bien_the]),
			follow=True,
		)
		self.assertEqual(response.status_code, 200)
		self.assertTrue(BienTheSanPham.objects.filter(pk=self.variant.ma_bien_the).exists())
		self.assertContains(response, "Ngừng kinh doanh")

	def test_primary_key_validators_reject_slashes_spaces_and_case_duplicates(self):
		bad_product = SanPhamForm(
			data={
				"ma_sp": "SP/01",
				"danh_muc": self.category.ma_dm,
				"ten_sp": "Bánh mới",
				"trang_thai": "ACTIVE",
			}
		)
		self.assertFalse(bad_product.is_valid())
		self.assertIn("ma_sp", bad_product.errors)

		bad_variant = BienTheForm(
			data={
				"ma_bien_the": "BT 02",
				"huong_vi": "Gừng",
				"quy_cach": "120g",
				"barcode": "8938501000012",
				"gia_ban_le": "40000",
				"gia_ban_si": "35000",
				"so_luong_toi_thieu_si": "10",
				"trang_thai": "ACTIVE",
			}
		)
		self.assertFalse(bad_variant.is_valid())
		self.assertIn("ma_bien_the", bad_variant.errors)

		dup_category = DanhMucForm(
			data={
				"ma_dm": "DM002",
				"ten_dm": "bánh dừa nướng",
				"trang_thai": "ACTIVE",
			}
		)
		self.assertFalse(dup_category.is_valid())
		self.assertIn("ten_dm", dup_category.errors)

	def test_vietnamese_unicode_case_insensitive_search(self):
		product = SanPham.objects.create(
			ma_sp="SP007",
			danh_muc=self.category,
			ten_sp="Bánh dừa nướng vị sầu riêng đặc biệt",
		)
		BienTheSanPham.objects.create(
			ma_bien_the="BT007",
			san_pham=product,
			huong_vi="Sầu riêng",
			quy_cach="120g",
			barcode="8938501000071",
			gia_ban_le=49000,
		)

		catalog_response = self.client.get(
			reverse("products:danh_sach"),
			{"q": "SẦU RIÊNG ĐẶC BIỆT"},
		)
		self.assertContains(catalog_response, product.ten_sp)

		self.client.force_login(self.manager)
		staff_response = self.client.get(
			reverse("products:quan_ly"),
			{"q": "ĐẶC BIỆT"},
		)
		self.assertContains(staff_response, product.ten_sp)

	def test_inactive_category_blocks_cart_add_in_module_3(self):
		from customers.models import KhachHang, LoaiKhachHang
		from orders.services import DichVuGioHang, LoiNghiepVuDonHang

		loai_kh, _ = LoaiKhachHang.objects.get_or_create(
			ma_loai_kh="LKH001",
			defaults={"ten_loai_kh": "Khách lẻ"},
		)
		customer_account = TaiKhoan.objects.create_user(
			email="inactive-cat-buyer@products.test",
			ma_tk="TK098",
			password="test-password",
			vai_tro=TaiKhoan.VaiTro.CUSTOMER,
		)
		khach_hang = KhachHang.objects.create(
			ma_kh="KH098",
			tai_khoan=customer_account,
			loai_khach_hang=loai_kh,
			ho_ten="Khách kiểm thử danh mục",
		)
		self.category.trang_thai = "INACTIVE"
		self.category.save(update_fields=["trang_thai"])
		self.variant.refresh_from_db()

		self.assertFalse(DichVuGioHang.bien_the_con_ban(self.variant))
		with self.assertRaises(LoiNghiepVuDonHang):
			DichVuGioHang.them_vao_gio(khach_hang, self.variant, 1)

	def test_product_without_active_variants_shows_contact_label_not_zero_price(self):
		no_variant_product = SanPham.objects.create(
			ma_sp="SP020",
			danh_muc=self.category,
			ten_sp="Sản phẩm chưa có biến thể",
		)
		catalog_response = self.client.get(reverse("products:danh_sach"))
		self.assertContains(catalog_response, no_variant_product.ten_sp)
		self.assertContains(catalog_response, "Liên hệ")
		self.assertNotContains(catalog_response, "<strong>0 ₫</strong>")

		self.client.force_login(self.manager)
		staff_response = self.client.get(reverse("products:quan_ly"))
		self.assertContains(staff_response, "Chưa có giá")

	def test_wholesale_customer_sees_wholesale_price_on_catalog_and_home(self):
		from customers.models import KhachHang, LoaiKhachHang

		loai_si, _ = LoaiKhachHang.objects.get_or_create(
			ma_loai_kh="LKH002",
			defaults={"ten_loai_kh": "Khách sỉ"},
		)
		wholesale_account = TaiKhoan.objects.create_user(
			email="wholesale@products.test",
			ma_tk="TK097",
			password="test-password",
			vai_tro=TaiKhoan.VaiTro.CUSTOMER,
		)
		KhachHang.objects.create(
			ma_kh="KH097",
			tai_khoan=wholesale_account,
			loai_khach_hang=loai_si,
			ho_ten="Đối tác sỉ",
		)

		self.client.force_login(wholesale_account)
		catalog_response = self.client.get(reverse("products:danh_sach"))
		self.assertContains(catalog_response, "29.000 ₫")
		home_response = self.client.get(reverse("storefront-home"))
		self.assertContains(home_response, "29.000 ₫")

	def test_first_uploaded_image_auto_becomes_primary_and_product_delete_cleans_file(self):
		self.client.force_login(self.manager)
		new_product = SanPham.objects.create(
			ma_sp="SP030",
			danh_muc=self.category,
			ten_sp="Sản phẩm xóa kèm ảnh",
		)

		with TemporaryDirectory() as media_root:
			with override_settings(MEDIA_ROOT=media_root):
				upload_response = self.client.post(
					reverse("products:quan_ly_hinh_anh", args=[new_product.ma_sp]),
					{
						"thao_tac": "them_anh",
						"tep_anh": SimpleUploadedFile(
							"first-photo.jpg",
							b"\xff\xd8\xff\xe0fake jpg bytes",
							content_type="image/jpeg",
						),
					},
				)
				self.assertEqual(upload_response.status_code, 302)
				img = HinhAnhSanPham.objects.get(san_pham=new_product)
				self.assertTrue(img.anh_chinh)
				saved_file = Path(media_root) / "products" / "first-photo.jpg"
				self.assertTrue(saved_file.is_file())

				delete_response = self.client.post(
					reverse("products:xoa", args=[new_product.ma_sp])
				)
				self.assertEqual(delete_response.status_code, 302)
				self.assertFalse(SanPham.objects.filter(pk=new_product.ma_sp).exists())
				self.assertFalse(saved_file.exists())

	def test_auto_generate_ean13_produces_new_unique_barcode_on_regenerate(self):
		self.client.force_login(self.manager)
		url = reverse("products:quan_ly_ma_vach", args=[self.product.ma_sp])

		first_resp = self.client.post(
			url,
			{"thao_tac": "sinh_tu_dong", "ma_bien_the": self.variant.ma_bien_the},
		)
		self.assertRedirects(first_resp, url)
		self.variant.refresh_from_db()
		first_barcode = self.variant.barcode
		self.assertRegex(first_barcode, r"^893[0-9]{10}$")

		second_resp = self.client.post(
			url,
			{"thao_tac": "sinh_tu_dong", "ma_bien_the": self.variant.ma_bien_the},
		)
		self.assertRedirects(second_resp, url)
		self.variant.refresh_from_db()
		self.assertNotEqual(self.variant.barcode, first_barcode)
		self.assertRegex(self.variant.barcode, r"^893[0-9]{10}$")

	def test_db_constraints_enforce_unique_flavor_pack_and_valid_prices(self):
		from django.db import IntegrityError, transaction

		with self.assertRaises(IntegrityError):
			with transaction.atomic():
				BienTheSanPham.objects.create(
					ma_bien_the="BT_DUP",
					san_pham=self.product,
					huong_vi=self.variant.huong_vi,
					quy_cach=self.variant.quy_cach,
					barcode="8938501000098",
					gia_ban_le=40000,
				)

		with self.assertRaises(IntegrityError):
			with transaction.atomic():
				BienTheSanPham.objects.create(
					ma_bien_the="BT_BADP",
					san_pham=self.product,
					huong_vi="Gừng",
					quy_cach="225g",
					barcode="8938501000097",
					gia_ban_le=30000,
					gia_ban_si=40000,
				)

	def test_filtered_catalog_shows_matching_variant_price_and_catalog_header_search(self):
		BienTheSanPham.objects.create(
			ma_bien_the="BT002",
			san_pham=self.product,
			huong_vi="Mè đen",
			quy_cach="150g",
			barcode="8938501000002",
			gia_ban_le=49000,
			gia_ban_si=42000,
			trang_thai="ACTIVE",
		)

		response = self.client.get(
			reverse("products:danh_sach"),
			{"flavor": "Mè đen"},
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "49.000 ₫")
		self.assertNotContains(response, "35.000 ₫")
		self.assertContains(response, f'action="{reverse("products:danh_sach")}"')

	def test_variant_form_defaults_unit_to_goi_when_blank(self):
		from .models import DonViTinh

		goi, _ = DonViTinh.objects.get_or_create(
			ma_dvt="DVT001",
			defaults={"ten_dvt": "Gói", "ky_hieu": "goi"},
		)
		form = BienTheForm(
			data={
				"ma_bien_the": "BT050",
				"huong_vi": "Gừng",
				"quy_cach": "120g",
				"don_vi_tinh": "",
				"barcode": "8938501000050",
				"gia_ban_le": "40000",
				"gia_ban_si": "35000",
				"so_luong_toi_thieu_si": "10",
				"trang_thai": "ACTIVE",
			}
		)
		self.assertTrue(form.is_valid(), form.errors)
		self.assertEqual(form.cleaned_data["don_vi_tinh"], goi)

	def test_activating_product_under_inactive_category_warns_and_preserves_filter_query(self):
		self.category.trang_thai = "INACTIVE"
		self.category.save(update_fields=["trang_thai"])
		self.product.trang_thai = "INACTIVE"
		self.product.save(update_fields=["trang_thai"])

		self.client.force_login(self.manager)
		response = self.client.post(
			reverse("products:doi_trang_thai", args=[self.product.ma_sp]),
			{"return_query": "q=Qu%C3%BD&status=INACTIVE"},
		)
		self.assertEqual(response.status_code, 302)
		self.assertIn("q=Qu%C3%BD", response["Location"])
		self.assertIn("status=INACTIVE", response["Location"])

		followed = self.client.get(reverse("products:quan_ly"))
		self.assertContains(followed, "Danh mục ngừng áp dụng")
		self.assertContains(followed, "Đang ẩn (DM tắt)")

	def test_empty_image_upload_rejected_and_ean13_advances_without_oscillating(self):
		self.client.force_login(self.manager)
		img_url = reverse("products:quan_ly_hinh_anh", args=[self.product.ma_sp])
		empty_resp = self.client.post(
			img_url,
			{
				"thao_tac": "them_anh",
				"tep_anh": SimpleUploadedFile("empty.jpg", b"", content_type="image/jpeg"),
			},
			follow=True,
		)
		self.assertContains(empty_resp, "Tệp ảnh rỗng")

		barcode_url = reverse("products:quan_ly_ma_vach", args=[self.product.ma_sp])
		generated = []
		for _ in range(3):
			self.client.post(
				barcode_url,
				{"thao_tac": "sinh_tu_dong", "ma_bien_the": self.variant.ma_bien_the},
			)
			self.variant.refresh_from_db()
			generated.append(self.variant.barcode)
		self.assertEqual(len(set(generated)), 3)

	def test_delete_product_cascades_unused_variants_in_one_action(self):
		self.client.force_login(self.manager)
		BienTheSanPham.objects.create(
			ma_bien_the="BT002",
			san_pham=self.product,
			huong_vi="Gừng",
			quy_cach="225g",
			barcode="8938501000002",
			gia_ban_le=65000,
		)

		response = self.client.post(
			reverse("products:xoa", args=[self.product.ma_sp]),
			follow=True,
		)
		self.assertEqual(response.status_code, 200)
		self.assertFalse(SanPham.objects.filter(pk=self.product.ma_sp).exists())
		self.assertFalse(BienTheSanPham.objects.filter(san_pham_id=self.product.ma_sp).exists())
		self.assertContains(response, "cùng 2 biến thể")

	def test_delete_product_rolls_back_when_any_variant_is_used_in_order(self):
		from customers.models import KhachHang, LoaiKhachHang
		from orders.models import ChiTietDonHang, DonHang, LoaiGia, PhuongThucThanhToan, TinhThanh

		unused_variant = BienTheSanPham.objects.create(
			ma_bien_the="BT002",
			san_pham=self.product,
			huong_vi="Mè đen",
			quy_cach="150g",
			barcode="8938501000002",
			gia_ban_le=49000,
		)
		loai_kh, _ = LoaiKhachHang.objects.get_or_create(
			ma_loai_kh="LKH001",
			defaults={"ten_loai_kh": "Khách lẻ"},
		)
		customer_account = TaiKhoan.objects.create_user(
			email="prod-del-buyer@products.test",
			ma_tk="TK096",
			password="test-password",
			vai_tro=TaiKhoan.VaiTro.CUSTOMER,
		)
		khach_hang = KhachHang.objects.create(
			ma_kh="KH096",
			tai_khoan=customer_account,
			loai_khach_hang=loai_kh,
			ho_ten="Khách kiểm thử xóa SP",
		)
		tinh, _ = TinhThanh.objects.get_or_create(
			ma_tinh="TT001",
			defaults={
				"ten_tinh": "Quảng Nam",
				"vung_mien": TinhThanh.VungMien.TRUNG,
				"phi_van_chuyen": Decimal("20000"),
			},
		)
		pttt, _ = PhuongThucThanhToan.objects.get_or_create(
			ma_pttt=PhuongThucThanhToan.MA_COD,
			defaults={"ten_pttt": "Thanh toán khi nhận hàng"},
		)
		don_hang = DonHang.objects.create(
			ma_dh="DH096",
			khach_hang=khach_hang,
			loai_khach_hang_ap_dung=loai_kh,
			ho_ten_nguoi_nhan="Khách kiểm thử xóa SP",
			sdt_nguoi_nhan="0900000001",
			dia_chi_giao_hang="123 Đường ABC",
			tinh_thanh=tinh,
			tong_tien_hang=Decimal("35000"),
			phi_van_chuyen=Decimal("20000"),
			tong_thanh_toan=Decimal("55000"),
			phuong_thuc_thanh_toan=pttt,
		)
		ChiTietDonHang.objects.create(
			ma_ctdh="CT096",
			don_hang=don_hang,
			bien_the=self.variant,
			so_luong=1,
			loai_gia_ap_dung=LoaiGia.GIA_LE,
			don_gia=Decimal("35000"),
			thanh_tien=Decimal("35000"),
		)

		self.client.force_login(self.manager)
		response = self.client.post(
			reverse("products:xoa", args=[self.product.ma_sp]),
			follow=True,
		)
		self.assertEqual(response.status_code, 200)
		self.assertTrue(SanPham.objects.filter(pk=self.product.ma_sp).exists())
		self.assertTrue(BienTheSanPham.objects.filter(pk=self.variant.ma_bien_the).exists())
		self.assertTrue(BienTheSanPham.objects.filter(pk=unused_variant.ma_bien_the).exists())
		self.assertContains(response, "Ngừng kinh doanh")

	def test_fake_image_upload_rejected_by_magic_bytes(self):
		self.client.force_login(self.manager)
		with TemporaryDirectory() as media_root:
			with override_settings(MEDIA_ROOT=media_root):
				response = self.client.post(
					reverse("products:quan_ly_hinh_anh", args=[self.product.ma_sp]),
					{
						"thao_tac": "them_anh",
						"tep_anh": SimpleUploadedFile(
							"fake.jpg",
							b"<html>not an image</html>",
							content_type="image/jpeg",
						),
					},
					follow=True,
				)
		self.assertContains(response, "không phải ảnh JPG, PNG hoặc WEBP hợp lệ")
		self.assertFalse(HinhAnhSanPham.objects.filter(duong_dan__contains="fake.jpg").exists())

	def test_variant_and_price_forms_reject_zero_prices_and_duplicate_pair_inline(self):
		dup_form = BienTheForm(
			data={
				"ma_bien_the": "BT088",
				"huong_vi": self.variant.huong_vi,
				"quy_cach": self.variant.quy_cach,
				"barcode": "8938501000088",
				"gia_ban_le": "35000",
				"gia_ban_si": "29000",
				"so_luong_toi_thieu_si": "10",
				"trang_thai": "ACTIVE",
			},
			san_pham=self.product,
		)
		self.assertFalse(dup_form.is_valid())
		self.assertIn("quy_cach", dup_form.errors)

		zero_price_form = BienTheForm(
			data={
				"ma_bien_the": "BT089",
				"huong_vi": "Gừng",
				"quy_cach": "225g",
				"barcode": "8938501000089",
				"gia_ban_le": "0",
				"gia_ban_si": "0",
				"so_luong_toi_thieu_si": "10",
				"trang_thai": "ACTIVE",
			},
			san_pham=self.product,
		)
		self.assertFalse(zero_price_form.is_valid())
		self.assertIn("gia_ban_le", zero_price_form.errors)
		self.assertIn("gia_ban_si", zero_price_form.errors)

		self.client.force_login(self.manager)
		price_resp = self.client.post(
			reverse("products:quan_ly_gia", args=[self.product.ma_sp]),
			{
				"ma_bien_the": self.variant.ma_bien_the,
				"gia_ban_le": "35000",
				"gia_ban_si": "0",
				"so_luong_toi_thieu_si": "10",
			},
		)
		self.assertEqual(price_resp.status_code, 200)
		self.variant.refresh_from_db()
		self.assertEqual(self.variant.gia_ban_si, Decimal("29000"))

	def test_staff_status_filter_separates_hidden_by_category_and_catalog_ignores_unknown_filters(self):
		self.category.trang_thai = "INACTIVE"
		self.category.save(update_fields=["trang_thai"])
		self.client.force_login(self.manager)

		active_only = self.client.get(reverse("products:quan_ly"), {"status": "ACTIVE"})
		self.assertNotContains(active_only, self.product.ten_sp)
		self.assertContains(active_only, "Không tìm thấy sản phẩm phù hợp với điều kiện lọc hiện tại.")

		hidden_only = self.client.get(reverse("products:quan_ly"), {"status": "HIDDEN"})
		self.assertContains(hidden_only, self.product.ten_sp)

		catalog_resp = self.client.get(
			reverse("products:danh_sach"),
			{"flavor": "KhongTonTaiXYZ", "pack": "9999kg"},
		)
		self.assertNotContains(catalog_resp, "KhongTonTaiXYZ")
		self.assertNotContains(catalog_resp, "9999kg")

	def test_nfd_vietnamese_search_and_category_duplicate_detection(self):
		import unicodedata

		nfd_keyword = unicodedata.normalize("NFD", "Bánh dừa")
		catalog_resp = self.client.get(reverse("products:danh_sach"), {"q": nfd_keyword})
		self.assertContains(catalog_resp, self.product.ten_sp)

		nfd_dup_cat = DanhMucForm(
			data={
				"ma_dm": "DM099",
				"ten_dm": unicodedata.normalize("NFD", "bánh dừa nướng"),
				"trang_thai": "ACTIVE",
			}
		)
		self.assertFalse(nfd_dup_cat.is_valid())
		self.assertIn("ten_dm", nfd_dup_cat.errors)

	def test_price_form_rejects_overflow_wholesale_quantity_without_500(self):
		self.client.force_login(self.manager)
		url = reverse("products:quan_ly_gia", args=[self.product.ma_sp])
		response = self.client.post(
			url,
			{
				"ma_bien_the": self.variant.ma_bien_the,
				"gia_ban_le": "35000",
				"gia_ban_si": "29000",
				"so_luong_toi_thieu_si": "99999999999999999999",
			},
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "vượt quá giới hạn")
		self.variant.refresh_from_db()
		self.assertEqual(self.variant.so_luong_toi_thieu_si, 10)

	def test_catalog_does_not_leak_inactive_variant_flavors_or_packs_in_sidebar(self):
		BienTheSanPham.objects.create(
			ma_bien_the="BT077",
			san_pham=self.product,
			huong_vi="Vị Bí Mật",
			quy_cach="999g",
			barcode="8938501000077",
			gia_ban_le=45000,
			trang_thai="INACTIVE",
		)
		response = self.client.get(
			reverse("products:danh_sach"),
			{"flavor": "Vị Bí Mật", "pack": "999g"},
		)
		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, "Vị Bí Mật")
		self.assertNotContains(response, "999g")

	def test_image_upload_sanitizes_windows_reserved_filename(self):
		self.client.force_login(self.manager)
		with TemporaryDirectory() as media_root:
			with override_settings(MEDIA_ROOT=media_root):
				response = self.client.post(
					reverse("products:quan_ly_hinh_anh", args=[self.product.ma_sp]),
					{
						"thao_tac": "them_anh",
						"tep_anh": SimpleUploadedFile(
							"CON.jpg",
							b"\xff\xd8\xff\xe0valid jpg header",
							content_type="image/jpeg",
						),
					},
				)
				self.assertEqual(response.status_code, 302)
				saved = HinhAnhSanPham.objects.filter(
					san_pham=self.product,
					duong_dan__contains="san_pham_CON.jpg",
				)
				self.assertTrue(saved.exists())
				self.assertTrue((Path(media_root) / "products" / "san_pham_CON.jpg").is_file())

	def test_db_constraints_and_admin_forms_reject_zero_prices_and_invalid_codes(self):
		from django.db import IntegrityError, transaction
		from .admin import BienTheAdminForm

		with self.assertRaises(IntegrityError):
			with transaction.atomic():
				BienTheSanPham.objects.create(
					ma_bien_the="BT_ZERO1",
					san_pham=self.product,
					huong_vi="Cacao",
					quy_cach="300g",
					barcode="8938501000095",
					gia_ban_le=0,
				)

		with self.assertRaises(IntegrityError):
			with transaction.atomic():
				BienTheSanPham.objects.create(
					ma_bien_the="BT_ZERO2",
					san_pham=self.product,
					huong_vi="Cacao",
					quy_cach="450g",
					barcode="8938501000094",
					gia_ban_le=30000,
					gia_ban_si=0,
				)

		admin_form = BienTheAdminForm(
			data={
				"ma_bien_the": "BT/BAD",
				"san_pham": self.product.ma_sp,
				"huong_vi": self.variant.huong_vi,
				"quy_cach": self.variant.quy_cach,
				"barcode": "not13digits",
				"gia_ban_le": "0",
				"gia_ban_si": "0",
				"so_luong_toi_thieu_si": "10",
				"trang_thai": "ACTIVE",
			}
		)
		self.assertFalse(admin_form.is_valid())
		self.assertIn("ma_bien_the", admin_form.errors)
		self.assertIn("barcode", admin_form.errors)
		self.assertIn("gia_ban_le", admin_form.errors)
		self.assertIn("quy_cach", admin_form.errors)
