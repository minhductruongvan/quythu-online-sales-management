# File: backend/orders/models.py
# Module 3 – Giỏ hàng, đặt hàng, xử lý đơn hàng
# Phần 1/3: TinhThanh, PhuongThucThanhToan, GioHang, ChiTietGioHang
#
# Quy ước chung của M3 (đã chốt ngày 31/10/2026):
# - Khóa chính là mã chuỗi 10 ký tự, sinh trong services.py theo kiểu M1
#   (tiền tố + số thứ tự 3 chữ số, ví dụ CART001).
# - db_table trùng tên bảng trong database/ERD.py, giống cách M2 làm.
# - Tiền dùng DecimalField(max_digits=15, decimal_places=0), cùng kiểu với giá của M2.
# - Model của M1, M2 được tham chiếu bằng chuỗi "app.Model", không import trực tiếp.

from django.db import models
from django.utils import timezone


# ==========================================================
# 1. BẢNG TỈNH/THÀNH VÀ PHÍ GIAO HÀNG (TINH_THANH)
#    Phục vụ M3-BR05: phí giao hàng theo Tỉnh/Thành phố nhận hàng.
# ==========================================================
class TinhThanh(models.Model):
    class VungMien(models.TextChoices):
        BAC = "BAC", "Bắc"
        TRUNG = "TRUNG", "Trung"
        NAM = "NAM", "Nam"

    ma_tinh = models.CharField(
        max_length=10,
        primary_key=True,
        verbose_name="Mã tỉnh/thành",
    )

    ten_tinh = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Tên tỉnh/thành",
    )

    # M5 dùng để thống kê theo vùng
    vung_mien = models.CharField(
        max_length=10,
        choices=VungMien.choices,
        verbose_name="Vùng miền",
    )

    phi_van_chuyen = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        verbose_name="Phí giao hàng",
    )

    # Tắt thì khách không chọn được địa chỉ thuộc tỉnh này (M3-UC04 E3)
    dang_hoat_dong = models.BooleanField(
        default=True,
        verbose_name="Đang phục vụ giao hàng",
    )

    class Meta:
        db_table = "TINH_THANH"
        verbose_name = "Tỉnh/Thành và phí giao hàng"
        verbose_name_plural = "Tỉnh/Thành và phí giao hàng"
        ordering = ["ten_tinh"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(phi_van_chuyen__gte=0),
                name="ck_tinhthanh_phi_khong_am",
            ),
        ]

    def __str__(self):
        return self.ten_tinh


# ==========================================================
# 2. BẢNG PHƯƠNG THỨC THANH TOÁN (PHUONGTHUCTHANHTOAN)
#    Danh mục cố định: PT001 Chuyển khoản, PT002 COD (seed bằng migration).
# ==========================================================
class PhuongThucThanhToan(models.Model):
    # Hằng số mã, để services.py so sánh mà không gõ tay chuỗi "PT001"
    MA_CHUYEN_KHOAN = "PT001"
    MA_COD = "PT002"

    ma_pttt = models.CharField(
        max_length=10,
        primary_key=True,
        verbose_name="Mã phương thức",
    )

    ten_pttt = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Tên phương thức",
    )

    # Số tài khoản, ngân hàng, chủ tài khoản – dùng để dựng mã QR (M3-BR17)
    thong_tin_tai_khoan = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Thông tin tài khoản",
    )

    dang_kich_hoat = models.BooleanField(
        default=True,
        verbose_name="Đang kích hoạt",
    )

    ghi_chu_huong_dan = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Hướng dẫn thanh toán",
    )

    class Meta:
        db_table = "PHUONGTHUCTHANHTOAN"
        verbose_name = "Phương thức thanh toán"
        verbose_name_plural = "Phương thức thanh toán"

    def __str__(self):
        return self.ten_pttt


