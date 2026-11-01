# File: backend/orders/serializers.py
# Module 3 – Serializer cho API giỏ hàng, trang thanh toán, đặt hàng.
#
# Serializer làm hai việc, và CHỈ hai việc này:
#   - Đầu vào: đọc dữ liệu trình duyệt gửi lên (JSON), kiểm tra ĐỊNH DẠNG
#     (có gửi không, có phải số nguyên không, mã có tồn tại không),
#     đổi sang kiểu Python cho view truyền vào service.
#   - Đầu ra: đổi kết quả service trả về (đối tượng model, dict) thành JSON.
# Quy tắc NGHIỆP VỤ (số lượng > 0, biến thể còn bán, giá sỉ/lẻ...) vẫn nằm
# trong services.py để test, API và giao diện HTML sau này dùng chung một chỗ.
#
# Phần 1 (file này): giỏ hàng – M3-UC01, M3-UC02.
# Phần 2 (bước sau): trang thanh toán, đặt hàng – M3-UC03, M3-UC04.

from rest_framework import serializers

from products.models import BienTheSanPham

from .models import LoaiGia

# Giới hạn kỹ thuật, KHÔNG phải quy tắc nghiệp vụ: số lớn nhất mà
# PositiveIntegerField của Django lưu an toàn trên mọi loại CSDL.
# Chặn ở đây để số khổng lồ không làm máy chủ lỗi 500 khi ghi xuống SQLite.
SO_LUONG_TOI_DA_KY_THUAT = 2147483647

# Câu báo trùng với câu của DichVuGioHang.kiem_tra_so_luong (M3-BR03)
LOI_SO_LUONG = "Số lượng phải là số nguyên lớn hơn 0."


def truong_so_luong():
    """
    Trường số lượng dùng chung cho thêm vào giỏ và sửa số lượng.
    Chỉ kiểm tra "có phải số nguyên không"; số <= 0 để service báo lỗi.
    """
    return serializers.IntegerField(
        max_value=SO_LUONG_TOI_DA_KY_THUAT,
        error_messages={
            "required": "Vui lòng nhập số lượng.",
            "null": "Vui lòng nhập số lượng.",
            "invalid": LOI_SO_LUONG,
            "max_value": "Số lượng quá lớn.",
            "max_string_length": "Số lượng quá lớn.",
        },
    )


# ==========================================================
# A. ĐẦU VÀO – dữ liệu trình duyệt gửi lên
# ==========================================================
class ThemVaoGioSerializer(serializers.Serializer):
    """
    M3-UC01. Trình duyệt gửi: {"ma_bien_the": "BT001", "so_luong": 2}
    Sau is_valid(): validated_data = {"bien_the": <BienTheSanPham>, "so_luong": 2}
    """

    # Nhận MÃ biến thể, trả về ĐỐI TƯỢNG biến thể (tra trong bảng của M2).
    # source="bien_the": trong validated_data, khóa là "bien_the" chứ không
    # phải "ma_bien_the", vì giá trị lúc đó đã là đối tượng, không còn là mã.
    ma_bien_the = serializers.PrimaryKeyRelatedField(
        queryset=BienTheSanPham.objects.select_related("san_pham"),
        source="bien_the",
        error_messages={
            "required": "Vui lòng chọn sản phẩm.",
            "null": "Vui lòng chọn sản phẩm.",
            "does_not_exist": "Không tìm thấy sản phẩm.",
            "incorrect_type": "Mã sản phẩm không hợp lệ.",
        },
    )
    so_luong = truong_so_luong()


class CapNhatSoLuongSerializer(serializers.Serializer):
    """
    M3-UC02 sửa số lượng. Mã dòng giỏ nằm trên URL (cart/<ma_ctgh>/),
    nên trình duyệt chỉ gửi: {"so_luong": 5}
    """

    so_luong = truong_so_luong()


# ==========================================================
# B. ĐẦU RA – đổi kết quả service thành JSON
#    Tiền là Decimal có 0 chữ số thập phân (đồng). Xuất bằng IntegerField
#    để JSON ra 460000 thay vì chuỗi "460000".
# ==========================================================
class DongGioHangSerializer(serializers.Serializer):
    """
    Một dòng giỏ, đầu vào là dict do DichVuTinhTien.dong_kem_gia trả về:
    {"ma_ctgh", "bien_the", "so_luong", "con_ban", "da_chon",
     "loai_gia", "don_gia", "thanh_tien"}
    source="bien_the.huong_vi": vào khóa "bien_the" của dict rồi lấy thuộc tính
    huong_vi của đối tượng biến thể (giống JOIN sang bảng BIENTHE_SANPHAM).
    """

    ma_ctgh = serializers.CharField()
    ma_bien_the = serializers.CharField(source="bien_the.ma_bien_the")
    ten_sp = serializers.CharField(source="bien_the.san_pham.ten_sp")
    huong_vi = serializers.CharField(source="bien_the.huong_vi")
    quy_cach = serializers.CharField(source="bien_the.quy_cach")
    so_luong = serializers.IntegerField()
    con_ban = serializers.BooleanField()  # False -> giao diện đánh dấu, không cho chọn (UC02-E3)
    da_chon = serializers.BooleanField()
    loai_gia = serializers.CharField()  # mã: GIA_LE / GIA_SI
    ten_loai_gia = serializers.SerializerMethodField()  # nhãn: Giá lẻ / Giá sỉ
    don_gia = serializers.IntegerField()
    thanh_tien = serializers.IntegerField()

    def get_ten_loai_gia(self, dong):
        return LoaiGia(dong["loai_gia"]).label


