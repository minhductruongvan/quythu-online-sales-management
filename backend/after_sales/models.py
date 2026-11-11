# File: backend/after_sales/models.py
# Module 4 – Quản lý hậu mãi và xử lý phát sinh (hủy đơn, giao không thành công,
# đổi/trả, hoàn tiền, danh mục nguyên nhân, timeline).
#
# Quy ước (theo M1, M3):
# - Khóa chính là mã chuỗi tối đa 10 ký tự, sinh trong services.py (tiền tố + số thứ tự).
# - Model của M1, M2, M3 được tham chiếu bằng chuỗi "app.Model", không import trực tiếp.
# - M4 KHÔNG tạo model đơn hàng. Mọi bảng dưới đây đều có khóa ngoại về DonHang của M3.
# - M4 chỉ ghi lên đơn gốc hai thứ: DonHang.trang_thai_hau_mai (M3 đã chừa cột này)
#   và trạng thái "Đã hủy" thông qua hàm huy_don của M3 (xem services.py).
# - Tiền dùng DecimalField(max_digits=15, decimal_places=0), cùng kiểu với M2, M3.

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


# ==========================================================
# 1. CÁC BỘ GIÁ TRỊ DÙNG CHUNG
# ==========================================================
class LoaiXuLy(models.TextChoices):
    """M4-BR10: danh mục nguyên nhân thuộc ba loại xử lý."""
    HUY_DON = "HUY_DON", "Hủy đơn"
    GIAO_THAT_BAI = "GIAO_THAT_BAI", "Giao hàng không thành công"
    DOI_TRA = "DOI_TRA", "Đổi/trả hàng"


class LoaiYeuCau(models.TextChoices):
    """Loại yêu cầu hậu mãi hiển thị trong danh sách lịch sử và timeline (M4-UC09)."""
    HUY_DON = "HUY_DON", "Hủy đơn"
    GIAO_THAT_BAI = "GIAO_THAT_BAI", "Giao hàng không thành công"
    DOI_TRA = "DOI_TRA", "Đổi/trả hàng"
    HOAN_TIEN = "HOAN_TIEN", "Hoàn tiền"


# ==========================================================
# 2. DANH MỤC NGUYÊN NHÂN (M4-UC07, M4-BR02, M4-BR10)
# ==========================================================
class NguyenNhan(models.Model):
    ma_nguyen_nhan = models.CharField(max_length=10, primary_key=True, verbose_name="Mã nguyên nhân")
    loai_xu_ly = models.CharField(max_length=20, choices=LoaiXuLy.choices, verbose_name="Loại xử lý")
    ten_nguyen_nhan = models.CharField(max_length=100, verbose_name="Tên nguyên nhân")
    mo_ta = models.CharField(max_length=255, null=True, blank=True, verbose_name="Mô tả")
    thu_tu_hien_thi = models.PositiveSmallIntegerField(default=0, verbose_name="Thứ tự hiển thị")
    # UC07 Input: thiết lập nguyên nhân có bắt buộc ảnh / ghi chú không
    bat_buoc_anh = models.BooleanField(default=False, verbose_name="Bắt buộc ảnh minh chứng")
    bat_buoc_ghi_chu = models.BooleanField(default=False, verbose_name="Bắt buộc ghi chú")
    # M4-BR07: lỗi do cửa hàng / nhà sản xuất (hàng lỗi, hư hỏng, giao sai) -> cửa hàng chịu phí hai chiều
    loi_do_cua_hang = models.BooleanField(default=False, verbose_name="Lỗi do cửa hàng/nhà sản xuất")
    dang_ap_dung = models.BooleanField(default=True, verbose_name="Đang áp dụng")
    ngay_tao = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    ngay_cap_nhat = models.DateTimeField(auto_now=True, verbose_name="Ngày cập nhật")

    class Meta:
        db_table = "HM_NGUYENNHAN"
        verbose_name = "Nguyên nhân hậu mãi"
        verbose_name_plural = "Nguyên nhân hậu mãi"
        ordering = ["loai_xu_ly", "thu_tu_hien_thi", "ma_nguyen_nhan"]
        constraints = [
            # M4-BR10: tên không trùng trong cùng loại xử lý
            models.UniqueConstraint(fields=["loai_xu_ly", "ten_nguyen_nhan"], name="uq_hm_nn_loai_ten"),
            models.CheckConstraint(
                condition=models.Q(loai_xu_ly__in=LoaiXuLy.values), name="ck_hm_nn_loai_hop_le"
            ),
        ]

    def __str__(self):
        return f"{self.ma_nguyen_nhan} - {self.ten_nguyen_nhan}"


