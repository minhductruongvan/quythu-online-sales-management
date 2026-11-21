from django.db import models
from django.db.models import F, Min, Q


# ==========================================================
# 1. BẢNG DANH MỤC SẢN PHẨM (Ví dụ: Bánh dừa nướng, Bánh kẹo)
# ==========================================================
class DanhMucSanPham(models.Model):
    # Mã danh mục làm khóa chính (ví dụ: DM001)
    ma_dm = models.CharField(max_length=10, primary_key=True, verbose_name="Mã danh mục")

    # Tên danh mục (ví dụ: Bánh dừa nướng)
    ten_dm = models.CharField(max_length=100, unique=True, verbose_name="Tên danh mục")

    # Mô tả thêm về danh mục
    mo_ta = models.CharField(max_length=500, blank=True, null=True, verbose_name="Mô tả")

    # Trạng thái: ACTIVE (đang dùng) hoặc INACTIVE (ngừng dùng)
    trang_thai = models.CharField(max_length=20, default='ACTIVE', verbose_name="Trạng thái")

    # Tự động lưu ngày tạo
    ngay_tao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'DANHMUCSANPHAM'
        verbose_name = 'Danh mục sản phẩm'
        verbose_name_plural = 'Danh mục sản phẩm'

    # Hàm này giúp hiển thị tên danh mục thay vì hiển thị mã khó hiểu
    def __str__(self):
        return self.ten_dm


# ==========================================================
# 2. BẢNG SẢN PHẨM CHÍNH (Ví dụ: Bánh dừa nướng Quý Thu)
# ==========================================================
class SanPham(models.Model):
    # Mã sản phẩm làm khóa chính (ví dụ: SP001)
    ma_sp = models.CharField(max_length=10, primary_key=True, verbose_name="Mã sản phẩm")

    # Sản phẩm này thuộc về danh mục nào (liên kết khóa ngoại đến DanhMucSanPham)
    danh_muc = models.ForeignKey(DanhMucSanPham, on_delete=models.PROTECT, verbose_name="Danh mục")

    # Tên sản phẩm
    ten_sp = models.CharField(max_length=200, verbose_name="Tên sản phẩm")

    # Mô tả giới thiệu sản phẩm
    mo_ta = models.TextField(blank=True, null=True, verbose_name="Mô tả chi tiết")

    # Trạng thái: ACTIVE (đang bán) hoặc INACTIVE (ngừng bán)
    trang_thai = models.CharField(max_length=20, default='ACTIVE', verbose_name="Trạng thái")

    ngay_tao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'SANPHAM'
        verbose_name = 'Sản phẩm'
        verbose_name_plural = 'Sản phẩm'

    def __str__(self):
        return self.ten_sp

    # Hàm tính giá thấp nhất từ các biến thể đang bán (theo yêu cầu M2-BR07)
    def lay_gia_thap_nhat(self):
        gia_thap_nhat = BienTheSanPham.objects.filter(
            san_pham=self,
            trang_thai='ACTIVE',
        ).aggregate(gia_thap_nhat=Min('gia_ban_le'))['gia_thap_nhat']
        return gia_thap_nhat if gia_thap_nhat is not None else 0

    # Hàm lấy link ảnh đại diện chính của sản phẩm
    def lay_anh_dai_dien(self):
        # Tìm ảnh được đánh dấu là ảnh chính (anh_chinh=True)
        anh = HinhAnhSanPham.objects.filter(san_pham=self, anh_chinh=True).first()
        if anh:
            return anh.duong_dan

        # Nếu không có ảnh chính, lấy ảnh đầu tiên theo mã hình ảnh
        anh_dau_tien = (
            HinhAnhSanPham.objects.filter(san_pham=self)
            .order_by("ma_hinh_anh")
            .first()
        )
        if anh_dau_tien:
            return anh_dau_tien.duong_dan

        # Nếu chưa có ảnh nào thì trả về ảnh mẫu mặc định
        return "https://placehold.co/400x300?text=Banh+Dua+Quy+Thu"


class DonViTinh(models.Model):
    ma_dvt = models.CharField(max_length=10, primary_key=True, verbose_name="Mã đơn vị tính")
    ten_dvt = models.CharField(max_length=50, unique=True, verbose_name="Tên đơn vị")
    ky_hieu = models.CharField(max_length=20, unique=True, verbose_name="Ký hiệu")

    class Meta:
        db_table = "DONVITINH"
        verbose_name = "Đơn vị tính"
        verbose_name_plural = "Đơn vị tính"
        ordering = ["ten_dvt"]

    def __str__(self):
        return self.ten_dvt


