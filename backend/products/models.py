from django.db import models


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
    danh_muc = models.ForeignKey(DanhMucSanPham, on_delete=models.CASCADE, verbose_name="Danh mục")

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
    # Viết bằng vòng lặp for cơ bản để bạn dễ hiểu nhất:
    def lay_gia_thap_nhat(self):
        # 1. Tìm tất cả biến thể của sản phẩm này có trạng thái ACTIVE
        danh_sach_bien_the = BienTheSanPham.objects.filter(san_pham=self, trang_thai='ACTIVE')

        # Nếu chưa có biến thể nào thì trả về 0 đồng
        if len(danh_sach_bien_the) == 0:
            return 0

        # Lấy giá của biến thể đầu tiên làm giá nhỏ nhất tạm thời
        gia_nho_nhat = danh_sach_bien_the[0].gia_ban_le

        # Duyệt qua từng biến thể để tìm giá nhỏ nhất
        for bien_the in danh_sach_bien_the:
            if bien_the.gia_ban_le < gia_nho_nhat:
                gia_nho_nhat = bien_the.gia_ban_le

        return gia_nho_nhat

    # Hàm lấy link ảnh đại diện chính của sản phẩm
    def lay_anh_dai_dien(self):
        # Tìm ảnh được đánh dấu là ảnh chính (anh_chinh=True)
        anh = HinhAnhSanPham.objects.filter(san_pham=self, anh_chinh=True).first()
        if anh:
            return anh.duong_dan

        # Nếu không có ảnh chính, lấy ảnh bất kỳ đầu tiên
        anh_dau_tien = HinhAnhSanPham.objects.filter(san_pham=self).first()
        if anh_dau_tien:
            return anh_dau_tien.duong_dan

        # Nếu chưa có ảnh nào thì trả về ảnh mẫu mặc định
        return "https://placehold.co/400x300?text=Banh+Dua+Quy+Thu"


# ==========================================================
# 3. BẢNG BIẾN THỂ SẢN PHẨM (Hương vị, Quy cách, Giá, Mã vạch)
# ==========================================================
class BienTheSanPham(models.Model):
    # Khóa chính của biến thể (ví dụ: BT001)
    ma_bien_the = models.CharField(max_length=10, primary_key=True, verbose_name="Mã biến thể")

    # Biến thể này thuộc sản phẩm nào
    san_pham = models.ForeignKey(SanPham, on_delete=models.CASCADE, verbose_name="Sản phẩm")

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

    # Số lượng tối thiểu để được giá sỉ
    so_luong_toi_thieu_si = models.IntegerField(default=10, verbose_name="Số lượng tối thiểu hưởng giá sỉ")

    # Trạng thái: ACTIVE (còn bán) hoặc INACTIVE (ngừng bán)
    trang_thai = models.CharField(max_length=20, default='ACTIVE', verbose_name="Trạng thái")

    ngay_tao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'BIENTHE_SANPHAM'
        verbose_name = 'Biến thể sản phẩm'
        verbose_name_plural = 'Biến thể sản phẩm'

    def __str__(self):
        return self.san_pham.ten_sp + " - " + self.huong_vi + " (" + self.quy_cach + ")"


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