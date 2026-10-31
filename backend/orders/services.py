# File: backend/orders/services.py
# Module 3 – Nghiệp vụ giỏ hàng, đặt hàng, xử lý đơn hàng
# Phần 1/4: lỗi nghiệp vụ, sinh mã, tra tỉnh/thành từ địa chỉ của khách
#
# Quy ước (theo M1 – customers/services.py):
# - View không tự xử lý nghiệp vụ, chỉ gọi hàm ở file này.
# - Vi phạm quy tắc nghiệp vụ thì raise LoiNghiepVuDonHang kèm câu báo lỗi
#   tiếng Việt; view bắt lỗi này và trả câu báo về cho người dùng.

import unicodedata

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