class LichSuNguyenNhan(models.Model):
    """M4-BR13: thay đổi danh mục nguyên nhân được lưu lịch sử (người sửa, thời điểm, giá trị cũ/mới)."""

    class HanhDong(models.TextChoices):
        THEM = "THEM", "Thêm mới"
        SUA = "SUA", "Sửa"
        NGUNG = "NGUNG", "Ngưng sử dụng"
        KICH_HOAT = "KICH_HOAT", "Kích hoạt"
        XOA = "XOA", "Xóa"

    ma_lich_su = models.CharField(max_length=10, primary_key=True, verbose_name="Mã lịch sử")
    # Không dùng khóa ngoại: nguyên nhân chưa từng dùng có thể bị xóa (UC07 A2), lịch sử vẫn phải còn
    ma_nguyen_nhan = models.CharField(max_length=10, db_index=True, verbose_name="Mã nguyên nhân")
    hanh_dong = models.CharField(max_length=15, choices=HanhDong.choices, verbose_name="Hành động")
    nguoi_thuc_hien = models.ForeignKey(
        "customers.TaiKhoan", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="lich_su_nguyen_nhan", verbose_name="Người thực hiện",
    )
    thoi_diem = models.DateTimeField(default=timezone.now, verbose_name="Thời điểm")
    gia_tri_cu = models.TextField(null=True, blank=True, verbose_name="Giá trị cũ")
    gia_tri_moi = models.TextField(null=True, blank=True, verbose_name="Giá trị mới")

    class Meta:
        db_table = "HM_LICHSU_NGUYENNHAN"
        verbose_name = "Lịch sử danh mục nguyên nhân"
        verbose_name_plural = "Lịch sử danh mục nguyên nhân"
        ordering = ["-thoi_diem", "-ma_lich_su"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Lịch sử danh mục nguyên nhân không được sửa.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Lịch sử danh mục nguyên nhân không được xóa.")


# ==========================================================
# 3. YÊU CẦU HỦY ĐƠN (M4-UC01, M4-UC02)
# ==========================================================
class TrangThaiYeuCauHuy(models.TextChoices):
    CHO_XU_LY = "CHO_XU_LY", "Chờ xử lý"
    DA_DUYET = "DA_DUYET", "Đã duyệt"
    TU_CHOI = "TU_CHOI", "Từ chối"
    THU_HOI = "THU_HOI", "Đã thu hồi"


class YeuCauHuy(models.Model):
    ma_yc_huy = models.CharField(max_length=10, primary_key=True, verbose_name="Mã yêu cầu hủy")
    don_hang = models.ForeignKey(
        "orders.DonHang", on_delete=models.PROTECT, related_name="yeu_cau_huy", verbose_name="Đơn hàng"
    )
    nguyen_nhan = models.ForeignKey(
        NguyenNhan, on_delete=models.PROTECT, related_name="yeu_cau_huy", verbose_name="Nguyên nhân"
    )
    ghi_chu_khach = models.CharField(max_length=500, null=True, blank=True, verbose_name="Ghi chú của khách")
    thong_tin_tai_khoan_hoan = models.TextField(null=True, blank=True, verbose_name="Tài khoản hoàn tiền (mã hóa)")
    trang_thai = models.CharField(
        max_length=20, choices=TrangThaiYeuCauHuy.choices, default=TrangThaiYeuCauHuy.CHO_XU_LY,
        verbose_name="Trạng thái",
    )
    # Giá trị DonHang.trang_thai_hau_mai trước khi gửi yêu cầu, để trả đơn về khi từ chối/thu hồi (BR15)
    hau_mai_truoc = models.CharField(max_length=30, null=True, blank=True, verbose_name="Hậu mãi trước đó")
    thoi_diem_gui = models.DateTimeField(default=timezone.now, verbose_name="Thời điểm gửi")
    nhan_vien_xu_ly = models.ForeignKey(
        "customers.NhanVien", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="yeu_cau_huy_da_xu_ly", verbose_name="Nhân viên xử lý",
    )
    thoi_diem_xu_ly = models.DateTimeField(null=True, blank=True, verbose_name="Thời điểm xử lý")
    ly_do_tu_choi = models.CharField(max_length=255, null=True, blank=True, verbose_name="Lý do từ chối")
    ghi_chu_noi_bo = models.CharField(max_length=255, null=True, blank=True, verbose_name="Ghi chú nội bộ")

    class Meta:
        db_table = "HM_YEUCAU_HUY"
        verbose_name = "Yêu cầu hủy đơn"
        verbose_name_plural = "Yêu cầu hủy đơn"
        ordering = ["thoi_diem_gui", "ma_yc_huy"]  # cũ nhất trước (UC02 bước 1)
        constraints = [
            # M4-BR03: mỗi đơn chỉ có tối đa một yêu cầu hủy "Chờ xử lý". Ràng buộc ở CSDL
            # nên bấm gửi nhiều lần liên tiếp cũng không tạo được yêu cầu trùng.
            models.UniqueConstraint(
                fields=["don_hang"],
                condition=models.Q(trang_thai="CHO_XU_LY"),
                name="uq_hm_huy_mot_cho_xu_ly",
            ),
            models.CheckConstraint(
                condition=models.Q(trang_thai__in=TrangThaiYeuCauHuy.values), name="ck_hm_huy_trang_thai"
            ),
        ]

    def __str__(self):
        return f"{self.ma_yc_huy} - {self.don_hang_id} - {self.get_trang_thai_display()}"


# ==========================================================
# 4. GIAO HÀNG KHÔNG THÀNH CÔNG (M4-UC03)
#    Mỗi dòng là một lần giao thất bại cùng cách xử lý đã chọn.
#    Bảng GiaoHang của M3 giữ các lần giao; bảng này giữ phần xử lý của M4.
# ==========================================================
class HuongXuLyGiao(models.TextChoices):
    GIAO_LAI = "GIAO_LAI", "Giao lại"
    DOI_THONG_TIN_GIAO_LAI = "DOI_THONG_TIN_GIAO_LAI", "Cập nhật thông tin giao hàng rồi giao lại"
    HOAN_VE_KHO = "HOAN_VE_KHO", "Hoàn hàng về kho"


class BenChiuPhi(models.TextChoices):
    CUA_HANG = "CUA_HANG", "Cửa hàng"
    KHACH_HANG = "KHACH_HANG", "Khách hàng"


class XuLyGiaoThatBai(models.Model):
    ma_xu_ly = models.CharField(max_length=10, primary_key=True, verbose_name="Mã xử lý")
    don_hang = models.ForeignKey(
        "orders.DonHang", on_delete=models.PROTECT, related_name="xu_ly_giao_that_bai", verbose_name="Đơn hàng"
    )
    giao_hang = models.OneToOneField(
        "orders.GiaoHang", on_delete=models.PROTECT, related_name="xu_ly_that_bai",
        verbose_name="Lần giao thất bại (M3)",
    )
    lan_giao = models.PositiveSmallIntegerField(verbose_name="Lần giao thất bại")
    nguyen_nhan = models.ForeignKey(
        NguyenNhan, on_delete=models.PROTECT, related_name="xu_ly_giao_that_bai", verbose_name="Nguyên nhân"
    )
    ghi_chu = models.CharField(max_length=500, null=True, blank=True, verbose_name="Ghi chú")
    phan_hoi_khach = models.CharField(max_length=500, null=True, blank=True, verbose_name="Phản hồi của khách")
    huong_xu_ly = models.CharField(max_length=30, choices=HuongXuLyGiao.choices, verbose_name="Hướng xử lý")
    ben_chiu_phi = models.CharField(
        max_length=15, choices=BenChiuPhi.choices, default=BenChiuPhi.CUA_HANG, verbose_name="Bên chịu phí"
    )
    ngay_giao_lai_du_kien = models.DateField(null=True, blank=True, verbose_name="Ngày giao lại dự kiến")
    # Thông tin giao mới được lưu tại M4; M4 không ghi đè địa chỉ trên đơn gốc của M3
    ten_nguoi_nhan_moi = models.CharField(max_length=100, null=True, blank=True)
    sdt_nguoi_nhan_moi = models.CharField(max_length=15, null=True, blank=True)
    dia_chi_giao_moi = models.CharField(max_length=500, null=True, blank=True)
    dia_chi_kho = models.CharField(max_length=500, null=True, blank=True, verbose_name="Địa chỉ kho hoàn về")
    nhan_vien = models.ForeignKey(
        "customers.NhanVien", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="xu_ly_giao_that_bai", verbose_name="Nhân viên xử lý",
    )
    thoi_diem = models.DateTimeField(default=timezone.now, verbose_name="Thời điểm ghi nhận")
    # UC03 A1: xác nhận hàng đã về kho
    da_nhap_kho = models.BooleanField(default=False, verbose_name="Đã nhập kho")
    thoi_diem_nhap_kho = models.DateTimeField(null=True, blank=True, verbose_name="Thời điểm nhập kho")
    ghi_chu_noi_bo = models.CharField(max_length=255, null=True, blank=True, verbose_name="Ghi chú nội bộ")

    class Meta:
        db_table = "HM_XULY_GIAOTHATBAI"
        verbose_name = "Xử lý giao hàng không thành công"
        verbose_name_plural = "Xử lý giao hàng không thành công"
        ordering = ["don_hang", "lan_giao"]
        constraints = [
            models.UniqueConstraint(fields=["don_hang", "lan_giao"], name="uq_hm_gtb_don_lan"),
            models.CheckConstraint(
                condition=models.Q(huong_xu_ly__in=HuongXuLyGiao.values), name="ck_hm_gtb_huong_hop_le"
            ),
        ]

    def __str__(self):
        return f"{self.ma_xu_ly} - {self.don_hang_id} - lần {self.lan_giao}"


# ==========================================================
# 5. YÊU CẦU ĐỔI/TRẢ HÀNG (M4-UC04, M4-UC05)
# ==========================================================
class HinhThucDoiTra(models.TextChoices):
    DOI = "DOI", "Đổi sản phẩm"
    TRA = "TRA", "Trả hàng hoàn tiền"


class TrangThaiDoiTra(models.TextChoices):
    CHO_XU_LY = "CHO_XU_LY", "Chờ xử lý"
    DA_DUYET = "DA_DUYET", "Đã duyệt"
    DANG_CHO_NHAN_HANG = "DANG_CHO_NHAN_HANG", "Đang chờ nhận hàng"
    DA_NHAN_HANG = "DA_NHAN_HANG", "Đã nhận hàng"
    HOAN_TAT = "HOAN_TAT", "Hoàn tất"
    TU_CHOI = "TU_CHOI", "Từ chối"
    THU_HOI = "THU_HOI", "Đã thu hồi"
    HET_HAN_GUI_HANG = "HET_HAN_GUI_HANG", "Hết hạn gửi hàng"  # M4-BR16


# Các trạng thái còn "giữ" số lượng của dòng sản phẩm (M4-BR06): chưa bị đóng bằng từ chối/thu hồi/hết hạn
TRANG_THAI_DOI_TRA_GIU_SO_LUONG = [
    TrangThaiDoiTra.CHO_XU_LY, TrangThaiDoiTra.DA_DUYET, TrangThaiDoiTra.DANG_CHO_NHAN_HANG,
    TrangThaiDoiTra.DA_NHAN_HANG, TrangThaiDoiTra.HOAN_TAT,
]


class YeuCauDoiTra(models.Model):
    ma_yc_doi_tra = models.CharField(max_length=10, primary_key=True, verbose_name="Mã yêu cầu đổi/trả")
    don_hang = models.ForeignKey(
        "orders.DonHang", on_delete=models.PROTECT, related_name="yeu_cau_doi_tra", verbose_name="Đơn hàng"
    )
    hinh_thuc = models.CharField(max_length=5, choices=HinhThucDoiTra.choices, verbose_name="Hình thức")
    nguyen_nhan = models.ForeignKey(
        NguyenNhan, on_delete=models.PROTECT, related_name="yeu_cau_doi_tra", verbose_name="Nguyên nhân"
    )
    mo_ta = models.CharField(max_length=500, null=True, blank=True, verbose_name="Mô tả chi tiết")
    thong_tin_tai_khoan_hoan = models.TextField(null=True, blank=True, verbose_name="Tài khoản hoàn tiền (mã hóa)")
    trang_thai = models.CharField(
        max_length=25, choices=TrangThaiDoiTra.choices, default=TrangThaiDoiTra.CHO_XU_LY,
        verbose_name="Trạng thái",
    )
    hau_mai_truoc = models.CharField(max_length=30, null=True, blank=True, verbose_name="Hậu mãi trước đó")
    thoi_diem_gui = models.DateTimeField(default=timezone.now, verbose_name="Thời điểm gửi")

    # ----- Xử lý của nhân viên (UC05) -----
    nhan_vien_xu_ly = models.ForeignKey(
        "customers.NhanVien", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="yeu_cau_doi_tra_da_xu_ly", verbose_name="Nhân viên xử lý",
    )
    thoi_diem_xu_ly = models.DateTimeField(null=True, blank=True, verbose_name="Thời điểm duyệt/từ chối")
    ly_do_tu_choi = models.CharField(max_length=255, null=True, blank=True, verbose_name="Lý do từ chối")
    ghi_chu_noi_bo = models.CharField(max_length=255, null=True, blank=True, verbose_name="Ghi chú nội bộ")
    khong_thu_hoi_hang = models.BooleanField(default=False, verbose_name="Không thu hồi hàng")  # UC05 A1
    han_gui_hang = models.DateTimeField(null=True, blank=True, verbose_name="Hạn khách gửi hàng")  # BR16
    thoi_diem_nhan_hang = models.DateTimeField(null=True, blank=True, verbose_name="Thời điểm nhận hàng")
    ben_chiu_phi_van_chuyen = models.CharField(  # M4-BR07
        max_length=15, choices=BenChiuPhi.choices, default=BenChiuPhi.KHACH_HANG,
        verbose_name="Bên chịu phí vận chuyển",
    )
    # Giao hàng thay thế (hình thức đổi). M4 không tạo đơn hàng mới nên chỉ lưu thông tin gửi hàng đổi.
    ma_van_don_doi = models.CharField(max_length=50, null=True, blank=True, verbose_name="Mã vận đơn hàng đổi")
    ma_van_don_gui_lai = models.CharField(
        max_length=50, null=True, blank=True, verbose_name="Mã vận đơn gửi trả lại khách"
    )
    chenh_lech_gia = models.DecimalField(  # BR17: dương = khách trả thêm, âm = hoàn phần chênh
        max_digits=15, decimal_places=0, default=0, verbose_name="Chênh lệch giá khi đổi"
    )
    thoi_diem_hoan_tat = models.DateTimeField(null=True, blank=True, verbose_name="Thời điểm hoàn tất")

    class Meta:
        db_table = "HM_YEUCAU_DOITRA"
        verbose_name = "Yêu cầu đổi/trả"
        verbose_name_plural = "Yêu cầu đổi/trả"
        ordering = ["thoi_diem_gui", "ma_yc_doi_tra"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(trang_thai__in=TrangThaiDoiTra.values), name="ck_hm_dt_trang_thai"
            ),
            models.CheckConstraint(
                condition=models.Q(hinh_thuc__in=HinhThucDoiTra.values), name="ck_hm_dt_hinh_thuc"
            ),
        ]

    def __str__(self):
        return f"{self.ma_yc_doi_tra} - {self.don_hang_id} - {self.get_trang_thai_display()}"