# ==========================================================
# 3. BẢNG GIỎ HÀNG (GIOHANG)
#    Mỗi khách hàng có đúng một giỏ (M3-BR03).
# ==========================================================
class GioHang(models.Model):
    ma_gio_hang = models.CharField(
        max_length=10,
        primary_key=True,
        verbose_name="Mã giỏ hàng",
    )

    # OneToOne = khóa ngoại kèm UNIQUE: một khách chỉ có một giỏ
    khach_hang = models.OneToOneField(
        "customers.KhachHang",
        on_delete=models.CASCADE,
        related_name="gio_hang",
        verbose_name="Khách hàng",
    )

    ngay_tao = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Ngày tạo",
    )

    # Tự cập nhật mỗi lần gọi save() – ghi nhận lần cập nhật giỏ gần nhất
    ngay_cap_nhat = models.DateTimeField(
        auto_now=True,
        verbose_name="Ngày cập nhật",
    )

    class Meta:
        db_table = "GIOHANG"
        verbose_name = "Giỏ hàng"
        verbose_name_plural = "Giỏ hàng"

    def __str__(self):
        return f"{self.ma_gio_hang} - {self.khach_hang_id}"


# ==========================================================
# 4. BẢNG CHI TIẾT GIỎ HÀNG (CT_GIOHANG)
#    Mỗi dòng gắn với đúng một biến thể; thêm lại cùng biến thể thì cộng dồn.
# ==========================================================
class ChiTietGioHang(models.Model):
    ma_ctgh = models.CharField(
        max_length=10,
        primary_key=True,
        verbose_name="Mã dòng giỏ hàng",
    )

    gio_hang = models.ForeignKey(
        GioHang,
        on_delete=models.CASCADE,
        related_name="chi_tiet",
        verbose_name="Giỏ hàng",
    )

    # CASCADE (không theo RESTRICT của ERD): giỏ chỉ là lựa chọn tạm thời,
    # không được chặn M2 xóa biến thể chỉ vì nó đang nằm trong giỏ ai đó.
    bien_the = models.ForeignKey(
        "products.BienTheSanPham",
        on_delete=models.CASCADE,
        related_name="dong_gio_hang",
        verbose_name="Biến thể sản phẩm",
    )

    so_luong = models.PositiveIntegerField(
        default=1,
        verbose_name="Số lượng",
    )

    ngay_cap_nhat = models.DateTimeField(
        auto_now=True,
        verbose_name="Ngày cập nhật",
    )

    class Meta:
        db_table = "CT_GIOHANG"
        verbose_name = "Chi tiết giỏ hàng"
        verbose_name_plural = "Chi tiết giỏ hàng"
        constraints = [
            # Tương đương CONSTRAINT UQ_CTGH UNIQUE (MaGioHang, MaBienTheSP)
            models.UniqueConstraint(
                fields=["gio_hang", "bien_the"],
                name="uq_ctgh_giohang_bienthe",
            ),
            # Tương đương CHECK (SoLuong > 0)
            models.CheckConstraint(
                condition=models.Q(so_luong__gt=0),
                name="ck_ctgh_soluong_duong",
            ),
        ]

    def __str__(self):
        return f"{self.ma_ctgh} - {self.bien_the_id} x {self.so_luong}"


# ==========================================================
# 5. CÁC BỘ GIÁ TRỊ TRẠNG THÁI (dùng chung cho DonHang, LichSu, GiaoDich)
#    Lưu mã không dấu, hiển thị nhãn tiếng Việt.
# ==========================================================
class TrangThaiDonHang(models.TextChoices):
    CHO_XAC_NHAN = "CHO_XAC_NHAN", "Chờ xác nhận"
    DA_XAC_NHAN = "DA_XAC_NHAN", "Đã xác nhận"
    CHO_THANH_TOAN = "CHO_THANH_TOAN", "Chờ thanh toán"
    DANG_CHUAN_BI = "DANG_CHUAN_BI", "Đang chuẩn bị hàng"
    CHO_BO_SUNG = "CHO_BO_SUNG", "Chờ bổ sung hàng"
    SAN_SANG_GIAO = "SAN_SANG_GIAO", "Sẵn sàng giao"
    DANG_GIAO = "DANG_GIAO", "Đang giao"
    GIAO_THANH_CONG = "GIAO_THANH_CONG", "Giao thành công"
    HOAN_THANH = "HOAN_THANH", "Hoàn thành"
    DA_HUY = "DA_HUY", "Đã hủy"


