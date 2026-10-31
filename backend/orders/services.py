# File: backend/orders/services.py
# Module 3 – Nghiệp vụ giỏ hàng, đặt hàng, xử lý đơn hàng
# Nội dung đã có:
#   1. Lỗi nghiệp vụ          2. Sinh mã khóa chính
#   3. Tra tỉnh/thành         4. Giỏ hàng (M3-UC01, M3-UC02)
#
# Quy ước (theo M1 – customers/services.py):
# - View không tự xử lý nghiệp vụ, chỉ gọi hàm ở file này.
# - Vi phạm quy tắc nghiệp vụ thì raise LoiNghiepVuDonHang kèm câu báo lỗi
#   tiếng Việt; view bắt lỗi này và trả câu báo về cho người dùng.

import unicodedata

from django.db import transaction

from .models import (
    ChiTietDonHang,
    ChiTietGioHang,
    DonHang,
    GiaoDichThanhToan,
    GioHang,
    LichSuTrangThaiDonHang,
    TinhThanh,
)


# ==========================================================
# 1. LỖI NGHIỆP VỤ
# ==========================================================
class LoiNghiepVuDonHang(Exception):
    """Lỗi khi vi phạm quy tắc nghiệp vụ của M3 (giỏ hàng, đặt hàng, xử lý đơn)."""
    pass


class LoiQuyenDonHang(LoiNghiepVuDonHang):
    """Lỗi khi người dùng không có quyền thao tác trên giỏ hàng hoặc đơn hàng."""
    pass


# ==========================================================
# 2. SINH MÃ KHÓA CHÍNH (theo cách M1: đếm + 1, trùng thì tăng tiếp)
#    TinhThanh (TT) và PhuongThucThanhToan (PT) đã nạp sẵn bằng migration
#    nên không cần sinh mã.
# ==========================================================
TIEN_TO_MA = {
    GioHang: "CART",
    ChiTietGioHang: "CG",
    DonHang: "DH",
    ChiTietDonHang: "CT",
    LichSuTrangThaiDonHang: "LT",
    GiaoDichThanhToan: "GD",
}


def sinh_ma(model):
    """Trả về mã chưa dùng cho model, ví dụ sinh_ma(DonHang) -> "DH001"."""
    tien_to = TIEN_TO_MA[model]
    ten_khoa_chinh = model._meta.pk.name  # ví dụ "ma_dh" với DonHang

    so_thu_tu = model.objects.count() + 1

    while True:
        ma = f"{tien_to}{so_thu_tu:03d}"

        if not model.objects.filter(**{ten_khoa_chinh: ma}).exists():
            return ma

        so_thu_tu += 1


# ==========================================================
# 3. TRA TỈNH/THÀNH TỪ ĐỊA CHỈ CỦA KHÁCH
#    DiaChiKH.tinh_thanh (M1) là ô chữ tự do, còn bảng phí là TinhThanh (M3).
#    Phải chuẩn hóa hai bên về cùng một dạng rồi mới so được.
#    Phục vụ M3-UC03 E4, M3-UC04, M3-BR05.
# ==========================================================
TIEN_TO_TEN_TINH = ("thanh pho ", "tp. ", "tp.", "tp ", "tinh ")

# Tên gọi khác hay gặp -> tên đã chuẩn hóa trong bảng TinhThanh
TEN_GOI_KHAC = {
    "hcm": "ho chi minh",
    "tphcm": "ho chi minh",
    "sai gon": "ho chi minh",
    "thua thien hue": "hue",
}


