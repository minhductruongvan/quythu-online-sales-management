from django.contrib.auth.models import AbstractUser
from django.db import models


class TaiKhoan(AbstractUser):
    username = None

    class VaiTro(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Khách hàng"
        EMPLOYEE = "EMPLOYEE", "Nhân viên"
        MANAGER = "MANAGER", "Quản lý"

    class TrangThai(models.TextChoices):
        ACTIVE = "ACTIVE", "Hoạt động"
        LOCKED = "LOCKED", "Đã khóa"

    ma_tk = models.CharField(
        max_length=10,
        unique=True,
        verbose_name="Mã tài khoản",
    )

    email = models.EmailField(
        unique=True,
        verbose_name="Email",
    )

    so_dien_thoai = models.CharField(
        max_length=15,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Số điện thoại",
    )

    vai_tro = models.CharField(
        max_length=20,
        choices=VaiTro.choices,
        default=VaiTro.CUSTOMER,
        verbose_name="Vai trò",
    )

    trang_thai = models.CharField(
        max_length=20,
        choices=TrangThai.choices,
        default=TrangThai.ACTIVE,
        verbose_name="Trạng thái",
    )

    ngay_tao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Ngày tạo",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["ma_tk"]

    def __str__(self):
        return f"{self.ma_tk} - {self.email}"

class LoaiKhachHang(models.Model):
    ma_loai_kh = models.CharField(
        max_length=10,
        primary_key=True,
        verbose_name="Mã loại khách hàng",
    )

    ten_loai_kh = models.CharField(
        max_length=50,
        unique=True,
        choices=[
            ("Khách lẻ", "Khách lẻ"),
            ("Khách sỉ", "Khách sỉ"),
        ],
        verbose_name="Tên loại khách hàng",
    )

    mo_ta = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Mô tả",
    )

    def __str__(self):
        return self.ten_loai_kh

class KhachHang(models.Model):
    class TrangThai(models.TextChoices):
        ACTIVE = "ACTIVE", "Hoạt động"
        INACTIVE = "INACTIVE", "Ngừng hoạt động"

    ma_kh = models.CharField(
        max_length=10,
        primary_key=True,
        verbose_name="Mã khách hàng",
    )

    tai_khoan = models.OneToOneField(
        TaiKhoan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="khach_hang",
        verbose_name="Tài khoản",
    )

    loai_khach_hang = models.ForeignKey(
        LoaiKhachHang,
        on_delete=models.PROTECT,
        related_name="khach_hang",
        verbose_name="Loại khách hàng",
    )

    ho_ten = models.CharField(
        max_length=100,
        verbose_name="Họ tên",
    )

    so_dien_thoai = models.CharField(
        max_length=15,
        blank=True,
        null=True,
    )

    trang_thai = models.CharField(
        max_length=20,
        choices=TrangThai.choices,
        default=TrangThai.ACTIVE,
        verbose_name="Trạng thái",
    )

    ngay_tao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Ngày tạo",
    )

    ngay_cap_nhat = models.DateTimeField(
        auto_now=True,
        verbose_name="Ngày cập nhật",
    )

    def __str__(self):
        return f"{self.ma_kh} - {self.ho_ten}"

class NhanVien(models.Model):
    class TrangThai(models.TextChoices):
        ACTIVE = "ACTIVE", "Hoạt động"
        INACTIVE = "INACTIVE", "Ngừng hoạt động"

    ma_nv = models.CharField(
        max_length=10,
        primary_key=True,
        verbose_name="Mã nhân viên",
    )

    tai_khoan = models.OneToOneField(
        TaiKhoan,
        on_delete=models.PROTECT,
        related_name="nhan_vien",
        verbose_name="Tài khoản",
    )

    ho_ten = models.CharField(
        max_length=100,
        verbose_name="Họ tên",
    )

    so_dien_thoai = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        verbose_name="Số điện thoại",
    )

    trang_thai = models.CharField(
        max_length=20,
        choices=TrangThai.choices,
        default=TrangThai.ACTIVE,
        verbose_name="Trạng thái",
    )

    ngay_tao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Ngày tạo",
    )

    ngay_cap_nhat = models.DateTimeField(
        auto_now=True,
        verbose_name="Ngày cập nhật",
    )

    def __str__(self):
        return f"{self.ma_nv} - {self.ho_ten}"

class DiaChiKH(models.Model):
    ma_dia_chi = models.CharField(
        max_length=10,
        primary_key=True,
        verbose_name="Mã địa chỉ",
    )

    khach_hang = models.ForeignKey(
        KhachHang,
        on_delete=models.CASCADE,
        related_name="dia_chi",
        verbose_name="Khách hàng",
    )

    ten_nguoi_nhan = models.CharField(
        max_length=100,
        verbose_name="Tên người nhận",
    )

    so_dien_thoai = models.CharField(
        max_length=15,
        verbose_name="Số điện thoại",
    )

    dia_chi_chi_tiet = models.CharField(
        max_length=255,
        verbose_name="Địa chỉ chi tiết",
    )

    phuong_xa = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Phường/Xã",
    )

    quan_huyen = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="Quận/Huyện",
    )

    tinh_thanh = models.CharField(
        max_length=100,
        verbose_name="Tỉnh/Thành phố",
    )

    mac_dinh = models.BooleanField(
        default=False,
        verbose_name="Địa chỉ mặc định",
    )

    ngay_tao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Ngày tạo",
    )

    ngay_cap_nhat = models.DateTimeField(
        auto_now=True,
        verbose_name="Ngày cập nhật",
    )

    def __str__(self):
        return f"{self.ten_nguoi_nhan} - {self.dia_chi_chi_tiet}"

class LichSuKhachHang(models.Model):
    class LoaiThayDoi(models.TextChoices):
        PROFILE_UPDATE = "PROFILE_UPDATE", "Cập nhật hồ sơ"
        CUSTOMER_TYPE = "CUSTOMER_TYPE", "Thay đổi loại khách hàng"
        STATUS = "STATUS", "Thay đổi trạng thái"
        ACCOUNT_LOCK = "ACCOUNT_LOCK", "Khóa tài khoản"
        ACCOUNT_UNLOCK = "ACCOUNT_UNLOCK", "Mở khóa tài khoản"
        IMPORT = "IMPORT", "Nhập dữ liệu"

    ma_lich_su = models.CharField(
        max_length=10,
        primary_key=True,
        verbose_name="Mã lịch sử",
    )

    khach_hang = models.ForeignKey(
        KhachHang,
        on_delete=models.CASCADE,
        related_name="lich_su_thay_doi",
        verbose_name="Khách hàng",
    )

    nguoi_thuc_hien = models.ForeignKey(
        TaiKhoan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lich_su_khach_hang_da_thuc_hien",
        verbose_name="Người thực hiện",
    )

    loai_thay_doi = models.CharField(
        max_length=30,
        choices=LoaiThayDoi.choices,
        verbose_name="Loại thay đổi",
    )

    noi_dung_cu = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="Nội dung cũ",
    )

    noi_dung_moi = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="Nội dung mới",
    )

    thoi_gian = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Thời gian",
    )

    def __str__(self):
        return f"{self.ma_lich_su} - {self.get_loai_thay_doi_display()}"