class TrangThaiThanhToan(models.TextChoices):
    CHUA_THANH_TOAN = "CHUA_THANH_TOAN", "Chưa thanh toán"
    DA_THANH_TOAN = "DA_THANH_TOAN", "Đã thanh toán"
    THAT_BAI = "THAT_BAI", "Thanh toán thất bại"


# ==========================================================
# 6. BẢNG ĐƠN HÀNG (DONHANG)
#    Bản ghi gốc duy nhất của giao dịch bán (M3-BR23).
#    M1 đọc lịch sử mua, M4 ghi trạng thái hậu mãi, M5 thống kê.
# ==========================================================
class DonHang(models.Model):
    ma_dh = models.CharField(max_length=10, primary_key=True, verbose_name="Mã đơn hàng")

    # ---------- Ai đặt, loại khách chốt tại lúc đặt (M3-BR02) ----------
    khach_hang = models.ForeignKey(
        "customers.KhachHang",
        on_delete=models.PROTECT,
        related_name="don_hang",
        verbose_name="Khách hàng",
    )
    loai_khach_hang_ap_dung = models.ForeignKey(
        "customers.LoaiKhachHang",
        on_delete=models.PROTECT,
        related_name="don_hang",
        verbose_name="Loại khách áp dụng",
    )

    # ---------- Bản sao thông tin nhận hàng (M3-BR08) ----------
    ho_ten_nguoi_nhan = models.CharField(max_length=100, verbose_name="Họ tên người nhận")
    sdt_nguoi_nhan = models.CharField(max_length=15, verbose_name="SĐT người nhận")
    dia_chi_giao_hang = models.CharField(max_length=500, verbose_name="Địa chỉ giao hàng")
    tinh_thanh = models.ForeignKey(
        TinhThanh,
        on_delete=models.PROTECT,
        related_name="don_hang",
        verbose_name="Tỉnh/Thành nhận hàng",
    )

    # ---------- Tiền, chốt tại lúc đặt (M3-BR06, M3-BR07) ----------
    tong_tien_hang = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name="Tổng tiền hàng")
    phi_van_chuyen = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name="Phí giao hàng")
    tong_thanh_toan = models.DecimalField(max_digits=15, decimal_places=0, default=0, verbose_name="Tổng thanh toán")

    # ---------- Thanh toán ----------
    phuong_thuc_thanh_toan = models.ForeignKey(
        PhuongThucThanhToan,
        on_delete=models.PROTECT,
        related_name="don_hang",
        verbose_name="Phương thức thanh toán",
    )
    trang_thai_thanh_toan = models.CharField(
        max_length=20,
        choices=TrangThaiThanhToan.choices,
        default=TrangThaiThanhToan.CHUA_THANH_TOAN,
        verbose_name="Trạng thái thanh toán",
    )

    # ---------- Trạng thái xử lý (M3-BR14) ----------
    trang_thai = models.CharField(
        max_length=30,
        choices=TrangThaiDonHang.choices,
        default=TrangThaiDonHang.CHO_XAC_NHAN,
        verbose_name="Trạng thái đơn",
    )
    # M4 ghi; M3 chỉ đọc và hiển thị cạnh trạng thái xử lý (M3-BR22, M3-BR23)
    trang_thai_hau_mai = models.CharField(max_length=30, null=True, blank=True, verbose_name="Trạng thái hậu mãi")
    ghi_chu = models.CharField(max_length=255, null=True, blank=True, verbose_name="Ghi chú")

    # ---------- Các mốc thời gian (M3-BR15) ----------
    # default=timezone.now thay vì auto_now_add: cho phép tạo đơn mẫu ở ngày quá khứ
    ngay_dat = models.DateTimeField(default=timezone.now, verbose_name="Ngày đặt")
    nhan_vien_xac_nhan = models.ForeignKey(
        "customers.NhanVien",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="don_hang_da_xac_nhan",
        verbose_name="Nhân viên xác nhận",
    )
    thoi_diem_xac_nhan = models.DateTimeField(null=True, blank=True, verbose_name="Thời điểm xác nhận")
    thoi_diem_bat_dau_chuan_bi = models.DateTimeField(null=True, blank=True, verbose_name="Bắt đầu chuẩn bị")

    # Xử lý thiếu hàng (M3-UC10): hẹn ngày và nhớ bước để quay lại
    thoi_diem_hen_cung_cap = models.DateTimeField(null=True, blank=True, verbose_name="Hẹn cung cấp")
    trang_thai_truoc_cho_bo_sung = models.CharField(
        max_length=30,
        choices=TrangThaiDonHang.choices,
        null=True,
        blank=True,
        verbose_name="Trạng thái trước khi chờ bổ sung",
    )

    so_lan_giao_lai = models.PositiveSmallIntegerField(default=0, verbose_name="Số lần giao lại")
    thoi_diem_ban_giao = models.DateTimeField(null=True, blank=True, verbose_name="Thời điểm bàn giao")
    thoi_diem_giao_thanh_cong = models.DateTimeField(null=True, blank=True, verbose_name="Giao thành công")
    # Có giá trị = cửa sổ đổi/trả 7 ngày đã đóng (M3-BR21)
    thoi_diem_xac_nhan_nhan_hang = models.DateTimeField(null=True, blank=True, verbose_name="Xác nhận nhận hàng")
    xac_nhan_tu_dong = models.BooleanField(default=False, verbose_name="Hệ thống tự xác nhận")
    thoi_diem_hoan_thanh = models.DateTimeField(null=True, blank=True, verbose_name="Thời điểm hoàn thành")

    class Meta:
        db_table = "DONHANG"
        verbose_name = "Đơn hàng"
        verbose_name_plural = "Đơn hàng"
        ordering = ["-ngay_dat"]  # mới nhất lên trước (M3-UC05, M3-UC07)
        constraints = [
            # CHECK (TongThanhToan = TongTienHang + PhiVanChuyen)
            models.CheckConstraint(
                condition=models.Q(tong_thanh_toan=models.F("tong_tien_hang") + models.F("phi_van_chuyen")),
                name="ck_donhang_tong_thanh_toan",
            ),
            models.CheckConstraint(
                condition=models.Q(tong_tien_hang__gte=0) & models.Q(phi_van_chuyen__gte=0),
                name="ck_donhang_tien_khong_am",
            ),
            models.CheckConstraint(
                condition=models.Q(so_lan_giao_lai__lte=2),
                name="ck_donhang_so_lan_giao_lai",
            ),
            # CHECK (TrangThaiDonHang IN (...)): chặn cả khi code ghi sai giá trị
            models.CheckConstraint(
                condition=models.Q(trang_thai__in=TrangThaiDonHang.values),
                name="ck_donhang_trang_thai_hop_le",
            ),
            models.CheckConstraint(
                condition=models.Q(trang_thai_thanh_toan__in=TrangThaiThanhToan.values),
                name="ck_donhang_tt_thanh_toan_hop_le",
            ),
        ]

    def __str__(self):
        return f"{self.ma_dh} - {self.get_trang_thai_display()}"