# ==========================================================
# 3. BẢNG BIẾN THỂ SẢN PHẨM (Hương vị, Quy cách, Giá, Mã vạch)
# ==========================================================
class BienTheSanPham(models.Model):
    # Khóa chính của biến thể (ví dụ: BT001)
    ma_bien_the = models.CharField(max_length=10, primary_key=True, verbose_name="Mã biến thể")

    # Biến thể này thuộc sản phẩm nào
    san_pham = models.ForeignKey(SanPham, on_delete=models.PROTECT, verbose_name="Sản phẩm")

    don_vi_tinh = models.ForeignKey(
        DonViTinh,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bien_the",
        verbose_name="Đơn vị tính",
    )

    # Hương vị: Truyền thống, Mè đen, Gừng (theo tài liệu M2-BR04)
    huong_vi = models.CharField(max_length=50, verbose_name="Hương vị")

    # Quy cách: 120g, 125g, 150g, 225g (theo tài liệu M2-BR04)
    quy_cach = models.CharField(max_length=20, verbose_name="Quy cách đóng gói")

    # Mã vạch duy nhất (theo tài liệu M2-BR06)
    barcode = models.CharField(max_length=50, unique=True, verbose_name="Mã vạch")

    # Giá bán lẻ
    gia_ban_le = models.DecimalField(max_digits=15, decimal_places=0, verbose_name="Giá bán lẻ")

    # Giá bán sỉ
    gia_ban_si = models.DecimalField(max_digits=15, decimal_places=0, blank=True, null=True, verbose_name="Giá bán sỉ")

    # Mức tham khảo, không phải điều kiện áp dụng giá cho đối tác bán sỉ.
    so_luong_toi_thieu_si = models.IntegerField(default=10, verbose_name="Mức số lượng đặt sỉ tham khảo")

    # Trạng thái: ACTIVE (còn bán) hoặc INACTIVE (ngừng bán)
    trang_thai = models.CharField(max_length=20, default='ACTIVE', verbose_name="Trạng thái")

    ngay_tao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'BIENTHE_SANPHAM'
        verbose_name = 'Biến thể sản phẩm'
        verbose_name_plural = 'Biến thể sản phẩm'
        ordering = ['ma_bien_the']
        constraints = [
            models.UniqueConstraint(
                fields=['san_pham', 'huong_vi', 'quy_cach'],
                name='uq_bienthe_sp_huongvi_quycach',
            ),
            models.CheckConstraint(
                condition=Q(gia_ban_le__gt=0),
                name='ck_bienthe_gia_le_duong',
            ),
            models.CheckConstraint(
                condition=Q(gia_ban_si__isnull=True) | Q(gia_ban_si__gt=0),
                name='ck_bienthe_gia_si_duong',
            ),
            models.CheckConstraint(
                condition=Q(gia_ban_si__isnull=True) | Q(gia_ban_si__lte=F('gia_ban_le')),
                name='ck_bienthe_gia_si_khong_hon_gia_le',
            ),
            models.CheckConstraint(
                condition=Q(so_luong_toi_thieu_si__gte=1),
                name='ck_bienthe_sl_si_duong',
            ),
        ]

    def __str__(self):
        return self.san_pham.ten_sp + " - " + self.huong_vi + " (" + self.quy_cach + ")"


class LichSuGiaBienThe(models.Model):
    san_pham = models.ForeignKey(
        SanPham,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lich_su_gia",
        verbose_name="Sản phẩm",
    )
    bien_the = models.ForeignKey(
        BienTheSanPham,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lich_su_gia",
        verbose_name="Biến thể",
    )
    ma_bien_the = models.CharField(max_length=10, verbose_name="Mã biến thể")
    ten_bien_the = models.CharField(max_length=120, verbose_name="Tên biến thể")
    nguoi_thuc_hien = models.ForeignKey(
        "customers.TaiKhoan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lich_su_gia_san_pham",
        verbose_name="Người cập nhật",
    )
    gia_ban_le_cu = models.DecimalField(max_digits=15, decimal_places=0)
    gia_ban_le_moi = models.DecimalField(max_digits=15, decimal_places=0)
    gia_ban_si_cu = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True)
    gia_ban_si_moi = models.DecimalField(max_digits=15, decimal_places=0, null=True, blank=True)
    so_luong_toi_thieu_si_cu = models.IntegerField()
    so_luong_toi_thieu_si_moi = models.IntegerField()
    thoi_gian = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian cập nhật")

    class Meta:
        db_table = "LICHSU_GIA_BIENTHE"
        ordering = ["-thoi_gian", "-pk"]
        verbose_name = "Lịch sử giá biến thể"
        verbose_name_plural = "Lịch sử giá biến thể"

    def __str__(self):
        return f"{self.ma_bien_the} - {self.thoi_gian:%Y-%m-%d %H:%M}"


# ==========================================================
# 4. BẢNG HÌNH ẢNH SẢN PHẨM
# ==========================================================
class HinhAnhSanPham(models.Model):
    ma_hinh_anh = models.CharField(max_length=10, primary_key=True, verbose_name="Mã hình ảnh")
    san_pham = models.ForeignKey(SanPham, on_delete=models.CASCADE, verbose_name="Sản phẩm")
    duong_dan = models.CharField(max_length=500, verbose_name="Đường dẫn ảnh")
    anh_chinh = models.BooleanField(default=False, verbose_name="Là ảnh đại diện chính")

    class Meta:
        db_table = 'HINHANH_SANPHAM'
        verbose_name = 'Hình ảnh sản phẩm'
        verbose_name_plural = 'Hình ảnh sản phẩm'