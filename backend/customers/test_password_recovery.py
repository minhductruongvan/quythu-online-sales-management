import re
import time
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from .models import KhachHang, LoaiKhachHang, TaiKhoan


@override_settings(
    MAILERS={
        "default": {
            "BACKEND": "django.core.mail.backends.locmem.EmailBackend",
        },
    },
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class PasswordRecoveryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.email = "reset.customer@example.com"
        self.account = TaiKhoan.objects.create(
            ma_tk="TK_RESET",
            email=self.email,
            vai_tro=TaiKhoan.VaiTro.CUSTOMER,
            trang_thai=TaiKhoan.TrangThai.ACTIVE,
        )
        self.account.set_password("OldPassword123!")
        self.account.save()
        KhachHang.objects.create(
            ma_kh="KH_RESET",
            tai_khoan=self.account,
            loai_khach_hang=LoaiKhachHang.objects.get(ma_loai_kh="LKH001"),
            ho_ten="Khách hàng khôi phục",
            email=self.email,
            so_dien_thoai="0900000077",
            trang_thai=KhachHang.TrangThai.ACTIVE,
        )

    def _request_otp(self, email=None):
        return self.client.post(
            reverse("password-reset-request"),
            {"email": email or self.email},
            format="json",
        )

    def _otp_from_email(self):
        self.assertEqual(len(mail.outbox), 1)
        match = re.search(r"\b(\d{6})\b", mail.outbox[0].body)
        self.assertIsNotNone(match)
        return match.group(1)

    def test_request_sends_one_time_code_to_customer_email(self):
        response = self._request_otp()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mail.outbox[0].to, [self.email])
        self.assertIn("OTP", response.data["message"])

    def test_otp_resets_password_and_cannot_be_reused(self):
        self._request_otp()
        otp = self._otp_from_email()
        url = reverse("password-reset-confirm")

        response = self.client.post(
            url,
            {
                "email": self.email,
                "otp": otp,
                "new_password": "SecureNewPassword2026!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.account.refresh_from_db()
        self.assertTrue(self.account.check_password("SecureNewPassword2026!"))

        reused = self.client.post(
            url,
            {
                "email": self.email,
                "otp": otp,
                "new_password": "AnotherSecurePassword2026!",
            },
            format="json",
        )
        self.assertEqual(reused.status_code, 400)

    def test_unknown_email_gets_generic_response_without_sending_email(self):
        response = self._request_otp("not-a-customer@example.com")

        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.data["message"].lower())
        self.assertEqual(mail.outbox, [])

    def test_invalid_otp_is_rejected(self):
        self._request_otp()
        otp = self._otp_from_email()
        response = self.client.post(
            reverse("password-reset-confirm"),
            {
                "email": self.email,
                "otp": "000000" if otp != "000000" else "000001",
                "new_password": "SecureNewPassword2026!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_expired_otp_is_rejected(self):
        self._request_otp()
        otp = self._otp_from_email()
        expired_time = time.time() + 301

        with mock.patch(
            "customers.password_recovery.time.time",
            return_value=expired_time,
        ):
            response = self.client.post(
                reverse("password-reset-confirm"),
                {
                    "email": self.email,
                    "otp": otp,
                    "new_password": "SecureNewPassword2026!",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 400)

    def test_too_many_invalid_otp_attempts_invalidate_code(self):
        self._request_otp()
        otp = self._otp_from_email()
        wrong_otp = "000000" if otp != "000000" else "000001"
        url = reverse("password-reset-confirm")
        payload = {
            "email": self.email,
            "otp": wrong_otp,
            "new_password": "SecureNewPassword2026!",
        }

        for _ in range(5):
            self.assertEqual(
                self.client.post(url, payload, format="json").status_code,
                400,
            )

        payload["otp"] = otp
        self.assertEqual(
            self.client.post(url, payload, format="json").status_code,
            400,
        )

    def test_email_resend_is_rate_limited(self):
        self.assertEqual(self._request_otp().status_code, 200)
        limited = self._request_otp()

        self.assertEqual(limited.status_code, 429)
        self.assertEqual(len(mail.outbox), 1)

    def test_password_reset_endpoints_require_csrf_token(self):
        client = APIClient(enforce_csrf_checks=True)
        client.get(reverse("login-page"))
        csrf_token = client.cookies["csrftoken"].value
        url = reverse("password-reset-request")
        payload = {"email": self.email}

        rejected = client.post(url, payload, format="json")
        self.assertEqual(rejected.status_code, 403)

        accepted = client.post(
            url,
            payload,
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(accepted.status_code, 200)

    def test_login_page_has_password_recovery_form(self):
        response = self.client.get(reverse("login-page"))

        self.assertContains(response, "Quên mật khẩu?")
        self.assertContains(response, "Gửi mã OTP")
        self.assertContains(response, "/api/customers/password-reset/confirm/")

    @mock.patch("customers.password_recovery.EmailMessage.send", return_value=0)
    def test_email_delivery_failure_is_reported(self, email_send_mock):
        with self.assertLogs("customers.password_recovery", level="ERROR"):
            response = self._request_otp()

        self.assertEqual(response.status_code, 503)
        email_send_mock.assert_called_once()