# ==========================================================
# 7. CÁC BỘ GIÁ TRỊ DÙNG CHO PHẦN 3
#    Đặt ở cấp module vì class Meta bên trong model không nhìn thấy
#    các tên khai báo trong thân class model (xem giải thích).
# ==========================================================
class LoaiGia(models.TextChoices):
    GIA_LE = "GIA_LE", "Giá lẻ"
    GIA_SI = "GIA_SI", "Giá sỉ"


# Kết quả nhân viên kiểm tra hàng thực tế (M3-UC09)
class KetQuaKiemTra(models.TextChoices):
    CHUA_KIEM_TRA = "CHUA_KIEM_TRA", "Chưa kiểm tra"
    DU = "DU", "Đủ hàng"
    THIEU = "THIEU", "Thiếu hàng"


class TacNhan(models.TextChoices):
    KHACH_HANG = "KHACH_HANG", "Khách hàng"
    HE_THONG = "HE_THONG", "Hệ thống"
    NHAN_VIEN = "NHAN_VIEN", "Nhân viên"


# ==========================================================
# 8. BẢNG CHI TIẾT ĐƠN HÀNG (CT_DONHANG)
#    Giá và loại giá được chốt tại lúc đặt (M3-BR04, M3-BR07).
# ==========================================================
class ChiTietDonHang(models.Model):
    ma_ctdh = models.CharField(max_length=10, primary_key=True, verbose_name="Mã dòng đơn")
    don_hang = models.ForeignKey(
        DonHang,
        on_delete=models.CASCADE,
        related_name="chi_tiet",
        verbose_name="Đơn hàng",
    )
    # PROTECT: biến thể đã bán thì không xóa được (M2-BR13 bảo toàn lịch sử)
    bien_the = models.ForeignKey(
        "products.BienTheSanPham",
        on_delete=models.PROTECT,
        related_name="dong_don_hang",
        verbose_name="Biến thể sản phẩm",
    )
    so_luong = models.PositiveIntegerField(verbose_name="Số lượng")
    loai_gia_ap_dung = models.CharField(max_length=10, choices=LoaiGia.choices, verbose_name="Loại giá áp dụng")
    don_gia = models.DecimalField(max_digits=15, decimal_places=0, verbose_name="Đơn giá")
    thanh_tien = models.DecimalField(max_digits=15, decimal_places=0, verbose_name="Thành tiền")
    ket_qua_kiem_tra = models.CharField(
        max_length=20,
        choices=KetQuaKiemTra.choices,
        default=KetQuaKiemTra.CHUA_KIEM_TRA,
        verbose_name="Kết quả kiểm tra hàng",
    )
    so_luong_thieu = models.PositiveIntegerField(default=0, verbose_name="Số lượng thiếu")

    class Meta:
        db_table = "CT_DONHANG"
        verbose_name = "Chi tiết đơn hàng"
        verbose_name_plural = "Chi tiết đơn hàng"
        constraints = [
            models.UniqueConstraint(fields=["don_hang", "bien_the"], name="uq_ctdh_donhang_bienthe"),
            models.CheckConstraint(condition=models.Q(so_luong__gt=0), name="ck_ctdh_soluong_duong"),
            models.CheckConstraint(condition=models.Q(don_gia__gte=0), name="ck_ctdh_dongia_khong_am"),
            # CHECK (ThanhTien = SoLuong * DonGia)
            models.CheckConstraint(
                condition=models.Q(thanh_tien=models.F("so_luong") * models.F("don_gia")),
                name="ck_ctdh_thanh_tien",
            ),
            models.CheckConstraint(
                condition=models.Q(so_luong_thieu__lte=models.F("so_luong")),
                name="ck_ctdh_thieu_khong_qua_so_luong",
            ),
            models.CheckConstraint(
                condition=models.Q(loai_gia_ap_dung__in=LoaiGia.values),
                name="ck_ctdh_loai_gia_hop_le",
            ),
        ]

    def __str__(self):
        return f"{self.ma_ctdh} - {self.bien_the_id} x {self.so_luong}"