class KetQuaKiemTraTra(models.TextChoices):
    CHUA_KIEM_TRA = "CHUA_KIEM_TRA", "Chưa kiểm tra"
    DAT = "DAT", "Đạt"
    KHONG_DAT = "KHONG_DAT", "Không đạt"


class KhoNhap(models.TextChoices):
    """M4-BR04: hàng đạt nhập kho bán; hàng lỗi/hư hỏng nhập kho hàng lỗi."""
    KHO_BAN = "KHO_BAN", "Kho bán"
    KHO_LOI = "KHO_LOI", "Kho hàng lỗi"


class DongDoiTra(models.Model):
    ma_dong = models.CharField(max_length=10, primary_key=True, verbose_name="Mã dòng")
    yeu_cau = models.ForeignKey(
        YeuCauDoiTra, on_delete=models.CASCADE, related_name="dong", verbose_name="Yêu cầu đổi/trả"
    )
    chi_tiet_don_hang = models.ForeignKey(
        "orders.ChiTietDonHang", on_delete=models.PROTECT, related_name="dong_doi_tra",
        verbose_name="Dòng sản phẩm của đơn",
    )
    so_luong = models.PositiveIntegerField(verbose_name="Số lượng yêu cầu")
    bien_the_doi = models.ForeignKey(  # chỉ có với hình thức đổi
        "products.BienTheSanPham", on_delete=models.PROTECT, null=True, blank=True,
        related_name="dong_doi_tra_nhan", verbose_name="Sản phẩm/phân loại muốn nhận",
    )
    # ----- Kết quả kiểm tra hàng nhận về (UC05 bước 4) -----
    ket_qua_kiem_tra = models.CharField(
        max_length=15, choices=KetQuaKiemTraTra.choices, default=KetQuaKiemTraTra.CHUA_KIEM_TRA,
        verbose_name="Kết quả kiểm tra",
    )
    so_luong_dat = models.PositiveIntegerField(default=0, verbose_name="Số lượng đạt")
    kho_nhap = models.CharField(max_length=10, choices=KhoNhap.choices, null=True, blank=True)
    ghi_chu_kiem_tra = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "HM_DONG_DOITRA"
        verbose_name = "Dòng đổi/trả"
        verbose_name_plural = "Dòng đổi/trả"
        constraints = [
            models.UniqueConstraint(fields=["yeu_cau", "chi_tiet_don_hang"], name="uq_hm_dong_yc_ctdh"),
            models.CheckConstraint(condition=models.Q(so_luong__gt=0), name="ck_hm_dong_soluong_duong"),
            models.CheckConstraint(
                condition=models.Q(so_luong_dat__lte=models.F("so_luong")), name="ck_hm_dong_dat_khong_qua"
            ),
        ]

    def __str__(self):
        return f"{self.ma_dong} - {self.chi_tiet_don_hang_id} x {self.so_luong}"


