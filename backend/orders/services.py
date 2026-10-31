# File: backend/orders/services.py
# Module 3 – Nghiệp vụ giỏ hàng, đặt hàng, xử lý đơn hàng
# Nội dung đã có:
#   1. Lỗi nghiệp vụ          2. Sinh mã khóa chính
#   3. Tra tỉnh/thành         4. Giỏ hàng (M3-UC01, M3-UC02)
#   5. Địa chỉ giao hàng (M3-UC04)
#   6. Tính giá và tính tiền (M3-UC02 phần hiển thị, M3-UC03 bước 1)
#   7. Đặt hàng (M3-UC03 bước 3–4)
#
# Quy ước (theo M1 – customers/services.py):
# - View không tự xử lý nghiệp vụ, chỉ gọi hàm ở file này.
# - Vi phạm quy tắc nghiệp vụ thì raise LoiNghiepVuDonHang kèm câu báo lỗi
#   tiếng Việt; view bắt lỗi này và trả câu báo về cho người dùng.
# - Mọi số tiền dùng Decimal, không dùng float.

import unicodedata
from decimal import Decimal

from django.db import DatabaseError, transaction
from django.utils import timezone

from customers.models import DiaChiKH

from .models import (
    ChiTietDonHang,
    ChiTietGioHang,
    DonHang,
    GiaoDichThanhToan,
    GioHang,
    LichSuTrangThaiDonHang,
    LoaiGia,
    PhuongThucThanhToan,
    TacNhan,
    TinhThanh,
    TrangThaiDonHang,
    TrangThaiThanhToan,
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


# ==========================================================
# 5. ĐỊA CHỈ GIAO HÀNG – M3-UC04
#    M3 chỉ ĐỌC sổ địa chỉ DiaChiKH của M1, không tạo hay sửa (M3-BR08).
#    Quy tắc: M3-BR05 (phí theo tỉnh), M3-BR08, M1-BR09 (trường bắt buộc).
# ==========================================================
# Các trường DiaChiKH không được để trống -> tên hiển thị trong câu báo lỗi
TRUONG_DIA_CHI_BAT_BUOC = {
    "ten_nguoi_nhan": "tên người nhận",
    "so_dien_thoai": "số điện thoại",
    "dia_chi_chi_tiet": "địa chỉ chi tiết",
    "tinh_thanh": "Tỉnh/Thành phố",
}


class DichVuDiaChiGiaoHang:

    @staticmethod
    def lay_dia_chi_hien_thi_san(khach_hang):
        """
        UC04 bước 1: địa chỉ mặc định; không có thì địa chỉ cập nhật gần nhất.
        Sổ địa chỉ trống -> lỗi (UC04-E1, UC03-E3).
        """
        dia_chi = (
            DiaChiKH.objects
            .filter(khach_hang=khach_hang)
            .order_by("-mac_dinh", "-ngay_cap_nhat", "-ma_dia_chi")
            .first()
        )

        if dia_chi is None:
            raise LoiNghiepVuDonHang(
                "Bạn chưa có địa chỉ giao hàng. "
                "Vui lòng thêm địa chỉ mới trước khi đặt hàng."
            )

        return dia_chi

    @staticmethod
    def chon_dia_chi(khach_hang, ma_dia_chi):
        """
        UC04 bước 3: kiểm tra địa chỉ khách chọn, trả về địa chỉ, tỉnh và phí giao.
        """
        dia_chi = DiaChiKH.objects.filter(ma_dia_chi=ma_dia_chi).first()

        if dia_chi is None:
            raise LoiNghiepVuDonHang("Không tìm thấy địa chỉ giao hàng.")

        # UC04 NFR, M3-BR24: chỉ được dùng địa chỉ trong sổ của chính mình
        if dia_chi.khach_hang_id != khach_hang.ma_kh:
            raise LoiQuyenDonHang("Bạn không có quyền dùng địa chỉ này.")

        # UC04-E2: thiếu trường bắt buộc (M1-BR09)
        cac_truong_thieu = []
        for ten_truong, ten_hien_thi in TRUONG_DIA_CHI_BAT_BUOC.items():
            gia_tri = getattr(dia_chi, ten_truong) or ""
            if not gia_tri.strip():
                cac_truong_thieu.append(ten_hien_thi)

        if cac_truong_thieu:
            raise LoiNghiepVuDonHang(
                "Địa chỉ còn thiếu " + ", ".join(cac_truong_thieu)
                + ". Vui lòng cập nhật địa chỉ."
            )

        # UC04-E3, UC03-E4: tỉnh không có trong bảng phí thì tim_tinh_thanh báo lỗi
        tinh = tim_tinh_thanh(dia_chi.tinh_thanh)

        return {
            "dia_chi": dia_chi,
            "tinh_thanh": tinh,
            "phi_van_chuyen": tinh.phi_van_chuyen,
        }


# ==========================================================
# 6. TÍNH GIÁ VÀ TÍNH TIỀN
#    M3-UC02 (giá từng dòng, tạm tính, nhấn [Mua hàng]),
#    M3-UC03 bước 1 (tổng tiền hàng, phí giao, tổng thanh toán).
#    Quy tắc: M3-BR02 (loại khách), M3-BR04 (giá sỉ theo từng dòng),
#    M3-BR06 (thành tiền = tiền hàng + phí). Giá luôn tính ở máy chủ.
# ==========================================================
MA_LOAI_KHACH_SI = "LKH002"  # mã M1 nạp sẵn (customers/0003_seed_customer_types)


class DichVuTinhTien:

    # ---------- Giá của một dòng ----------
    @staticmethod
    def la_khach_si(khach_hang):
        """M3-BR02: M1 chỉ đổi khách sang LKH002 sau khi nhân viên duyệt."""
        return khach_hang.loai_khach_hang_id == MA_LOAI_KHACH_SI

    @staticmethod
    def tinh_gia_dong(khach_hang, bien_the, so_luong):
        """
        M3-BR04: trả về (loai_gia, don_gia, thanh_tien) cho MỘT dòng.
        Giá sỉ khi đủ cả ba điều kiện: khách sỉ, biến thể có giá sỉ,
        số lượng đạt mức tối thiểu của biến thể. Thiếu một điều kiện -> giá lẻ.
        """
        dung_gia_si = (
            DichVuTinhTien.la_khach_si(khach_hang)
            and bien_the.gia_ban_si is not None
            and so_luong >= bien_the.so_luong_toi_thieu_si
        )

        if dung_gia_si:
            loai_gia = LoaiGia.GIA_SI
            don_gia = Decimal(bien_the.gia_ban_si)
        else:
            loai_gia = LoaiGia.GIA_LE
            don_gia = Decimal(bien_the.gia_ban_le)

        return loai_gia, don_gia, don_gia * so_luong

    @staticmethod
    def dong_kem_gia(khach_hang, dong, con_ban, da_chon):
        """Gói một dòng giỏ cùng giá đã tính thành dict để hiển thị hoặc đặt hàng."""
        loai_gia, don_gia, thanh_tien = DichVuTinhTien.tinh_gia_dong(
            khach_hang, dong.bien_the, dong.so_luong
        )
        return {
            "ma_ctgh": dong.ma_ctgh,
            "bien_the": dong.bien_the,
            "so_luong": dong.so_luong,
            "con_ban": con_ban,
            "da_chon": da_chon,
            "loai_gia": loai_gia,
            "don_gia": don_gia,
            "thanh_tien": thanh_tien,
        }

    # ---------- M3-UC02: Xem giỏ hàng ----------
    @staticmethod
    def xem_gio_hang(khach_hang, ma_ctgh_da_chon=None):
        """
        UC02 bước 1–2: mọi dòng trong giỏ kèm giá. Tạm tính chỉ cộng các dòng
        vừa được tích chọn vừa còn bán. Giỏ trống -> danh sách rỗng (UC02-A2).
        """
        DichVuGioHang.kiem_tra_khach_hang(khach_hang)
        cac_ma_da_chon = set(ma_ctgh_da_chon or [])

        cac_dong = (
            ChiTietGioHang.objects
            .select_related("bien_the__san_pham")
            .filter(gio_hang__khach_hang=khach_hang)
            .order_by("ma_ctgh")
        )

        ket_qua = []
        tam_tinh = Decimal("0")

        for dong in cac_dong:
            con_ban = DichVuGioHang.bien_the_con_ban(dong.bien_the)
            # UC02-E3: dòng ngừng bán bị đánh dấu và không được tính là đã chọn
            da_chon = con_ban and dong.ma_ctgh in cac_ma_da_chon

            dong_gia = DichVuTinhTien.dong_kem_gia(khach_hang, dong, con_ban, da_chon)
            ket_qua.append(dong_gia)

            if da_chon:
                tam_tinh += dong_gia["thanh_tien"]

        return {"cac_dong": ket_qua, "tam_tinh": tam_tinh}

    # ---------- M3-UC02 bước 3: nhấn [Mua hàng] ----------
    @staticmethod
    def lay_cac_dong_da_chon(khach_hang, danh_sach_ma_ctgh):
        """
        Kiểm tra các dòng khách chọn để mua và trả về kèm giá tính lại.
        Dùng khi nhấn [Mua hàng] (UC02 bước 3), mở trang thanh toán và đặt hàng (UC03).
        """
        DichVuGioHang.kiem_tra_khach_hang(khach_hang)

        # dict.fromkeys bỏ mã bị gửi trùng mà vẫn giữ thứ tự
        cac_ma = list(dict.fromkeys(danh_sach_ma_ctgh or []))

        if not cac_ma:
            raise LoiNghiepVuDonHang("Vui lòng chọn sản phẩm cần mua.")  # UC02-E1

        ket_qua = []
        for ma_ctgh in cac_ma:
            dong = DichVuGioHang.lay_dong_cua_khach(khach_hang, ma_ctgh)  # M3-BR24

            if not DichVuGioHang.bien_the_con_ban(dong.bien_the):  # UC02-E3, UC03-E2
                raise LoiNghiepVuDonHang(
                    f"Sản phẩm \"{dong.bien_the.san_pham.ten_sp}\" hiện không được bán. "
                    "Vui lòng xóa khỏi giỏ hàng."
                )

            ket_qua.append(DichVuTinhTien.dong_kem_gia(khach_hang, dong, True, True))

        return ket_qua

    # ---------- M3-UC03 bước 1: các khoản tiền trên trang thanh toán ----------
    @staticmethod
    def tinh_tong_tien(khach_hang, danh_sach_ma_ctgh, ma_dia_chi):
        """
        M3-BR06: tổng thanh toán = tổng tiền hàng các dòng đã chọn + phí giao hàng.
        Không nhận số tiền nào từ trình duyệt; mọi con số tính lại tại đây.
        """
        cac_dong = DichVuTinhTien.lay_cac_dong_da_chon(khach_hang, danh_sach_ma_ctgh)
        giao_hang = DichVuDiaChiGiaoHang.chon_dia_chi(khach_hang, ma_dia_chi)

        tong_tien_hang = Decimal("0")
        for dong in cac_dong:
            tong_tien_hang += dong["thanh_tien"]

        phi_van_chuyen = Decimal(giao_hang["phi_van_chuyen"])

        return {
            "cac_dong": cac_dong,
            "dia_chi": giao_hang["dia_chi"],
            "tinh_thanh": giao_hang["tinh_thanh"],
            "tong_tien_hang": tong_tien_hang,
            "phi_van_chuyen": phi_van_chuyen,
            "tong_thanh_toan": tong_tien_hang + phi_van_chuyen,
        }


# ==========================================================
# 7. ĐẶT HÀNG – M3-UC03 bước 3–4
#    Quy tắc: M3-BR07 (chốt giá), M3-BR08 (bản sao địa chỉ), M3-BR09 (PTTT),
#    M3-BR10 (một giao dịch CSDL), M3-BR15 (lịch sử), M3-BR16 (bản ghi thanh toán).
# ==========================================================
class DichVuDatHang:

    # ---------- Kiểm tra phương thức thanh toán (UC03-E1) ----------
    @staticmethod
    def lay_phuong_thuc(ma_pttt):
        if not ma_pttt:
            raise LoiNghiepVuDonHang("Vui lòng chọn phương thức thanh toán.")

        phuong_thuc = PhuongThucThanhToan.objects.filter(
            ma_pttt=ma_pttt, dang_kich_hoat=True
        ).first()

        if phuong_thuc is None:
            raise LoiNghiepVuDonHang("Phương thức thanh toán không hợp lệ.")

        return phuong_thuc

    # ---------- Ghép địa chỉ để lưu bản sao vào đơn (M3-BR08) ----------
    @staticmethod
    def ghep_dia_chi(dia_chi):
        """Ví dụ: "12 Lê Lợi, Phường Thuận Hòa". Phần nào trống thì bỏ qua."""
        cac_phan = [dia_chi.dia_chi_chi_tiet, dia_chi.phuong_xa, dia_chi.quan_huyen]
        return ", ".join(phan.strip() for phan in cac_phan if phan and phan.strip())

    # ---------- Tạo bản ghi thanh toán đi kèm đơn (M3-BR16) ----------
    @staticmethod
    def tao_giao_dich_thanh_toan(don, thoi_diem):
        return GiaoDichThanhToan.objects.create(
            ma_giao_dich=sinh_ma(GiaoDichThanhToan),
            don_hang=don,
            phuong_thuc=don.phuong_thuc_thanh_toan,
            so_tien_phai_thu=don.tong_thanh_toan,
            trang_thai=TrangThaiThanhToan.CHUA_THANH_TOAN,
            thoi_diem_tao=thoi_diem,
        )

    # ---------- Loại các dòng đã đặt khỏi giỏ (M3-BR03, M3-BR10) ----------
    @staticmethod
    def loai_dong_khoi_gio(khach_hang, cac_ma_ctgh):
        so_dong_da_xoa, _ = ChiTietGioHang.objects.filter(
            gio_hang__khach_hang=khach_hang, ma_ctgh__in=cac_ma_ctgh
        ).delete()

        # Ít hơn số dòng cần xóa = có yêu cầu khác vừa đặt hoặc xóa các dòng này
        # (UC03-E6). Raise để transaction hoàn tác cả đơn vừa tạo.
        if so_dong_da_xoa != len(cac_ma_ctgh):
            raise LoiNghiepVuDonHang(
                "Giỏ hàng vừa thay đổi hoặc đơn hàng đã được đặt. Vui lòng kiểm tra lại."
            )

        gio = DichVuGioHang.lay_gio_hang(khach_hang)
        gio.save(update_fields=["ngay_cap_nhat"])

    # ---------- M3-UC03: Đặt hàng ----------
    @staticmethod
    def dat_hang(khach_hang, danh_sach_ma_ctgh, ma_dia_chi, ma_pttt):
        """
        Trả về DonHang vừa tạo. Mọi bước ghi nằm trong một transaction:
        lỗi ở bất kỳ bước nào thì không có gì được lưu (M3-BR10, UC03-E5).
        """
        phuong_thuc = DichVuDatHang.lay_phuong_thuc(ma_pttt)  # UC03-E1

        try:
            with transaction.atomic():
                # Bước 3: kiểm tra và tính lại toàn bộ tiền ở máy chủ
                # (BR01 khách hoạt động, UC03-E2 dòng ngừng bán, E3, E4, M3-BR24)
                tinh = DichVuTinhTien.tinh_tong_tien(khach_hang, danh_sach_ma_ctgh, ma_dia_chi)
                dia_chi = tinh["dia_chi"]
                bay_gio = timezone.now()  # một mốc chung cho đơn, lịch sử, giao dịch

                # Bước 4a: lưu đơn, chốt loại khách, người nhận, tỉnh, tiền
                don = DonHang.objects.create(
                    ma_dh=sinh_ma(DonHang),
                    khach_hang=khach_hang,
                    loai_khach_hang_ap_dung_id=khach_hang.loai_khach_hang_id,  # M3-BR02
                    ho_ten_nguoi_nhan=dia_chi.ten_nguoi_nhan.strip(),
                    sdt_nguoi_nhan=dia_chi.so_dien_thoai.strip(),
                    dia_chi_giao_hang=DichVuDatHang.ghep_dia_chi(dia_chi),
                    tinh_thanh=tinh["tinh_thanh"],
                    tong_tien_hang=tinh["tong_tien_hang"],
                    phi_van_chuyen=tinh["phi_van_chuyen"],
                    tong_thanh_toan=tinh["tong_thanh_toan"],
                    phuong_thuc_thanh_toan=phuong_thuc,
                    trang_thai_thanh_toan=TrangThaiThanhToan.CHUA_THANH_TOAN,
                    trang_thai=TrangThaiDonHang.CHO_XAC_NHAN,
                    ngay_dat=bay_gio,
                )

                # Bước 4b: lưu các dòng đơn với giá chốt tại lúc đặt (M3-BR07)
                for dong in tinh["cac_dong"]:
                    ChiTietDonHang.objects.create(
                        ma_ctdh=sinh_ma(ChiTietDonHang),
                        don_hang=don,
                        bien_the=dong["bien_the"],
                        so_luong=dong["so_luong"],
                        loai_gia_ap_dung=dong["loai_gia"],
                        don_gia=dong["don_gia"],
                        thanh_tien=dong["thanh_tien"],
                    )

                # Bước 4c: dòng lịch sử đầu tiên, chưa có trạng thái cũ (M3-BR15)
                LichSuTrangThaiDonHang.objects.create(
                    ma_lstt=sinh_ma(LichSuTrangThaiDonHang),
                    don_hang=don,
                    trang_thai_cu=None,
                    trang_thai=TrangThaiDonHang.CHO_XAC_NHAN,
                    thoi_diem=bay_gio,
                    tac_nhan=TacNhan.KHACH_HANG,
                    ghi_chu="Khách đặt hàng",
                )

                # Bước 4d: bản ghi thanh toán "Chưa thanh toán" (M3-BR16)
                DichVuDatHang.tao_giao_dich_thanh_toan(don, bay_gio)

                # Bước 4e: bỏ các dòng đã đặt khỏi giỏ; dòng không chọn vẫn ở lại
                cac_ma_ctgh = [dong["ma_ctgh"] for dong in tinh["cac_dong"]]
                DichVuDatHang.loai_dong_khoi_gio(khach_hang, cac_ma_ctgh)

        except DatabaseError as loi:
            # Lỗi CSDL bất kỳ (khóa CSDL, vi phạm CHECK, trùng mã...): transaction
            # đã hoàn tác, chỉ đổi thành câu báo cho khách (UC03-E5)
            raise LoiNghiepVuDonHang("Không thể đặt hàng, vui lòng thử lại.") from loi

        return don