def chuan_hoa_ten_tinh(ten_tinh):
    """
    Đưa tên tỉnh về dạng so sánh được:
    "  Thành phố  Đà Nẵng " -> "da nang"; "Khánh Hoà" và "Khánh Hòa" -> "khanh hoa".
    """
    if not ten_tinh:
        return ""

    # Bước 1: chữ thường, tách dấu khỏi chữ cái rồi bỏ phần dấu
    chuoi = unicodedata.normalize("NFD", ten_tinh.strip().lower())
    chuoi = "".join(ky_tu for ky_tu in chuoi if unicodedata.category(ky_tu) != "Mn")
    chuoi = chuoi.replace("đ", "d")

    # Bước 2: gộp nhiều khoảng trắng liên tiếp thành một
    chuoi = " ".join(chuoi.split())

    # Bước 3: bỏ tiền tố hành chính ở đầu
    for tien_to in TIEN_TO_TEN_TINH:
        if chuoi.startswith(tien_to):
            chuoi = chuoi[len(tien_to):].strip()
            break

    # Bước 4: đổi tên gọi khác về tên chuẩn
    return TEN_GOI_KHAC.get(chuoi, chuoi)


def tim_tinh_thanh(ten_tinh):
    """
    Tìm dòng TinhThanh ứng với tên tỉnh trên địa chỉ của khách.
    Không tìm thấy hoặc tỉnh đã ngừng phục vụ -> LoiNghiepVuDonHang.
    """
    khoa_can_tim = chuan_hoa_ten_tinh(ten_tinh)

    if not khoa_can_tim:
        raise LoiNghiepVuDonHang("Địa chỉ giao hàng chưa có Tỉnh/Thành phố.")

    for tinh in TinhThanh.objects.all():
        if chuan_hoa_ten_tinh(tinh.ten_tinh) == khoa_can_tim:
            if not tinh.dang_hoat_dong:
                raise LoiNghiepVuDonHang(
                    f"Hiện chưa giao hàng đến {tinh.ten_tinh}. "
                    "Vui lòng chọn địa chỉ khác."
                )
            return tinh

    raise LoiNghiepVuDonHang(
        f"Tỉnh/Thành phố \"{ten_tinh}\" chưa có trong bảng phí giao hàng, "
        "không tính được phí. Vui lòng chọn địa chỉ khác."
    )

# ==========================================================
# 4. GIỎ HÀNG – M3-UC01 (thêm vào giỏ), M3-UC02 (sửa số lượng, xóa dòng)
#    Quy tắc: M3-BR01 (khách đang hoạt động), M3-BR03 (biến thể đang bán,
#    số lượng nguyên > 0, cộng dồn), M3-BR11 (hết hàng không chặn),
#    M3-BR24 (chỉ thao tác trên giỏ của chính mình).
# ==========================================================
TRANG_THAI_DANG_BAN = "ACTIVE"  # giá trị trang_thai của M1, M2 khi đang dùng


