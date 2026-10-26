from django.db import transaction
from rest_framework import serializers

from .models import (
    TaiKhoan,
    LoaiKhachHang,
    KhachHang,
    NhanVien,
    DiaChiKH,
    LichSuKhachHang,
)


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
            so_dien_thoai=validated_data["so_dien_thoai"],
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

class DangNhapSerializer(serializers.Serializer):
    email = serializers.EmailField()
    mat_khau = serializers.CharField(
        write_only=True,
    )

    def validate_email(self, value):
        return value.strip().lower()

class ThongTinCaNhanSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        source="tai_khoan.email",
        required=False,
    )

    so_dien_thoai = serializers.CharField(
        source="tai_khoan.so_dien_thoai",
        max_length=15,
        required=False,
    )
    loai_khach_hang = serializers.CharField(
        source="loai_khach_hang.ten_loai_kh",
        read_only=True,
    )

    class Meta:
        model = KhachHang
        fields = [
            "ma_kh",
            "ho_ten",
            "email",
            "so_dien_thoai",
            "loai_khach_hang",
        ]
        read_only_fields = [
            "ma_kh",
            "loai_khach_hang",
        ]

    def validate_email(self, value):
        email = value.strip().lower()

        tai_khoan = self.instance.tai_khoan

        if tai_khoan is None:
            raise serializers.ValidationError(
                "Khách hàng này chưa có tài khoản đăng nhập."
            )

        if TaiKhoan.objects.filter(
                email__iexact=email
        ).exclude(pk=tai_khoan.pk).exists():
            raise serializers.ValidationError(
                "Email này đã được sử dụng."
            )

        return email

    def validate_so_dien_thoai(self, value):
        so_dien_thoai = value.strip()

        tai_khoan = self.instance.tai_khoan

        if TaiKhoan.objects.filter(
                so_dien_thoai=so_dien_thoai
        ).exclude(pk=tai_khoan.pk).exists():
            raise serializers.ValidationError(
                "Số điện thoại này đã được sử dụng."
            )

        return so_dien_thoai

    @transaction.atomic
    def update(self, instance, validated_data):
        tai_khoan_data = validated_data.pop("tai_khoan", {})

        if "ho_ten" in validated_data:
            instance.ho_ten = validated_data["ho_ten"]

        if "email" in tai_khoan_data:
            instance.tai_khoan.email = tai_khoan_data["email"]

        if "so_dien_thoai" in tai_khoan_data:
            so_dien_thoai = tai_khoan_data["so_dien_thoai"]
            instance.tai_khoan.so_dien_thoai = so_dien_thoai
            instance.so_dien_thoai = so_dien_thoai

        instance.tai_khoan.save()
        instance.save()

        return instance

class HoSoKhachHangSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        source="tai_khoan.email",
        required=False,
    )

    so_dien_thoai = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )
    loai_khach_hang = serializers.CharField(
        source="loai_khach_hang.ten_loai_kh",
        read_only=True,
    )

    class Meta:
        model = KhachHang
        fields = [
            "ma_kh",
            "ho_ten",
            "email",
            "so_dien_thoai",
            "loai_khach_hang",
            "trang_thai",
            "ngay_tao",
            "ngay_cap_nhat",
        ]
        read_only_fields = [
            "ma_kh",
            "loai_khach_hang",
            "trang_thai",
            "ngay_tao",
            "ngay_cap_nhat",
        ]

    def validate_email(self, value):
        email = value.strip().lower()

        tai_khoan = self.instance.tai_khoan

        if tai_khoan is None:
            raise serializers.ValidationError(
                "Khách hàng này chưa có tài khoản đăng nhập."
            )

        if TaiKhoan.objects.filter(
                email__iexact=email
        ).exclude(pk=tai_khoan.pk).exists():
            raise serializers.ValidationError(
                "Email này đã được sử dụng."
            )

        return email
    def validate_so_dien_thoai(self, value):
        so_dien_thoai = value.strip()

        if not so_dien_thoai:
            return so_dien_thoai

        if KhachHang.objects.filter(
                so_dien_thoai=so_dien_thoai
        ).exclude(
            pk=self.instance.pk
        ).exists():
            raise serializers.ValidationError(
                "Số điện thoại này đã tồn tại trong hồ sơ khách hàng."
            )

        tai_khoan_query = TaiKhoan.objects.filter(
            so_dien_thoai=so_dien_thoai
        )

        if self.instance.tai_khoan is not None:
            tai_khoan_query = tai_khoan_query.exclude(
                pk=self.instance.tai_khoan.pk
            )

        if tai_khoan_query.exists():
            raise serializers.ValidationError(
                "Số điện thoại này đã được sử dụng bởi một tài khoản."
            )

        return so_dien_thoai

    @transaction.atomic
    def update(self, instance, validated_data):
        tai_khoan_data = validated_data.pop("tai_khoan", {})

        if "ho_ten" in validated_data:
            instance.ho_ten = validated_data["ho_ten"]

        if "email" in tai_khoan_data:
            if instance.tai_khoan is None:
                raise serializers.ValidationError({
                    "email": "Khách hàng này chưa có tài khoản đăng nhập."
                })

            instance.tai_khoan.email = tai_khoan_data["email"]

        if "so_dien_thoai" in tai_khoan_data:
            so_dien_thoai = tai_khoan_data["so_dien_thoai"]

            instance.so_dien_thoai = so_dien_thoai

            if instance.tai_khoan is not None:
                instance.tai_khoan.so_dien_thoai = so_dien_thoai

        if instance.tai_khoan is not None:
            instance.tai_khoan.save()

        instance.save()

        return instance

class ThemKhachHangSerializer(serializers.Serializer):
    ho_ten = serializers.CharField(max_length=100)
    so_dien_thoai = serializers.CharField(
        max_length=15,
        required=False,
        allow_blank=True,
    )

    def validate_so_dien_thoai(self, value):
        so_dien_thoai = value.strip()

        if not so_dien_thoai:
            return so_dien_thoai

        if KhachHang.objects.filter(
                so_dien_thoai=so_dien_thoai
        ).exists():
            raise serializers.ValidationError(
                "Số điện thoại này đã tồn tại trong hồ sơ khách hàng."
            )

        if TaiKhoan.objects.filter(
                so_dien_thoai=so_dien_thoai
        ).exists():
            raise serializers.ValidationError(
                "Số điện thoại này đã được sử dụng bởi một tài khoản."
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

        khach_hang = KhachHang.objects.create(
            ma_kh=self._tao_ma_khach_hang(),
            tai_khoan=None,
            loai_khach_hang=loai_khach_le,
            ho_ten=validated_data["ho_ten"],
            so_dien_thoai=validated_data.get("so_dien_thoai") or None,
        )
        return khach_hang

    def _tao_ma_khach_hang(self):
        so_thu_tu = KhachHang.objects.count() + 1

        while True:
            ma_kh = f"KH{so_thu_tu:03d}"

            if not KhachHang.objects.filter(
                    ma_kh=ma_kh
            ).exists():
                return ma_kh

            so_thu_tu += 1

class PhanLoaiKhachHangSerializer(serializers.ModelSerializer):
    loai_khach_hang = serializers.SlugRelatedField(
        slug_field="ten_loai_kh",
        queryset=LoaiKhachHang.objects.all()
    )

    class Meta:
        model = KhachHang
        fields = [
            "ma_kh",
            "ho_ten",
            "loai_khach_hang",
        ]
        read_only_fields = [
            "ma_kh",
            "ho_ten",
        ]

class DiaChiKHSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiaChiKH
        fields = [
            "ma_dia_chi",
            "ten_nguoi_nhan",
            "so_dien_thoai",
            "dia_chi_chi_tiet",
            "phuong_xa",
            "quan_huyen",
            "tinh_thanh",
            "mac_dinh",
            "ngay_tao",
            "ngay_cap_nhat",
        ]

        read_only_fields = [
            "ma_dia_chi",
            "ngay_tao",
            "ngay_cap_nhat",
        ]