def kiem_tra_dung_luong_anh(tep):
    """M4-BR07: mỗi ảnh không quá 5 MB."""
    if tep.size > 5 * 1024 * 1024:
        raise ValidationError("Mỗi ảnh không được quá 5 MB.")


class AnhMinhChung(models.Model):
    ma_anh = models.CharField(max_length=10, primary_key=True, verbose_name="Mã ảnh")
    yeu_cau = models.ForeignKey(
        YeuCauDoiTra, on_delete=models.CASCADE, related_name="anh_minh_chung", verbose_name="Yêu cầu đổi/trả"
    )
    # FileField (không dùng ImageField) để không cần cài thêm thư viện Pillow
    tep = models.FileField(
        upload_to="after_sales/minh_chung/",
        validators=[FileExtensionValidator(["jpg", "jpeg", "png"]), kiem_tra_dung_luong_anh],
        verbose_name="Ảnh minh chứng",
    )
    thoi_diem_tai = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "HM_ANH_MINHCHUNG"
        verbose_name = "Ảnh minh chứng"
        verbose_name_plural = "Ảnh minh chứng"
        ordering = ["thoi_diem_tai", "ma_anh"]


# ==========================================================
# 6. HOÀN TIỀN (M4-UC06, M4-BR08, M4-BR09)
# ==========================================================
class NguonHoanTien(models.TextChoices):
    HUY_DON = "HUY_DON", "Hủy đơn"
    GIAO_THAT_BAI = "GIAO_THAT_BAI", "Hoàn hàng về kho"
    TRA_HANG = "TRA_HANG", "Trả hàng"
    CHENH_LECH_DOI = "CHENH_LECH_DOI", "Chênh lệch khi đổi hàng"
    THANH_TOAN_THUA = "THANH_TOAN_THUA", "Thanh toán thừa"


