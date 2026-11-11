from tempfile import TemporaryDirectory
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from customers.models import NhanVien, TaiKhoan
from .forms import BienTheForm, DanhMucForm, SanPhamForm
from .models import BienTheSanPham, DanhMucSanPham, HinhAnhSanPham, SanPham
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

	def test_customer_catalog_and_detail_render_product_images(self):
		catalog_response = self.client.get(
			reverse("products:danh_sach"),
			{"category": self.category.ma_dm},
		)
		self.assertContains(catalog_response, "/media/products/primary.jpg")
		self.assertNotContains(
			catalog_response,
			"/static/images/Gemini_Generated_Image_l2w5xgl2w5xgl2w5.png",
		)

		detail_response = self.client.get(
			reverse("products:chi_tiet", args=[self.product.ma_sp])
		)
		self.assertContains(detail_response, "/media/products/primary.jpg")
		self.assertContains(detail_response, "/media/products/detail.jpg")
		self.assertNotContains(
			detail_response,
			"/static/images/Gemini_Generated_Image_l2w5xgl2w5xgl2w5.png",
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
			"/static/images/Gemini_Generated_Image_s5w1mls5w1mls5w1.png",
		)
		self.assertContains(
			catalog_response,
			"/static/images/Gemini_Generated_Image_s5w1mls5w1mls5w1.png",
		)

	def test_cacao_and_durian_images_are_shared_across_storefront_pages(self):
		products = (
			(
				"SP006",
				"BT006",
				"Bánh dừa nướng cacao",
				"cacao",
				"/static/images/cacao.png",
			),
			(
				"SP007",
				"BT007",
				"Bánh dừa nướng vị sầu riêng",
				"sầu riêng",
				"/static/images/s%E1%BA%A7u%20ri%C3%AAng.png",
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
			"/static/images/Gemini_Generated_Image_l2w5xgl2w5xgl2w5.png",
		)

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
		self.assertContains(detail, self.variant.quy_cach)
		self.assertContains(detail, "/media/products/primary.jpg")
		self.assertContains(detail, "/media/products/detail.jpg")
		self.assertContains(detail, reverse("products:sua_bien_the", args=[self.variant.ma_bien_the]))
		self.assertContains(detail, "Sửa thông tin sản phẩm")

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
			"/static/images/Gemini_Generated_Image_s5w1mls5w1mls5w1.png",
		)
		self.assertContains(response, "/media/products/primary.jpg")

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
							b"test image content",
							content_type="image/jpeg",
						),
					},
				)

		self.assertEqual(response.status_code, 302)
		self.assertTrue(HinhAnhSanPham.objects.filter(pk="HA002").exists())
		self.assertTrue(HinhAnhSanPham.objects.filter(pk="HA003").exists())
