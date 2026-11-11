import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from customers.models import (
    KhachHang,
    LoaiKhachHang,
    NhanVien,
    TaiKhoan,
)


class Command(BaseCommand):
    help = "Create or refresh the three local demo accounts."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Demo accounts may only be seeded when DEBUG=True."
            )

        password = os.environ.get("M1_DEMO_PASSWORD", "Quythu123!")
        if not password:
            raise CommandError("The demo account password cannot be empty.")

        customer_type, _ = LoaiKhachHang.objects.get_or_create(
            ma_loai_kh="LKH001",
            defaults={
                "ten_loai_kh": "Khách lẻ",
                "mo_ta": "Khách hàng bán lẻ",
            },
        )
        accounts = (
            (
                "khachhang@gmail.com",
                "DEMO001",
                TaiKhoan.VaiTro.CUSTOMER,
                "Khách hàng Quý Thu",
                "KHDEMO001",
            ),
            (
                "nhanvien@gmail.com",
                "DEMO002",
                TaiKhoan.VaiTro.EMPLOYEE,
                "Nhân viên Quý Thu",
                "NVDEMO001",
            ),
            (
                "quanly@gmail.com",
                "DEMO003",
                TaiKhoan.VaiTro.MANAGER,
                "Quản lý Quý Thu",
                "NVDEMO002",
            ),
        )

        for email, account_code, role, full_name, profile_code in accounts:
            account, created = TaiKhoan.objects.get_or_create(
                email=email,
                defaults={
                    "ma_tk": account_code,
                    "vai_tro": role,
                    "trang_thai": TaiKhoan.TrangThai.ACTIVE,
                },
            )
            account.vai_tro = role
            account.trang_thai = TaiKhoan.TrangThai.ACTIVE
            account.is_active = True
            account.is_staff = role == TaiKhoan.VaiTro.MANAGER
            account.set_password(password)
            account.save()

            if role == TaiKhoan.VaiTro.CUSTOMER:
                KhachHang.objects.get_or_create(
                    tai_khoan=account,
                    defaults={
                        "ma_kh": profile_code,
                        "loai_khach_hang": customer_type,
                        "ho_ten": full_name,
                        "email": email,
                        "trang_thai": KhachHang.TrangThai.ACTIVE,
                    },
                )
            else:
                NhanVien.objects.get_or_create(
                    tai_khoan=account,
                    defaults={
                        "ma_nv": profile_code,
                        "ho_ten": full_name,
                        "trang_thai": NhanVien.TrangThai.ACTIVE,
                    },
                )

            verb = "Created" if created else "Updated"
            self.stdout.write(f"{verb} {role.lower()} account: {email}")