class TrangThaiHoanTien(models.TextChoices):
    CHO_HOAN = "CHO_HOAN", "Chờ hoàn"
    DA_HOAN = "DA_HOAN", "Đã hoàn"
    THAT_BAI = "THAT_BAI", "Thất bại"


class PhuongThucHoan(models.TextChoices):
    PHUONG_THUC_GOC = "PHUONG_THUC_GOC", "Về phương thức thanh toán ban đầu"
    CHUYEN_KHOAN = "CHUYEN_KHOAN", "Chuyển khoản"


class GiaoDichHoanTien(models.Model):
    ma_hoan_tien = models.CharField(max_length=10, primary_key=True, verbose_name="Mã khoản hoàn")
    don_hang = models.ForeignKey(
        "orders.DonHang", on_delete=models.PROTECT, related_name="hoan_tien", verbose_name="Đơn hàng"
    )
    nguon = models.CharField(max_length=20, choices=NguonHoanTien.choices, verbose_name="Nguồn phát sinh")
    yeu_cau_huy = models.ForeignKey(
        YeuCauHuy, on_delete=models.SET_NULL, null=True, blank=True, related_name="hoan_tien"
    )
    yeu_cau_doi_tra = models.ForeignKey(
        YeuCauDoiTra, on_delete=models.SET_NULL, null=True, blank=True, related_name="hoan_tien"
    )
    xu_ly_giao_that_bai = models.ForeignKey(
        XuLyGiaoThatBai, on_delete=models.SET_NULL, null=True, blank=True, related_name="hoan_tien"
    )
    # Giao dịch điều chỉnh sai sót (BR09): trỏ về giao dịch gốc, bắt buộc có lý do
    giao_dich_goc = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="giao_dich_dieu_chinh"
    )
    la_dieu_chinh = models.BooleanField(default=False, verbose_name="Là giao dịch điều chỉnh")

    so_tien_da_thanh_toan = models.DecimalField(
        max_digits=15, decimal_places=0, verbose_name="Số tiền khách đã thanh toán"
    )
    so_tien_de_xuat = models.DecimalField(max_digits=15, decimal_places=0, verbose_name="Số tiền đề xuất hoàn")
    so_tien_hoan = models.DecimalField(
        max_digits=15, decimal_places=0, null=True, blank=True, verbose_name="Số tiền hoàn thực tế"
    )
    ly_do_dieu_chinh = models.CharField(max_length=255, null=True, blank=True, verbose_name="Lý do điều chỉnh")
    phuong_thuc_hoan = models.CharField(
        max_length=20, choices=PhuongThucHoan.choices, default=PhuongThucHoan.PHUONG_THUC_GOC,
        verbose_name="Phương thức hoàn",
    )
    # Lưu dạng mã hóa; chỉ giải mã khi nhân viên xử lý, hiển thị luôn che bớt (xem services.py)
    thong_tin_tai_khoan_nhan = models.TextField(null=True, blank=True, verbose_name="Tài khoản nhận (mã hóa)")
    ma_giao_dich_hoan = models.CharField(
        max_length=50, null=True, blank=True, unique=True, verbose_name="Mã giao dịch hoàn"  # BR09
    )
    trang_thai = models.CharField(
        max_length=15, choices=TrangThaiHoanTien.choices, default=TrangThaiHoanTien.CHO_HOAN,
        verbose_name="Trạng thái",
    )
    ly_do_that_bai = models.CharField(max_length=255, null=True, blank=True, verbose_name="Lý do thất bại")
    thoi_diem_tao = models.DateTimeField(default=timezone.now, verbose_name="Thời điểm tạo")
    thoi_diem_hoan = models.DateTimeField(null=True, blank=True, verbose_name="Thời điểm hoàn")
    nhan_vien_xu_ly = models.ForeignKey(
        "customers.NhanVien", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hoan_tien_da_xu_ly", verbose_name="Nhân viên xử lý",
    )

    class Meta:
        db_table = "HM_GIAODICH_HOANTIEN"
        verbose_name = "Giao dịch hoàn tiền"
        verbose_name_plural = "Giao dịch hoàn tiền"
        ordering = ["thoi_diem_tao", "ma_hoan_tien"]
        constraints = [
            models.CheckConstraint(condition=models.Q(so_tien_da_thanh_toan__gt=0), name="ck_hm_ht_da_tt_duong"),
            models.CheckConstraint(condition=models.Q(so_tien_de_xuat__gt=0), name="ck_hm_ht_de_xuat_duong"),
            models.CheckConstraint(
                condition=models.Q(so_tien_hoan__isnull=True) | models.Q(so_tien_hoan__gt=0),
                name="ck_hm_ht_hoan_duong",
            ),
            models.CheckConstraint(condition=models.Q(nguon__in=NguonHoanTien.values), name="ck_hm_ht_nguon"),
            models.CheckConstraint(
                condition=models.Q(trang_thai__in=TrangThaiHoanTien.values), name="ck_hm_ht_trang_thai"
            ),
        ]

    def save(self, *args, **kwargs):
        # BR09: giao dịch đã hoàn không được sửa. Kiểm tra theo giá trị đang lưu trong CSDL.
        if not self._state.adding:
            da_hoan = GiaoDichHoanTien.objects.filter(
                pk=self.pk, trang_thai=TrangThaiHoanTien.DA_HOAN
            ).exists()
            if da_hoan:
                raise ValidationError("Giao dịch hoàn tiền đã hoàn không được sửa. Hãy tạo giao dịch điều chỉnh.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.trang_thai == TrangThaiHoanTien.DA_HOAN:
            raise ValidationError("Giao dịch hoàn tiền đã hoàn không được xóa.")
        super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.ma_hoan_tien} - {self.don_hang_id} - {self.get_trang_thai_display()}"