# ==========================================================
# 9. BẢNG LỊCH SỬ TRẠNG THÁI ĐƠN HÀNG (LICHSUTRANGTHAI_DH)
#    Mỗi lần đổi trạng thái ghi một dòng; không sửa, không xóa (M3-BR15).
# ==========================================================
class LichSuTrangThaiDonHang(models.Model):
    ma_lstt = models.CharField(max_length=10, primary_key=True, verbose_name="Mã lịch sử")
    don_hang = models.ForeignKey(
        DonHang,
        on_delete=models.CASCADE,
        related_name="lich_su_trang_thai",
        verbose_name="Đơn hàng",
    )
    # Dòng đầu tiên (lúc đặt hàng) không có trạng thái cũ
    trang_thai_cu = models.CharField(
        max_length=30,
        choices=TrangThaiDonHang.choices,
        null=True,
        blank=True,
        verbose_name="Trạng thái cũ",
    )
    trang_thai = models.CharField(max_length=30, choices=TrangThaiDonHang.choices, verbose_name="Trạng thái mới")
    thoi_diem = models.DateTimeField(default=timezone.now, verbose_name="Thời điểm")
    tac_nhan = models.CharField(max_length=20, choices=TacNhan.choices, verbose_name="Tác nhân")
    nhan_vien = models.ForeignKey(
        "customers.NhanVien",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lich_su_don_hang",
        verbose_name="Nhân viên thao tác",
    )
    ghi_chu = models.CharField(max_length=255, null=True, blank=True, verbose_name="Ghi chú")

    class Meta:
        db_table = "LICHSUTRANGTHAI_DH"
        verbose_name = "Lịch sử trạng thái đơn"
        verbose_name_plural = "Lịch sử trạng thái đơn"
        ordering = ["thoi_diem"]  # cũ đến mới, đọc như một dòng thời gian
        constraints = [
            models.CheckConstraint(
                condition=models.Q(trang_thai__in=TrangThaiDonHang.values),
                name="ck_lstt_trang_thai_hop_le",
            ),
            models.CheckConstraint(
                condition=models.Q(tac_nhan__in=TacNhan.values),
                name="ck_lstt_tac_nhan_hop_le",
            ),
        ]

    def __str__(self):
        return f"{self.don_hang_id}: {self.trang_thai_cu} -> {self.trang_thai}"


