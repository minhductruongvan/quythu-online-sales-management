from django.db import models


class LoaiBaoCao(models.TextChoices):
    CHI_TIET_DOANH_THU = "Chi tiết doanh thu", "Chi tiết doanh thu"
    SAN_PHAM_BAN_CHAY = "Sản phẩm bán chạy", "Sản phẩm bán chạy"
    SAN_PHAM_BAN_GAN_DAY = "Sản phẩm bán gần đây", "Sản phẩm bán gần đây"
    KHU_VUC = "Khu vực", "Khu vực"


class NhatKyXuatBaoCao(models.Model):
    class DinhDang(models.TextChoices):
        CSV = "CSV", "CSV"
        EXCEL = "Excel", "Excel"
        PDF = "PDF", "PDF"

    ma_nhat_ky_xuat = models.CharField(max_length=10, primary_key=True, verbose_name="Mã nhật ký xuất")
    nhan_vien = models.ForeignKey(
        "customers.NhanVien",
        on_delete=models.PROTECT,
        related_name="nhat_ky_xuat_bao_cao",
        verbose_name="Nhân viên",
    )
    loai_bao_cao = models.CharField(
        max_length=50,
        choices=LoaiBaoCao.choices,
        verbose_name="Loại báo cáo",
    )
    ky_bao_cao = models.CharField(max_length=100, verbose_name="Kỳ báo cáo")
    bo_loc_ap_dung = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="Bộ lọc áp dụng",
    )
    dinh_dang_file = models.CharField(
        max_length=10,
        choices=DinhDang.choices,
        verbose_name="Định dạng file",
    )
    thoi_diem_xuat = models.DateTimeField(auto_now_add=True, verbose_name="Thời điểm xuất")

    class Meta:
        db_table = "NHATKY_XUAT_BAOCAO"
        verbose_name = "Nhật ký xuất báo cáo"
        verbose_name_plural = "Nhật ký xuất báo cáo"
        ordering = ["-thoi_diem_xuat"]

    def __str__(self):
        return f"{self.ma_nhat_ky_xuat} - {self.get_loai_bao_cao_display()}"