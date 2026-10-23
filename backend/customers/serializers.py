from django.db import transaction
from rest_framework import serializers

from .models import TaiKhoan, KhachHang, LoaiKhachHang


class DangKyKhachHangSerializer(serializers.Serializer):
    email = serializers.EmailField()
    so_dien_thoai = serializers.CharField(max_length=15)
    mat_khau = serializers.CharField(
        write_only=True,
        min_length=8,
    )
    ho_ten = serializers.CharField(max_length=100)

    def validate_email(self, value):
        email = value.strip().lower()

        if TaiKhoan.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                "Email này đã được sử dụng."
            )

        return email

    def validate_so_dien_thoai(self, value):
        so_dien_thoai = value.strip()

        if TaiKhoan.objects.filter(
            so_dien_thoai=so_dien_thoai
        ).exists():
            raise serializers.ValidationError(
                "Số điện thoại này đã được sử dụng."
            )

        return so_dien_thoai

    @transaction.atomic
    def create(self, validated_data):
        loai_khach_le, _ = LoaiKhachHang.objects.get_or_create(
            ma_loai_kh="LKH001",
            defaults={
                "ten_loai_kh": "Khách lẻ",
                "mo_ta": "Khách hàng bán lẻ",
            },
        )

        tai_khoan = TaiKhoan(
            ma_tk=self._tao_ma_tai_khoan(),
            email=validated_data["email"],
            so_dien_thoai=validated_data["so_dien_thoai"],
            vai_tro=TaiKhoan.VaiTro.CUSTOMER,
            trang_thai=TaiKhoan.TrangThai.ACTIVE,
        )

        tai_khoan.set_password(validated_data["mat_khau"])
        tai_khoan.save()

        khach_hang = KhachHang.objects.create(
            ma_kh=self._tao_ma_khach_hang(),
            tai_khoan=tai_khoan,
            loai_khach_hang=loai_khach_le,
            ho_ten=validated_data["ho_ten"],
        )

        return khach_hang

    def _tao_ma_tai_khoan(self):
        so_thu_tu = TaiKhoan.objects.count() + 1

        while True:
            ma_tk = f"TK{so_thu_tu:03d}"

            if not TaiKhoan.objects.filter(ma_tk=ma_tk).exists():
                return ma_tk

            so_thu_tu += 1

    def _tao_ma_khach_hang(self):
        so_thu_tu = KhachHang.objects.count() + 1

        while True:
            ma_kh = f"KH{so_thu_tu:03d}"

            if not KhachHang.objects.filter(ma_kh=ma_kh).exists():
                return ma_kh

            so_thu_tu += 1