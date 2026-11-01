from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient

from .models import (
    TaiKhoan,
    KhachHang,
    LoaiKhachHang,
    LichSuKhachHang,
)
class PhanQuyenKhachHangTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer_account = TaiKhoan.objects.create(
            ma_tk="TK_TEST_KH",
            email="customer_test@quythu.vn",
            vai_tro=TaiKhoan.VaiTro.CUSTOMER,
            trang_thai=TaiKhoan.TrangThai.ACTIVE,
        )
        self.customer_account.set_password("Test@123")
        self.customer_account.save()
        self.customer_type = LoaiKhachHang.objects.get(
            ma_loai_kh="LKH001"
        )
        self.customer = KhachHang.objects.create(
            ma_kh="KH_TEST",
            tai_khoan=self.customer_account,
            loai_khach_hang=self.customer_type,
            ho_ten="Khách Hàng Test",
            so_dien_thoai="0900000001",
            trang_thai=KhachHang.TrangThai.ACTIVE,
        )
        self.employee_account = TaiKhoan.objects.create(
            ma_tk="TK_TEST_NV",
            email="employee_test@quythu.vn",
            vai_tro=TaiKhoan.VaiTro.EMPLOYEE,
            trang_thai=TaiKhoan.TrangThai.ACTIVE,
        )
        self.employee_account.set_password("Test@123")
        self.employee_account.save()
    def test_customer_duoc_xem_profile_cua_chinh_minh(self):
        self.client.force_authenticate(user=self.customer_account)

        response = self.client.get(
            reverse("thong-tin-ca-nhan")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["data"]["ma_kh"],
            self.customer.ma_kh,
        )

    def test_customer_khong_duoc_xem_danh_sach_khach_hang(self):
        self.client.force_authenticate(user=self.customer_account)

        response = self.client.get(
            reverse("danh-sach-khach-hang")
        )

        self.assertEqual(response.status_code, 403)

    def test_employee_duoc_xem_danh_sach_khach_hang(self):
        self.client.force_authenticate(user=self.employee_account)

        response = self.client.get(
            reverse("danh-sach-khach-hang")
        )

        self.assertEqual(response.status_code, 200)

    def test_employee_khong_duoc_truy_cap_profile_khach_hang(self):
        self.client.force_authenticate(user=self.employee_account)

        response = self.client.get(
            reverse("thong-tin-ca-nhan")
        )

        self.assertEqual(response.status_code, 403)

    def test_cap_nhat_ho_so_ghi_dung_lich_su_thay_doi(self):
        self.client.force_authenticate(user=self.employee_account)

        url = reverse(
            "chi-tiet-khach-hang",
            kwargs={"ma_kh": self.customer.ma_kh},
        )

        response = self.client.patch(
            url,
            {
                "ho_ten": "Khách Hàng Test Mới",
                "email": "customer_new@quythu.vn",
                "so_dien_thoai": "0900000099",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.customer.refresh_from_db()
        self.customer_account.refresh_from_db()

        self.assertEqual(
            self.customer.ho_ten,
            "Khách Hàng Test Mới",
        )
        self.assertEqual(
            self.customer.so_dien_thoai,
            "0900000099",
        )
        self.assertEqual(
            self.customer_account.email,
            "customer_new@quythu.vn",
        )
        self.assertEqual(
            self.customer_account.so_dien_thoai,
            "0900000099",
        )

        lich_su = LichSuKhachHang.objects.get(
            khach_hang=self.customer,
            loai_thay_doi=LichSuKhachHang.LoaiThayDoi.PROFILE_UPDATE,
        )

        self.assertEqual(
            lich_su.nguoi_thuc_hien,
            self.employee_account,
        )

        self.assertIn(
            "Họ tên: Khách Hàng Test",
            lich_su.noi_dung_cu,
        )
        self.assertIn(
            "Email: customer_test@quythu.vn",
            lich_su.noi_dung_cu,
        )
        self.assertIn(
            "Số điện thoại: 0900000001",
            lich_su.noi_dung_cu,
        )

        self.assertIn(
            "Họ tên: Khách Hàng Test Mới",
            lich_su.noi_dung_moi,
        )
        self.assertIn(
            "Email: customer_new@quythu.vn",
            lich_su.noi_dung_moi,
        )
        self.assertIn(
            "Số điện thoại: 0900000099",
            lich_su.noi_dung_moi,
        )

    def test_khong_ghi_lich_su_khi_ho_so_khong_thay_doi(self):
        self.client.force_authenticate(user=self.employee_account)

        url = reverse(
            "chi-tiet-khach-hang",
            kwargs={"ma_kh": self.customer.ma_kh},
        )

        so_lich_su_truoc = LichSuKhachHang.objects.filter(
            khach_hang=self.customer,
            loai_thay_doi=LichSuKhachHang.LoaiThayDoi.PROFILE_UPDATE,
        ).count()

        response = self.client.patch(
            url,
            {
                "ho_ten": self.customer.ho_ten,
                "email": self.customer_account.email,
                "so_dien_thoai": self.customer.so_dien_thoai,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        so_lich_su_sau = LichSuKhachHang.objects.filter(
            khach_hang=self.customer,
            loai_thay_doi=LichSuKhachHang.LoaiThayDoi.PROFILE_UPDATE,
        ).count()

        self.assertEqual(
            so_lich_su_truoc,
            so_lich_su_sau,
        )