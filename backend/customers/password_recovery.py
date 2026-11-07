import hashlib
import hmac
import logging
import math
import secrets
import time
from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import KhachHang, TaiKhoan


logger = logging.getLogger(__name__)

OTP_TTL_SECONDS = 300
OTP_RESEND_SECONDS = 60
OTP_MAX_REQUESTS_PER_HOUR = 5
OTP_MAX_ATTEMPTS = 5
GENERIC_REQUEST_MESSAGE = (
    "Nếu email thuộc tài khoản khách hàng, mã OTP sẽ được gửi đến hộp thư."
)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.RegexField(r"^\d{6}$")
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        return value.strip().lower()


def _cache_key(kind, email):
    email_hash = hashlib.sha256(email.encode("utf-8")).hexdigest()
    return f"customer-password-reset:{kind}:{email_hash}"


def _otp_digest(email, otp):
    message = f"{email}:{otp}".encode("utf-8")
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def _active_customer_account(email):
    return TaiKhoan.objects.filter(
        email__iexact=email,
        vai_tro=TaiKhoan.VaiTro.CUSTOMER,
        trang_thai=TaiKhoan.TrangThai.ACTIVE,
        is_active=True,
        khach_hang__trang_thai=KhachHang.TrangThai.ACTIVE,
    ).first()


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    @method_decorator(csrf_protect)
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        request_count_key = _cache_key("requests", email)
        if not cache.add(
            request_count_key,
            1,
            timeout=3600,
        ):
            request_count = cache.incr(request_count_key)
        else:
            request_count = 1

        if request_count > OTP_MAX_REQUESTS_PER_HOUR:
            return Response(
                {"message": "Bạn đã yêu cầu quá nhiều mã. Vui lòng thử lại sau."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        cooldown_key = _cache_key("cooldown", email)
        if not cache.add(cooldown_key, True, timeout=OTP_RESEND_SECONDS):
            return Response(
                {"message": "Vui lòng đợi trước khi yêu cầu mã OTP mới."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        account = _active_customer_account(email)
        if account is None:
            return Response(
                {"message": GENERIC_REQUEST_MESSAGE},
                status=status.HTTP_200_OK,
            )

        otp = f"{secrets.randbelow(1_000_000):06d}"
        expiration = time.time() + OTP_TTL_SECONDS
        message = (
            f"Mã OTP đặt lại mật khẩu Quý Thu của bạn là: {otp}\n\n"
            "Mã có hiệu lực trong 5 phút và chỉ sử dụng được một lần. "
            "Nếu bạn không yêu cầu đặt lại mật khẩu, hãy bỏ qua email này."
        )

        try:
            email_message = EmailMessage(
                subject="Mã OTP đặt lại mật khẩu Quý Thu",
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[account.email],
            )
            sent_count = email_message.send(using="default")
        except (OSError, SMTPException):
            cache.delete(cooldown_key)
            logger.exception(
                "Could not send password reset OTP email for customer account."
            )
            return Response(
                {"message": "Không gửi được email OTP. Vui lòng thử lại sau."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if sent_count != 1:
            cache.delete(cooldown_key)
            logger.error("Password reset OTP email was not accepted by backend.")
            return Response(
                {"message": "Không gửi được email OTP. Vui lòng thử lại sau."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        cache.set(
            _cache_key("otp", email),
            {
                "digest": _otp_digest(email, otp),
                "attempts": 0,
                "expires_at": expiration,
            },
            timeout=OTP_TTL_SECONDS,
        )
        return Response(
            {"message": GENERIC_REQUEST_MESSAGE},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    @method_decorator(csrf_protect)
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        account = _active_customer_account(data["email"])
        otp_key = _cache_key("otp", data["email"])
        otp_data = cache.get(otp_key)

        if (
            account is None
            or otp_data is None
            or otp_data["expires_at"] <= time.time()
        ):
            cache.delete(otp_key)
            return Response(
                {"message": "OTP không hợp lệ hoặc đã hết hạn."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        provided_digest = _otp_digest(data["email"], data["otp"])
        if not hmac.compare_digest(otp_data["digest"], provided_digest):
            otp_data["attempts"] += 1
            remaining_seconds = math.ceil(otp_data["expires_at"] - time.time())
            if otp_data["attempts"] >= OTP_MAX_ATTEMPTS or remaining_seconds <= 0:
                cache.delete(otp_key)
            else:
                cache.set(
                    otp_key,
                    otp_data,
                    timeout=remaining_seconds,
                )
            return Response(
                {"message": "OTP không hợp lệ hoặc đã hết hạn."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(data["new_password"], user=account)
        except ValidationError as error:
            return Response(
                {"message": "Mật khẩu mới chưa đạt yêu cầu.", "errors": error.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        account.set_password(data["new_password"])
        account.save(update_fields=["password"])
        cache.delete(otp_key)
        cache.delete(_cache_key("cooldown", data["email"]))
        return Response(
            {"message": "Đặt lại mật khẩu thành công. Vui lòng đăng nhập lại."},
            status=status.HTTP_200_OK,
        )