# ==========================================================
# 7. SỔ BIẾN ĐỘNG KHO DO HẬU MÃI (M4-BR04)
#    M1–M3 hiện chưa có bảng tồn kho. Để M4 vẫn ghi vết được "cộng lại tồn kho"
#    mà không tự thêm bảng tồn kho vào module khác, M4 ghi mỗi lần nhập/xuất
#    do hậu mãi thành một dòng ở đây. Khi nhóm có bảng tồn kho thật, chỉ cần
#    sửa DichVuKho trong services.py để cập nhật bảng đó (xem hướng dẫn).
# ==========================================================
class LyDoBienDongKho(models.TextChoices):
    HUY_DON = "HUY_DON", "Hủy đơn"
    HOAN_HANG = "HOAN_HANG", "Hoàn hàng về kho sau giao thất bại"
    TRA_HANG = "TRA_HANG", "Nhận hàng trả"
    DOI_HANG_NHAN_VE = "DOI_HANG_NHAN_VE", "Nhận hàng đổi về"
    DOI_HANG_XUAT = "DOI_HANG_XUAT", "Xuất hàng đổi cho khách"


class BienDongKho(models.Model):
    ma_bien_dong = models.CharField(max_length=10, primary_key=True, verbose_name="Mã biến động")
    don_hang = models.ForeignKey(
        "orders.DonHang", on_delete=models.PROTECT, related_name="bien_dong_kho", verbose_name="Đơn hàng"
    )
    bien_the = models.ForeignKey(
        "products.BienTheSanPham", on_delete=models.PROTECT, related_name="bien_dong_kho_hau_mai",
        verbose_name="Biến thể sản phẩm",
    )
    so_luong = models.IntegerField(verbose_name="Số lượng (dương: nhập, âm: xuất)")
    kho = models.CharField(max_length=10, choices=KhoNhap.choices, default=KhoNhap.KHO_BAN, verbose_name="Kho")
    ly_do = models.CharField(max_length=20, choices=LyDoBienDongKho.choices, verbose_name="Lý do")
    ma_yeu_cau = models.CharField(max_length=10, null=True, blank=True, verbose_name="Mã yêu cầu liên quan")
    thoi_diem = models.DateTimeField(default=timezone.now, verbose_name="Thời điểm")
    nhan_vien = models.ForeignKey(
        "customers.NhanVien", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="bien_dong_kho_hau_mai", verbose_name="Nhân viên",
    )

    class Meta:
        db_table = "HM_BIENDONG_KHO"
        verbose_name = "Biến động kho do hậu mãi"
        verbose_name_plural = "Biến động kho do hậu mãi"
        ordering = ["thoi_diem", "ma_bien_dong"]
        constraints = [
            models.CheckConstraint(condition=~models.Q(so_luong=0), name="ck_hm_kho_khac_khong"),
        ]


