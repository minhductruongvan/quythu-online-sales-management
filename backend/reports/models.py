from django.db import models


class LoaiBaoCao(models.TextChoices):
    TONG_QUAN = "Tổng quan", "Tổng quan"
    DOANH_THU_SO_DON = "Doanh thu & số lượng đơn", "Doanh thu & số lượng đơn"
    CHI_TIET_DOANH_THU = "Chi tiết doanh thu", "Chi tiết doanh thu"
    SAN_PHAM_BAN_CHAY = "Sản phẩm bán chạy", "Sản phẩm bán chạy"
    SAN_PHAM_BAN_GAN_DAY = "Sản phẩm bán gần đây", "Sản phẩm bán gần đây"
    KHU_VUC = "Khu vực", "Khu vực"


class PhanQuyenBaoCao(models.Model):
    ma_phan_quyen = models.CharField(max_length=10, primary_key=True, verbose_name="Mã phân quyền")
    nhan_vien = models.ForeignKey(
        "customers.NhanVien",
        on_delete=models.CASCADE,
        related_name="phan_quyen_bao_cao",
        verbose_name="Nhân viên",
    )
    loai_bao_cao = models.CharField(
        max_length=50,
        choices=LoaiBaoCao.choices,
        verbose_name="Loại báo cáo",
    )
    quyen_xem = models.BooleanField(default=False, verbose_name="Được xem")
    quyen_xuat = models.BooleanField(default=False, verbose_name="Được xuất")
    nhan_vien_cap = models.ForeignKey(
        "customers.NhanVien",
        on_delete=models.PROTECT,
        related_name="phan_quyen_bao_cao_da_cap",
        verbose_name="Người cấp quyền",
    )
    thoi_diem_cap = models.DateTimeField(auto_now_add=True, verbose_name="Thời điểm cấp")
    thoi_diem_thu_hoi = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Thời điểm thu hồi",
    )

    class Meta:
        db_table = "PHANQUYEN_BAOCAO"
        verbose_name = "Phân quyền báo cáo"
        verbose_name_plural = "Phân quyền báo cáo"
        constraints = [
            models.UniqueConstraint(
                fields=["nhan_vien", "loai_bao_cao"],
                name="uq_nv_loai_bao_cao",
            ),
            models.CheckConstraint(
                condition=models.Q(quyen_xuat=False) | models.Q(quyen_xem=True),
                name="ck_bao_cao_xuat_can_quyen_xem",
            ),
            models.CheckConstraint(
                condition=models.Q(loai_bao_cao__in=LoaiBaoCao.values),
                name="ck_bao_cao_loai_hop_le",
            ),
        ]

    def __str__(self):
        return f"{self.nhan_vien_id} - {self.get_loai_bao_cao_display()}"


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