class DichVuGioHang:

    # ---------- Các hàm kiểm tra điều kiện ----------
    @staticmethod
    def kiem_tra_khach_hang(khach_hang):
        """M3-BR01: hồ sơ khách phải đang hoạt động."""
        if khach_hang.trang_thai != TRANG_THAI_DANG_BAN:
            raise LoiQuyenDonHang(
                "Tài khoản khách hàng đang ngừng hoạt động, không thể dùng giỏ hàng."
            )

    @staticmethod
    def bien_the_con_ban(bien_the):
        """True nếu cả biến thể lẫn sản phẩm cha đều đang bán (M2-BR09)."""
        return (
            bien_the.trang_thai == TRANG_THAI_DANG_BAN
            and bien_the.san_pham.trang_thai == TRANG_THAI_DANG_BAN
        )

    @staticmethod
    def kiem_tra_so_luong(so_luong):
        """M3-BR03: số lượng phải là số nguyên lớn hơn 0 (UC01-E2, UC02-E2)."""
        # bool là lớp con của int trong Python (True == 1) nên phải loại riêng
        if isinstance(so_luong, bool) or not isinstance(so_luong, int) or so_luong <= 0:
            raise LoiNghiepVuDonHang("Số lượng phải là số nguyên lớn hơn 0.")

    # ---------- Lấy giỏ và dòng giỏ ----------
    @staticmethod
    def lay_gio_hang(khach_hang, tao_neu_chua_co=False):
        """
        Trả về giỏ của khách. Khách chưa có giỏ:
        - tao_neu_chua_co=True  -> tạo giỏ mới (dùng khi thêm vào giỏ)
        - tao_neu_chua_co=False -> trả None (dùng khi chỉ xem)
        """
        gio = GioHang.objects.filter(khach_hang=khach_hang).first()

        if gio is None and tao_neu_chua_co:
            gio = GioHang.objects.create(
                ma_gio_hang=sinh_ma(GioHang),
                khach_hang=khach_hang,
            )

        return gio

    @staticmethod
    def lay_dong_cua_khach(khach_hang, ma_ctgh):
        """M3-BR24: chỉ trả dòng giỏ thuộc giỏ của chính khách này."""
        dong = (
            ChiTietGioHang.objects
            .select_related("gio_hang", "bien_the__san_pham")
            .filter(ma_ctgh=ma_ctgh)
            .first()
        )

        if dong is None:
            raise LoiNghiepVuDonHang("Không tìm thấy dòng hàng trong giỏ.")

        if dong.gio_hang.khach_hang_id != khach_hang.ma_kh:
            raise LoiQuyenDonHang("Bạn không có quyền thao tác trên giỏ hàng này.")

        return dong

    @staticmethod
    def dem_so_dong(khach_hang):
        """Số dòng trong giỏ, hiển thị trên biểu tượng giỏ hàng (UC01 bước 3)."""
        return ChiTietGioHang.objects.filter(gio_hang__khach_hang=khach_hang).count()

    # ---------- M3-UC01: Thêm vào giỏ ----------
    @staticmethod
    def them_vao_gio(khach_hang, bien_the, so_luong):
        DichVuGioHang.kiem_tra_khach_hang(khach_hang)
        DichVuGioHang.kiem_tra_so_luong(so_luong)

        if not DichVuGioHang.bien_the_con_ban(bien_the):
            raise LoiNghiepVuDonHang("Sản phẩm hiện không được bán.")  # UC01-E1

        # Tạo giỏ (nếu chưa có) và thêm/cộng dồn dòng: thành công cả hai hoặc không gì cả
        with transaction.atomic():
            gio = DichVuGioHang.lay_gio_hang(khach_hang, tao_neu_chua_co=True)

            dong = ChiTietGioHang.objects.filter(gio_hang=gio, bien_the=bien_the).first()

            if dong is None:
                dong = ChiTietGioHang.objects.create(
                    ma_ctgh=sinh_ma(ChiTietGioHang),
                    gio_hang=gio,
                    bien_the=bien_the,
                    so_luong=so_luong,
                )
            else:
                dong.so_luong += so_luong  # cộng dồn (M3-BR03)
                dong.save()

            gio.save(update_fields=["ngay_cap_nhat"])  # ghi thời điểm cập nhật giỏ

        return dong

    # ---------- M3-UC02: Sửa số lượng ----------
    @staticmethod
    def cap_nhat_so_luong(khach_hang, ma_ctgh, so_luong_moi):
        DichVuGioHang.kiem_tra_khach_hang(khach_hang)
        DichVuGioHang.kiem_tra_so_luong(so_luong_moi)

        dong = DichVuGioHang.lay_dong_cua_khach(khach_hang, ma_ctgh)

        if not DichVuGioHang.bien_the_con_ban(dong.bien_the):
            # UC02-E3: dòng hàng ngừng bán chỉ được xóa, không được sửa
            raise LoiNghiepVuDonHang(
                "Sản phẩm này hiện không được bán. Vui lòng xóa khỏi giỏ hàng."
            )

        with transaction.atomic():
            dong.so_luong = so_luong_moi
            dong.save()
            dong.gio_hang.save(update_fields=["ngay_cap_nhat"])

        return dong

    # ---------- M3-UC02: Xóa dòng ----------
    @staticmethod
    def xoa_dong(khach_hang, ma_ctgh):
        DichVuGioHang.kiem_tra_khach_hang(khach_hang)

        dong = DichVuGioHang.lay_dong_cua_khach(khach_hang, ma_ctgh)
        gio = dong.gio_hang

        with transaction.atomic():
            dong.delete()
            gio.save(update_fields=["ngay_cap_nhat"])