class GioHangSerializer(serializers.Serializer):
    """
    Cả giỏ, đầu vào là dict do DichVuTinhTien.xem_gio_hang trả về:
    {"cac_dong": [...], "tam_tinh": Decimal}
    """

    so_dong = serializers.SerializerMethodField()  # số trên biểu tượng giỏ (UC01 bước 3)
    cac_dong = DongGioHangSerializer(many=True)
    tam_tinh = serializers.IntegerField()

    def get_so_dong(self, gio):
        return len(gio["cac_dong"])

# ==========================================================
# PHẦN 2: TRANG THANH TOÁN, ĐẶT HÀNG – M3-UC03, M3-UC04
# ==========================================================

# ---------- C. ĐẦU VÀO: đặt hàng ----------
class DatHangSerializer(serializers.Serializer):
    """
    M3-UC03 bước 3. Trình duyệt gửi:
    {"chon": ["CG001", "CG002"], "ma_dia_chi": "DC001", "ma_pttt": "PT002"}
    Chỉ gửi MÃ; tiền hàng, phí, tổng đều do service tính lại.
    "chon" rỗng và "ma_pttt" rỗng vẫn cho qua để service báo đúng câu của UC
    (UC02-E1, UC03-E1).
    """

    chon = serializers.ListField(
        child=serializers.CharField(),
        default=list,
        error_messages={"not_a_list": "Danh sách sản phẩm chọn mua không hợp lệ."},
    )
    ma_dia_chi = serializers.CharField(
        error_messages={
            "required": "Vui lòng chọn địa chỉ giao hàng.",
            "blank": "Vui lòng chọn địa chỉ giao hàng.",
            "null": "Vui lòng chọn địa chỉ giao hàng.",
        },
    )
    ma_pttt = serializers.CharField(allow_blank=True, allow_null=True, default="")


# ---------- D. ĐẦU RA: trang thanh toán ----------
class DiaChiGiaoHangSerializer(serializers.Serializer):
    """Một địa chỉ trong sổ địa chỉ DiaChiKH của M1 (M3 chỉ đọc)."""

    ma_dia_chi = serializers.CharField()
    ten_nguoi_nhan = serializers.CharField()
    so_dien_thoai = serializers.CharField()
    dia_chi_chi_tiet = serializers.CharField()
    phuong_xa = serializers.CharField()   # có thể null -> JSON ra null
    quan_huyen = serializers.CharField()  # có thể null -> JSON ra null
    tinh_thanh = serializers.CharField()
    mac_dinh = serializers.BooleanField()


class PhuongThucThanhToanSerializer(serializers.Serializer):
    ma_pttt = serializers.CharField()
    ten_pttt = serializers.CharField()


class TrangThanhToanSerializer(serializers.Serializer):
    """
    Đầu vào là dict do DichVuTrangThanhToan.xem_trang_thanh_toan trả về:
    {"cac_dong", "dia_chi", "tinh_thanh", "tong_tien_hang", "phi_van_chuyen",
     "tong_thanh_toan", "cac_phuong_thuc"}
    """

    cac_dong = DongGioHangSerializer(many=True)
    dia_chi = DiaChiGiaoHangSerializer()
    ma_tinh = serializers.CharField(source="tinh_thanh.ma_tinh")
    ten_tinh = serializers.CharField(source="tinh_thanh.ten_tinh")
    tong_tien_hang = serializers.IntegerField()
    phi_van_chuyen = serializers.IntegerField()
    tong_thanh_toan = serializers.IntegerField()
    cac_phuong_thuc = PhuongThucThanhToanSerializer(many=True)


# ---------- E. ĐẦU RA: đơn hàng ----------
# Dùng cho đơn vừa đặt (UC03); giai đoạn 4 dùng lại cho chi tiết đơn (UC05, UC07).
# source="get_trang_thai_display": gọi hàm Django tự sinh cho trường có choices,
# trả nhãn tiếng Việt ("Chờ xác nhận") của mã đang lưu ("CHO_XAC_NHAN").
class ChiTietDonHangSerializer(serializers.Serializer):
    ma_ctdh = serializers.CharField()
    ma_bien_the = serializers.CharField(source="bien_the_id")
    ten_sp = serializers.CharField(source="bien_the.san_pham.ten_sp")
    huong_vi = serializers.CharField(source="bien_the.huong_vi")
    quy_cach = serializers.CharField(source="bien_the.quy_cach")
    so_luong = serializers.IntegerField()
    loai_gia = serializers.CharField(source="loai_gia_ap_dung")
    ten_loai_gia = serializers.CharField(source="get_loai_gia_ap_dung_display")
    don_gia = serializers.IntegerField()
    thanh_tien = serializers.IntegerField()


class DonHangSerializer(serializers.Serializer):
    ma_dh = serializers.CharField()
    ngay_dat = serializers.DateTimeField()
    trang_thai = serializers.CharField()
    ten_trang_thai = serializers.CharField(source="get_trang_thai_display")
    trang_thai_thanh_toan = serializers.CharField()
    ten_trang_thai_thanh_toan = serializers.CharField(source="get_trang_thai_thanh_toan_display")
    ma_pttt = serializers.CharField(source="phuong_thuc_thanh_toan_id")
    ten_pttt = serializers.CharField(source="phuong_thuc_thanh_toan.ten_pttt")
    ho_ten_nguoi_nhan = serializers.CharField()
    sdt_nguoi_nhan = serializers.CharField()
    dia_chi_giao_hang = serializers.CharField()
    ten_tinh = serializers.CharField(source="tinh_thanh.ten_tinh")
    tong_tien_hang = serializers.IntegerField()
    phi_van_chuyen = serializers.IntegerField()
    tong_thanh_toan = serializers.IntegerField()
    chi_tiet = ChiTietDonHangSerializer(many=True)  # don.chi_tiet.all()