# ==========================================================
# 10. BẢNG GIAO DỊCH THANH TOÁN (GIAODICH_THANHTOAN)
#     Tạo cùng lúc với đơn (M3-BR10). Chuyển khoản do cổng giả lập ghi nhận,
#     COD do nhân viên ghi nhận sau khi giao. M4 chỉ đọc để hoàn tiền.
# ==========================================================
class GiaoDichThanhToan(models.Model):
    ma_giao_dich = models.CharField(max_length=10, primary_key=True, verbose_name="Mã giao dịch")
    # ForeignKey (không phải OneToOne) để còn lưu được bản đính chính (M3-UC11 A1)
    don_hang = models.ForeignKey(
        DonHang,
        on_delete=models.CASCADE,
        related_name="giao_dich_thanh_toan",
        verbose_name="Đơn hàng",
    )
    phuong_thuc = models.ForeignKey(
        PhuongThucThanhToan,
        on_delete=models.PROTECT,
        related_name="giao_dich",
        verbose_name="Phương thức thanh toán",
    )
    so_tien_phai_thu = models.DecimalField(max_digits=15, decimal_places=0, verbose_name="Số tiền phải thu")
    so_tien_thuc_nhan = models.DecimalField(
        max_digits=15, decimal_places=0, null=True, blank=True, verbose_name="Số tiền thực nhận"
    )
    trang_thai = models.CharField(
        max_length=20,
        choices=TrangThaiThanhToan.choices,
        default=TrangThaiThanhToan.CHUA_THANH_TOAN,
        verbose_name="Trạng thái giao dịch",
    )
    # Cổng giả lập sinh mã này; COD để trống
    ma_giao_dich_ngan_hang = models.CharField(max_length=50, null=True, blank=True, verbose_name="Mã GD ngân hàng")
    thoi_diem_tao = models.DateTimeField(default=timezone.now, verbose_name="Thời điểm tạo")
    thoi_diem_thanh_toan = models.DateTimeField(null=True, blank=True, verbose_name="Thời điểm thanh toán")
    # Để trống khi cổng giả lập ghi nhận (tác nhân là Hệ thống)
    nhan_vien_ghi_nhan = models.ForeignKey(
        "customers.NhanVien",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="giao_dich_da_ghi_nhan",
        verbose_name="Nhân viên ghi nhận",
    )
    ghi_chu = models.CharField(max_length=255, null=True, blank=True, verbose_name="Ghi chú")

    class Meta:
        db_table = "GIAODICH_THANHTOAN"
        verbose_name = "Giao dịch thanh toán"
        verbose_name_plural = "Giao dịch thanh toán"
        ordering = ["thoi_diem_tao"]
        constraints = [
            models.CheckConstraint(condition=models.Q(so_tien_phai_thu__gte=0), name="ck_gd_phai_thu_khong_am"),
            # NULL hoặc >= 0
            models.CheckConstraint(
                condition=models.Q(so_tien_thuc_nhan__isnull=True) | models.Q(so_tien_thuc_nhan__gte=0),
                name="ck_gd_thuc_nhan_khong_am",
            ),
            models.CheckConstraint(
                condition=models.Q(trang_thai__in=TrangThaiThanhToan.values),
                name="ck_gd_trang_thai_hop_le",
            ),
        ]

    def __str__(self):
        return f"{self.ma_giao_dich} - {self.don_hang_id} - {self.get_trang_thai_display()}"