# ==========================================================
# 8. TIMELINE HẬU MÃI (M4-BR13, M4-UC09)
#    Mỗi lần đổi trạng thái của một yêu cầu ghi một dòng; không sửa, không xóa.
# ==========================================================
class LichSuHauMai(models.Model):
    ma_lich_su = models.CharField(max_length=10, primary_key=True, verbose_name="Mã mốc")
    don_hang = models.ForeignKey(
        "orders.DonHang", on_delete=models.CASCADE, related_name="lich_su_hau_mai", verbose_name="Đơn hàng"
    )
    loai_yeu_cau = models.CharField(max_length=15, choices=LoaiYeuCau.choices, verbose_name="Loại yêu cầu")
    ma_yeu_cau = models.CharField(max_length=10, db_index=True, verbose_name="Mã yêu cầu")
    moc = models.CharField(max_length=100, verbose_name="Mốc")
    trang_thai = models.CharField(max_length=30, verbose_name="Trạng thái")
    tac_nhan = models.CharField(max_length=20, verbose_name="Người thực hiện (loại)")  # TacNhan của M3
    nhan_vien = models.ForeignKey(
        "customers.NhanVien", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="lich_su_hau_mai", verbose_name="Nhân viên",
    )
    thoi_diem = models.DateTimeField(default=timezone.now, verbose_name="Thời điểm")
    ghi_chu = models.CharField(max_length=500, null=True, blank=True, verbose_name="Ghi chú (khách xem được)")
    # BR12: khách hàng không được thấy trường này
    ghi_chu_noi_bo = models.CharField(max_length=500, null=True, blank=True, verbose_name="Ghi chú nội bộ")
    anh_minh_chung = models.ForeignKey(
        AnhMinhChung, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        db_table = "HM_LICHSU_HAUMAI"
        verbose_name = "Mốc timeline hậu mãi"
        verbose_name_plural = "Timeline hậu mãi"
        ordering = ["thoi_diem", "ma_lich_su"]  # cũ đến mới, đọc như một dòng thời gian

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Mốc timeline hậu mãi không được sửa.")  # BR13
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Mốc timeline hậu mãi không được xóa.")  # BR13

    def __str__(self):
        return f"{self.ma_yeu_cau}: {self.moc}"


# ==========================================================
# 9. THÔNG BÁO HẬU MÃI (M4-BR18)
#    nhan_vien_chung = True: thông báo gửi cho mọi nhân viên có quyền xử lý.
#    M5 cũng có bảng thông báo riêng cho đơn hàng; bảng này chỉ chứa thông báo do M4 sinh ra.
# ==========================================================
class ThongBaoHauMai(models.Model):
    ma_thong_bao = models.CharField(max_length=10, primary_key=True, verbose_name="Mã thông báo")
    khach_hang = models.ForeignKey(
        "customers.KhachHang", on_delete=models.CASCADE, null=True, blank=True,
        related_name="thong_bao_hau_mai", verbose_name="Khách hàng nhận",
    )
    nhan_vien_chung = models.BooleanField(default=False, verbose_name="Gửi cho nhân viên")
    don_hang = models.ForeignKey(
        "orders.DonHang", on_delete=models.CASCADE, related_name="thong_bao_hau_mai", verbose_name="Đơn hàng"
    )
    tieu_de = models.CharField(max_length=150, verbose_name="Tiêu đề")
    noi_dung = models.CharField(max_length=500, verbose_name="Nội dung")
    da_doc = models.BooleanField(default=False, verbose_name="Đã đọc")
    thoi_diem_gui = models.DateTimeField(default=timezone.now, verbose_name="Thời điểm gửi")

    class Meta:
        db_table = "HM_THONGBAO"
        verbose_name = "Thông báo hậu mãi"
        verbose_name_plural = "Thông báo hậu mãi"
        ordering = ["-thoi_diem_gui", "-ma_thong_bao"]
        constraints = [
            # Hoặc gửi cho một khách, hoặc gửi cho nhân viên; không được cả hai, không được thiếu cả hai
            models.CheckConstraint(
                condition=(models.Q(khach_hang__isnull=False, nhan_vien_chung=False)
                           | models.Q(khach_hang__isnull=True, nhan_vien_chung=True)),
                name="ck_hm_tb_mot_nguoi_nhan",
            ),
        ]
