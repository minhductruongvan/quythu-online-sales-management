# File: backend/orders/services.py
# Module 3 – Nghiệp vụ giỏ hàng, đặt hàng, xử lý đơn hàng
# Nội dung đã có:
#   1. Lỗi nghiệp vụ          2. Sinh mã khóa chính
#   3. Tra tỉnh/thành         4. Giỏ hàng (M3-UC01, M3-UC02)
#   5. Địa chỉ giao hàng (M3-UC04)
#   6. Tính giá và tính tiền (M3-UC02 phần hiển thị, M3-UC03 bước 1)
#   7. Đặt hàng (M3-UC03 bước 3–4)
#   8. Trang thanh toán (M3-UC02 bước 3, M3-UC03 bước 1, M3-UC04)
#   9. Máy trạng thái đơn hàng (M3-BR14, M3-BR15, M3-BR22)
#  10. Xử lý đơn phía nhân viên: kiểm tra hàng (M3-UC09), xác nhận đơn
#      (M3-UC08), xử lý thiếu hàng (M3-UC10)
#  11. Thanh toán (M3-UC11): cổng giả lập chuyển khoản, thu tiền COD,
#      hủy đơn quá hạn thanh toán, xét hoàn thành đơn (M3-BR22)
#  12. Chuẩn bị và bàn giao hàng (M3-UC12), giao lại cho M4
#  13. Giao thành công (M3-UC13), xác nhận đã nhận hàng (M3-UC06),
#      tự xác nhận sau 7 ngày, hủy đơn cho M4, tác vụ định kỳ
#  14. Theo dõi đơn của khách (M3-UC05), tra cứu đơn phía nhân viên (M3-UC07)
#
# Quy ước (theo M1 – customers/services.py):
# - View không tự xử lý nghiệp vụ, chỉ gọi hàm ở file này.
# - Vi phạm quy tắc nghiệp vụ thì raise LoiNghiepVuDonHang kèm câu báo lỗi
#   tiếng Việt; view bắt lỗi này và trả câu báo về cho người dùng.
# - Mọi số tiền dùng Decimal, không dùng float.

from datetime import timedelta
from decimal import Decimal

from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.db.models import Q
from django.utils import timezone

from customers.models import DiaChiKH

from .models import (
    ChiTietDonHang,
    ChiTietGioHang,
    DonHang,
    GiaoDichThanhToan,
    GiaoHang,
    GioHang,
    HinhThucGiao,
    KetQuaGiao,
    KetQuaKiemTra,
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
    GiaoHang: "GH",
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
# 3. TRA TỈNH/THÀNH TỪ ĐỊA CHỈ CỦA KHÁCH – M3-UC03 E4, M3-UC04, M3-BR05
#    DiaChiKH.tinh_thanh (M1) là ô chữ tự do, còn bảng phí là TinhThanh (M3).
#    So hai bên sau khi bỏ khoảng trắng thừa và đổi về chữ thường, nên địa chỉ
#    phải ghi đúng tên tỉnh như trong bảng ("Đà Nẵng", "TP. Hồ Chí Minh").
# ==========================================================
def chuan_hoa_ten_tinh(ten_tinh):
    """Ví dụ: "  ĐÀ   Nẵng " -> "đà nẵng"."""
    return " ".join((ten_tinh or "").split()).lower()


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
        # Serializer đã bảo đảm là số nguyên; ở đây chỉ còn quy tắc "> 0"
        if so_luong <= 0:
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
MA_LOAI_KHACH_SI = "LKH002"  # Khách tự chọn khi đăng ký; quản lý cũng có thể cập nhật.


class DichVuTinhTien:

    # ---------- Giá của một dòng ----------
    @staticmethod
    def la_khach_si(khach_hang):
        """Khách sỉ được phân loại khi đăng ký hoặc khi hồ sơ được cập nhật."""
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

        cac_ma = list(danh_sach_ma_ctgh or [])

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

# ==========================================================
# 8. TRANG THANH TOÁN – M3-UC02 bước 3, M3-UC03 bước 1, M3-UC04
#    Chỉ ĐỌC và TÍNH, không ghi gì vào CSDL (nhấn [Mua hàng] chưa làm đổi giỏ).
#    Địa chỉ đang chọn do trình duyệt gửi kèm mỗi lần gọi; không gửi thì dùng
#    địa chỉ hiển thị sẵn (UC04 bước 1). Không có API lưu "địa chỉ đã chọn".
# ==========================================================
class DichVuTrangThanhToan:

    @staticmethod
    def xem_trang_thanh_toan(khach_hang, danh_sach_ma_ctgh, ma_dia_chi=None):
        """
        Trả về dict của tinh_tong_tien, thêm khóa "cac_phuong_thuc"
        (các phương thức thanh toán đang kích hoạt để khách chọn ở bước 2).
        """
        # Bước 1: kiểm tra các dòng chọn mua TRƯỚC địa chỉ, để khách chưa chọn
        # dòng nào nhận đúng câu "Vui lòng chọn sản phẩm cần mua" (UC02-E1, E3)
        DichVuTinhTien.lay_cac_dong_da_chon(khach_hang, danh_sach_ma_ctgh)

        # Bước 2: chưa chọn địa chỉ -> địa chỉ hiển thị sẵn (UC04 bước 1, UC04-E1)
        if not ma_dia_chi:
            ma_dia_chi = DichVuDiaChiGiaoHang.lay_dia_chi_hien_thi_san(khach_hang).ma_dia_chi

        # Bước 3: tính tiền hàng, phí giao theo tỉnh, tổng thanh toán (UC03 bước 1)
        trang = DichVuTinhTien.tinh_tong_tien(khach_hang, danh_sach_ma_ctgh, ma_dia_chi)

        # Bước 4: danh sách phương thức thanh toán đang dùng được (M3-BR09)
        trang["cac_phuong_thuc"] = list(
            PhuongThucThanhToan.objects.filter(dang_kich_hoat=True).order_by("ma_pttt")
        )
        return trang

# ==========================================================
# 9. MÁY TRẠNG THÁI ĐƠN HÀNG (M3-BR14, M3-BR15, M3-BR22) – giai đoạn 4B
#    Bảng cạnh là nơi DUY NHẤT định nghĩa trạng thái nào được đi tới
#    trạng thái nào. Mọi hàm xử lý đơn ở giai đoạn 4 (xác nhận, chuẩn bị,
#    bàn giao, hủy...) đều đổi trạng thái qua DichVuTrangThai.chuyen_trang_thai.
#    Bảng cạnh trả lời "có đường này không"; điều kiện riêng của từng
#    thao tác (đã thanh toán chưa, có yêu cầu hủy không...) nằm ở hàm gọi.
# ==========================================================
T = TrangThaiDonHang

CAC_CANH_HOP_LE = {
    T.CHO_XAC_NHAN: {T.DA_XAC_NHAN, T.CHO_BO_SUNG, T.DA_HUY},
    T.DA_XAC_NHAN: {T.CHO_THANH_TOAN, T.DANG_CHUAN_BI, T.DA_HUY},
    T.CHO_THANH_TOAN: {T.DANG_CHUAN_BI, T.DA_HUY},
    T.DANG_CHUAN_BI: {T.SAN_SANG_GIAO, T.CHO_BO_SUNG, T.DA_HUY},
    T.CHO_BO_SUNG: {T.CHO_XAC_NHAN, T.DANG_CHUAN_BI, T.DA_HUY},
    T.SAN_SANG_GIAO: {T.DANG_GIAO, T.DA_HUY},
    T.DANG_GIAO: {T.GIAO_THANH_CONG, T.DA_HUY},
    T.GIAO_THANH_CONG: {T.HOAN_THANH},
    T.HOAN_THANH: set(),  # tập rỗng: trạng thái cuối, không đi đâu được nữa
    T.DA_HUY: set(),
}

TRANG_THAI_CUOI = {T.HOAN_THANH, T.DA_HUY}


def ten_trang_thai(ma):
    """Đổi mã sang nhãn tiếng Việt; mã lạ thì trả nguyên mã (để câu báo lỗi không tự gây lỗi)."""
    return dict(TrangThaiDonHang.choices).get(ma, ma)


class DichVuTrangThai:

    @staticmethod
    def co_the_chuyen(trang_thai_cu, trang_thai_moi):
        return trang_thai_moi in CAC_CANH_HOP_LE.get(trang_thai_cu, set())

    @staticmethod
    def ghi_lich_su(don, trang_thai_cu, trang_thai_moi, tac_nhan, nhan_vien=None, ghi_chu="", thoi_diem=None):
        """Thêm một dòng lịch sử (M3-BR15). Lịch sử chỉ được thêm, không có hàm sửa hay xóa.

        Gọi thẳng hàm này (không qua chuyen_trang_thai) chỉ khi thao tác không đổi
        trạng thái nhưng tài liệu yêu cầu ghi lịch sử: kiểm tra hàng (UC09),
        gia hạn hẹn (UC10-A1). Khi đó trang_thai_cu = trang_thai_moi.
        """
        return LichSuTrangThaiDonHang.objects.create(
            ma_lstt=sinh_ma(LichSuTrangThaiDonHang),
            don_hang=don,
            trang_thai_cu=trang_thai_cu,
            trang_thai=trang_thai_moi,
            thoi_diem=thoi_diem or timezone.now(),
            tac_nhan=tac_nhan,
            nhan_vien=nhan_vien,
            ghi_chu=ghi_chu or None,
        )

    @staticmethod
    def chuyen_trang_thai(don, trang_thai_moi, tac_nhan, nhan_vien=None, ghi_chu="",
                          thoi_diem=None, cap_nhat_them=None):
        """Chuyển đơn sang trạng thái mới và ghi lịch sử trong cùng một transaction.

        cap_nhat_them: dict các cột khác của đơn cần ghi cùng lúc, ví dụ
        {"thoi_diem_xac_nhan": bay_gio}. Ghi chung một lệnh UPDATE với trạng thái
        nên không có lúc nào đơn đổi trạng thái mà thiếu mốc thời gian.
        """
        trang_thai_cu = don.trang_thai

        # BR22: Hoàn thành, Đã hủy là trạng thái cuối
        if trang_thai_cu in TRANG_THAI_CUOI:
            raise LoiNghiepVuDonHang(
                f"Đơn hàng {don.ma_dh} đã ở trạng thái \"{ten_trang_thai(trang_thai_cu)}\", "
                "không thể xử lý thêm."
            )
        # BR14: chỉ đi theo cạnh có trong bảng, không nhảy cóc
        if not DichVuTrangThai.co_the_chuyen(trang_thai_cu, trang_thai_moi):
            raise LoiNghiepVuDonHang(
                f"Không thể chuyển đơn hàng từ \"{ten_trang_thai(trang_thai_cu)}\" "
                f"sang \"{ten_trang_thai(trang_thai_moi)}\"."
            )

        thoi_diem = thoi_diem or timezone.now()
        cac_cot = {"trang_thai": trang_thai_moi}
        cac_cot.update(cap_nhat_them or {})

        with transaction.atomic():
            # Compare-and-set: chỉ cập nhật nếu trạng thái trong CSDL vẫn là trạng thái
            # mình đã đọc. Hai nhân viên bấm cùng lúc thì người sau nhận 0 dòng (UC08 E1).
            so_dong = DonHang.objects.filter(ma_dh=don.ma_dh, trang_thai=trang_thai_cu).update(**cac_cot)
            if so_dong == 0:
                raise LoiNghiepVuDonHang(
                    "Đơn hàng vừa được người khác xử lý, vui lòng tải lại đơn."
                )
            DichVuTrangThai.ghi_lich_su(
                don, trang_thai_cu, trang_thai_moi, tac_nhan,
                nhan_vien=nhan_vien, ghi_chu=ghi_chu, thoi_diem=thoi_diem,
            )

        # .update() ghi thẳng xuống CSDL, không đụng tới đối tượng `don` trong bộ nhớ;
        # gán lại để hàm gọi tiếp (ví dụ chuyển tiếp sang Chờ thanh toán) thấy giá trị mới
        for ten_cot, gia_tri in cac_cot.items():
            setattr(don, ten_cot, gia_tri)
        return don


# ==========================================================
# 10. XỬ LÝ ĐƠN PHÍA NHÂN VIÊN – giai đoạn 4C
#     M3-UC09 kiểm tra khả năng cung ứng, M3-UC08 xác nhận đơn,
#     M3-UC10 xử lý thiếu hàng (chờ bổ sung, gia hạn, đã đủ hàng).
#     Quy tắc: M3-BR11, BR12, BR13, BR14, BR15, BR19.
#     Mọi thao tác theo cùng một khuôn: kiểm tra điều kiện trước,
#     rồi ghi trong transaction.atomic(); lỗi CSDL thì báo và giữ nguyên đơn.
# ==========================================================
GOI_Y_HEN_CUNG_CAP = timedelta(days=1)  # BR13: hẹn 1–2 ngày; giao diện đặt sẵn bây giờ + 1 ngày
MA_HAU_MAI_CHO_HUY = "CHO_HUY"          # M4 ghi vào trang_thai_hau_mai khi khách gửi yêu cầu hủy
CAU_LOI_LUU = "Không thể lưu thao tác, vui lòng thử lại."


class DichVuXuLyDon:

    # ----- Các bước kiểm tra dùng chung -----
    @staticmethod
    def kiem_tra_trang_thai(don, cac_trang_thai, thao_tac):
        """Đơn phải đang ở một trong các trạng thái cho phép thao tác này."""
        if don.trang_thai not in cac_trang_thai:
            raise LoiNghiepVuDonHang(
                f"Không thể {thao_tac} khi đơn hàng đang ở trạng thái \"{ten_trang_thai(don.trang_thai)}\"."
            )

    @staticmethod
    def kiem_tra_khong_cho_huy(don):
        """M3-BR19: đơn có yêu cầu hủy đang chờ M4 xử lý thì không xác nhận, chuẩn bị, bàn giao."""
        if don.trang_thai_hau_mai == MA_HAU_MAI_CHO_HUY:
            raise LoiNghiepVuDonHang("Đơn hàng đang có yêu cầu hủy chờ xử lý, không thể thực hiện thao tác này.")

    @staticmethod
    def kiem_tra_hen_tuong_lai(thoi_diem_hen):
        """M3-UC10 E1: thời điểm hẹn cung cấp phải ở tương lai."""
        if thoi_diem_hen <= timezone.now():
            raise LoiNghiepVuDonHang("Thời điểm hẹn cung cấp phải ở tương lai.")

    # ----- M3-UC09: kiểm tra khả năng cung ứng -----
    @staticmethod
    def kiem_tra_kha_nang_cung_ung(don, nhan_vien, ket_qua, ghi_chu=""):
        """Ghi kết quả kiểm tra hàng thực tế cho từng dòng của đơn.

        ket_qua: dict {ma_ctdh: so_luong_thieu}. 0 là đủ hàng; lớn hơn 0 là thiếu
        (A1: thiếu một phần số lượng vẫn tính là thiếu). Trả về True nếu mọi dòng đủ.
        """
        DichVuXuLyDon.kiem_tra_trang_thai(
            don, {T.CHO_XAC_NHAN, T.DANG_CHUAN_BI}, "kiểm tra khả năng cung ứng"
        )
        cac_ma_dong = set(don.chi_tiet.values_list("ma_ctdh", flat=True))
        if set(ket_qua) - cac_ma_dong:
            raise LoiNghiepVuDonHang(f"Có dòng hàng không thuộc đơn {don.ma_dh}.")
        if cac_ma_dong - set(ket_qua):  # E1
            raise LoiNghiepVuDonHang("Còn dòng hàng chưa được đánh dấu, vui lòng hoàn tất kiểm tra.")

        so_dong_thieu = sum(1 for so_thieu in ket_qua.values() if so_thieu > 0)
        ket_luan = "đủ hàng" if so_dong_thieu == 0 else f"thiếu hàng ở {so_dong_thieu} dòng"
        try:
            with transaction.atomic():
                for ma_ctdh, so_thieu in ket_qua.items():
                    ChiTietDonHang.objects.filter(ma_ctdh=ma_ctdh).update(
                        ket_qua_kiem_tra=KetQuaKiemTra.THIEU if so_thieu > 0 else KetQuaKiemTra.DU,
                        so_luong_thieu=so_thieu,
                    )
                # Dòng lịch sử giữ nguyên trạng thái: ghi người và thời điểm kiểm tra
                DichVuTrangThai.ghi_lich_su(
                    don, don.trang_thai, don.trang_thai, TacNhan.NHAN_VIEN,
                    nhan_vien=nhan_vien, ghi_chu=f"Kiểm tra hàng: {ket_luan}. {ghi_chu}".strip(),
                )
        except DatabaseError as loi:  # E2 (kể cả số lượng thiếu lớn hơn số lượng đặt)
            raise LoiNghiepVuDonHang(CAU_LOI_LUU) from loi
        return so_dong_thieu == 0

    # ----- M3-UC08: xác nhận đơn -----
    @staticmethod
    def xac_nhan_don(don, nhan_vien, ghi_chu=""):
        DichVuXuLyDon.kiem_tra_trang_thai(don, {T.CHO_XAC_NHAN}, "xác nhận đơn")
        DichVuXuLyDon.kiem_tra_khong_cho_huy(don)  # E2
        # BR12: chỉ xác nhận sau khi đã kiểm tra và mọi dòng đều đủ hàng
        if don.chi_tiet.exclude(ket_qua_kiem_tra=KetQuaKiemTra.DU).exists():
            raise LoiNghiepVuDonHang("Chỉ xác nhận được đơn đã kiểm tra và đủ hàng ở mọi dòng.")

        bay_gio = timezone.now()
        try:
            with transaction.atomic():
                DichVuTrangThai.chuyen_trang_thai(
                    don, T.DA_XAC_NHAN, TacNhan.NHAN_VIEN, nhan_vien=nhan_vien,
                    ghi_chu=ghi_chu, thoi_diem=bay_gio,
                    cap_nhat_them={"nhan_vien_xac_nhan": nhan_vien, "thoi_diem_xac_nhan": bay_gio},
                )
                # Chuyển khoản: hệ thống chuyển tiếp sang Chờ thanh toán trong cùng transaction.
                # COD dừng ở Đã xác nhận, chờ nhân viên bấm [Bắt đầu chuẩn bị] (UC12).
                if don.phuong_thuc_thanh_toan_id == PhuongThucThanhToan.MA_CHUYEN_KHOAN:
                    DichVuTrangThai.chuyen_trang_thai(
                        don, T.CHO_THANH_TOAN, TacNhan.HE_THONG,
                        ghi_chu="Chờ khách thanh toán chuyển khoản.", thoi_diem=bay_gio,
                    )
        except DatabaseError as loi:  # E4
            raise LoiNghiepVuDonHang(CAU_LOI_LUU) from loi
        return don

    # ----- M3-UC10: xử lý thiếu hàng -----
    @staticmethod
    def chuyen_cho_bo_sung(don, nhan_vien, thoi_diem_hen, ghi_chu=""):
        DichVuXuLyDon.kiem_tra_trang_thai(
            don, {T.CHO_XAC_NHAN, T.DANG_CHUAN_BI}, "chuyển chờ bổ sung hàng"
        )  # E2
        if not don.chi_tiet.filter(ket_qua_kiem_tra=KetQuaKiemTra.THIEU).exists():
            raise LoiNghiepVuDonHang("Chỉ chuyển chờ bổ sung hàng khi kết quả kiểm tra có dòng thiếu hàng.")
        DichVuXuLyDon.kiem_tra_hen_tuong_lai(thoi_diem_hen)  # E1

        try:
            # Lưu trạng thái hiện tại để [Đã đủ hàng] đưa đơn quay lại đúng bước
            DichVuTrangThai.chuyen_trang_thai(
                don, T.CHO_BO_SUNG, TacNhan.NHAN_VIEN, nhan_vien=nhan_vien, ghi_chu=ghi_chu,
                cap_nhat_them={
                    "thoi_diem_hen_cung_cap": thoi_diem_hen,
                    "trang_thai_truoc_cho_bo_sung": don.trang_thai,
                },
            )
        except DatabaseError as loi:  # E3
            raise LoiNghiepVuDonHang(CAU_LOI_LUU) from loi
        return don

    @staticmethod
    def gia_han_hen(don, nhan_vien, thoi_diem_hen_moi, ghi_chu=""):
        """A1: đổi thời điểm hẹn, trạng thái giữ nguyên Chờ bổ sung hàng, ghi lịch sử."""
        DichVuXuLyDon.kiem_tra_trang_thai(don, {T.CHO_BO_SUNG}, "gia hạn hẹn cung cấp")
        DichVuXuLyDon.kiem_tra_hen_tuong_lai(thoi_diem_hen_moi)

        hen_moi = timezone.localtime(thoi_diem_hen_moi).strftime("%d/%m/%Y %H:%M")
        try:
            with transaction.atomic():
                DonHang.objects.filter(ma_dh=don.ma_dh).update(thoi_diem_hen_cung_cap=thoi_diem_hen_moi)
                DichVuTrangThai.ghi_lich_su(
                    don, T.CHO_BO_SUNG, T.CHO_BO_SUNG, TacNhan.NHAN_VIEN, nhan_vien=nhan_vien,
                    ghi_chu=f"Gia hạn hẹn cung cấp đến {hen_moi}. {ghi_chu}".strip(),
                )
        except DatabaseError as loi:
            raise LoiNghiepVuDonHang(CAU_LOI_LUU) from loi
        don.thoi_diem_hen_cung_cap = thoi_diem_hen_moi
        return don

    @staticmethod
    def da_du_hang(don, nhan_vien, ghi_chu=""):
        """Bước 4: hàng đã về, đơn quay về trạng thái trước khi chờ bổ sung."""
        DichVuXuLyDon.kiem_tra_trang_thai(don, {T.CHO_BO_SUNG}, "xác nhận đã đủ hàng")

        try:
            with transaction.atomic():
                # Các dòng thiếu nay đã đủ, để bước sau (xác nhận, chuẩn bị) không bị chặn
                don.chi_tiet.filter(ket_qua_kiem_tra=KetQuaKiemTra.THIEU).update(
                    ket_qua_kiem_tra=KetQuaKiemTra.DU, so_luong_thieu=0
                )
                DichVuTrangThai.chuyen_trang_thai(
                    don, don.trang_thai_truoc_cho_bo_sung, TacNhan.NHAN_VIEN,
                    nhan_vien=nhan_vien, ghi_chu=ghi_chu or "Đã đủ hàng.",
                    cap_nhat_them={"trang_thai_truoc_cho_bo_sung": None},
                )
        except DatabaseError as loi:  # E3
            raise LoiNghiepVuDonHang(CAU_LOI_LUU) from loi
        return don


# ==========================================================
# 11. THANH TOÁN – M3-UC11 (giai đoạn 4D)
#     Chuyển khoản: khách trả qua cổng thanh toán giả lập (thay cho việc
#     nhân viên đối soát). COD: nhân viên ghi nhận đã thu sau khi giao.
#     Quy tắc: M3-BR16 (bản ghi thanh toán), BR17 (24 giờ), BR18 (COD), BR22.
#     Thanh toán chỉ đổi trang_thai_thanh_toan, không đổi trạng thái xử lý
#     của đơn; vì vậy không ghi lịch sử trạng thái (trừ khi đơn hoàn thành).
# ==========================================================
THOI_HAN_THANH_TOAN = timedelta(hours=24)  # BR17, tính từ thoi_diem_xac_nhan
MA_HAU_MAI_CHO_DOI_TRA = "CHO_DOI_TRA"      # M4 ghi khi có yêu cầu đổi/trả đang mở
CHUA_TRA_TIEN = [TrangThaiThanhToan.CHUA_THANH_TOAN, TrangThaiThanhToan.THAT_BAI]


class DichVuThanhToan:

    @staticmethod
    def lay_giao_dich(don):
        """Bản ghi thanh toán tạo lúc đặt hàng (BR16: mỗi đơn một bản ghi)."""
        return don.giao_dich_thanh_toan.first()

    @staticmethod
    def kiem_tra_chua_thanh_toan(don):
        """E3: đơn đã ghi nhận thanh toán thì không ghi trùng."""
        if don.trang_thai_thanh_toan == TrangThaiThanhToan.DA_THANH_TOAN:
            raise LoiNghiepVuDonHang(f"Đơn hàng {don.ma_dh} đã được thanh toán trước đó.")

    @staticmethod
    def ghi_da_thanh_toan(don, so_tien_thuc_nhan, thoi_diem, nhan_vien=None,
                          ma_giao_dich_ngan_hang=None, ghi_chu=""):
        """Ghi "Đã thanh toán" vào giao dịch gốc và vào đơn. Gọi bên trong transaction.atomic()."""
        # Compare-and-set như máy trạng thái: hai yêu cầu cùng lúc thì yêu cầu sau nhận 0 dòng
        so_dong = DonHang.objects.filter(
            ma_dh=don.ma_dh, trang_thai_thanh_toan__in=CHUA_TRA_TIEN
        ).update(trang_thai_thanh_toan=TrangThaiThanhToan.DA_THANH_TOAN)
        if so_dong == 0:
            raise LoiNghiepVuDonHang(f"Đơn hàng {don.ma_dh} đã được thanh toán trước đó.")
        GiaoDichThanhToan.objects.filter(
            ma_giao_dich=DichVuThanhToan.lay_giao_dich(don).ma_giao_dich
        ).update(
            trang_thai=TrangThaiThanhToan.DA_THANH_TOAN,
            so_tien_thuc_nhan=so_tien_thuc_nhan,
            thoi_diem_thanh_toan=thoi_diem,
            nhan_vien_ghi_nhan=nhan_vien,
            ma_giao_dich_ngan_hang=ma_giao_dich_ngan_hang,
            ghi_chu=ghi_chu or None,
        )
        don.trang_thai_thanh_toan = TrangThaiThanhToan.DA_THANH_TOAN

    # ----- Chuyển khoản qua cổng giả lập -----
    @staticmethod
    def thanh_toan_gia_lap(don, khach_hang, thanh_cong):
        """Khách bấm thanh toán trên cổng giả lập; thanh_cong=False giả lập ngân hàng từ chối."""
        if don.khach_hang_id != khach_hang.ma_kh:  # BR24
            raise LoiQuyenDonHang("Bạn không có quyền thao tác trên đơn hàng này.")
        if don.phuong_thuc_thanh_toan_id != PhuongThucThanhToan.MA_CHUYEN_KHOAN:
            raise LoiNghiepVuDonHang("Đơn hàng này không thanh toán bằng chuyển khoản.")
        DichVuThanhToan.kiem_tra_chua_thanh_toan(don)  # E3
        DichVuXuLyDon.kiem_tra_trang_thai(don, {T.CHO_THANH_TOAN}, "thanh toán")  # E1
        DichVuXuLyDon.kiem_tra_khong_cho_huy(don)
        if don.thoi_diem_xac_nhan + THOI_HAN_THANH_TOAN <= timezone.now():  # A2
            DichVuThanhToan.huy_don_qua_han_thanh_toan()
            raise LoiNghiepVuDonHang(f"Đơn hàng {don.ma_dh} đã quá hạn thanh toán và bị hủy.")

        bay_gio = timezone.now()
        try:
            with transaction.atomic():
                if thanh_cong:
                    DichVuThanhToan.ghi_da_thanh_toan(
                        don, DichVuThanhToan.lay_giao_dich(don).so_tien_phai_thu, bay_gio,
                        ma_giao_dich_ngan_hang=f"GL{bay_gio:%Y%m%d%H%M%S}{don.ma_dh}",
                    )
                else:
                    # Giao dịch gốc giữ "Chưa thanh toán"; khách được thử lại trong hạn
                    DonHang.objects.filter(ma_dh=don.ma_dh).update(
                        trang_thai_thanh_toan=TrangThaiThanhToan.THAT_BAI
                    )
                    don.trang_thai_thanh_toan = TrangThaiThanhToan.THAT_BAI
        except DatabaseError as loi:  # E4
            raise LoiNghiepVuDonHang(CAU_LOI_LUU) from loi
        return don

    # ----- COD: nhân viên ghi nhận đã thu tiền -----
    @staticmethod
    def ghi_nhan_thu_cod(don, nhan_vien, so_tien_thuc_nhan, ghi_chu=""):
        if don.phuong_thuc_thanh_toan_id != PhuongThucThanhToan.MA_COD:
            raise LoiNghiepVuDonHang("Đơn hàng này không thanh toán khi nhận hàng (COD).")
        DichVuThanhToan.kiem_tra_chua_thanh_toan(don)  # E3
        DichVuXuLyDon.kiem_tra_trang_thai(don, {T.GIAO_THANH_CONG}, "ghi nhận thu tiền COD")  # E1, BR18

        so_tien_phai_thu = DichVuThanhToan.lay_giao_dich(don).so_tien_phai_thu
        if so_tien_thuc_nhan < so_tien_phai_thu:  # E2: nhận thiếu thì chưa ghi "Đã thanh toán"
            raise LoiNghiepVuDonHang(
                f"Số tiền thực nhận ít hơn số tiền phải thu ({so_tien_phai_thu} đ), "
                "chưa thể ghi nhận đã thanh toán."
            )
        if so_tien_thuc_nhan > so_tien_phai_thu:  # E2: nhận thừa thì ghi chú để M4 hoàn phần thừa
            ghi_chu = f"Nhận thừa {so_tien_thuc_nhan - so_tien_phai_thu} đ, chờ hoàn phần thừa. {ghi_chu}".strip()

        try:
            with transaction.atomic():
                DichVuThanhToan.ghi_da_thanh_toan(
                    don, so_tien_thuc_nhan, timezone.now(), nhan_vien=nhan_vien, ghi_chu=ghi_chu
                )
                DichVuThanhToan.xet_hoan_thanh(don)  # bước 3: đủ điều kiện thì "Hoàn thành"
        except DatabaseError as loi:  # E4
            raise LoiNghiepVuDonHang(CAU_LOI_LUU) from loi
        return don

    @staticmethod
    def ghi_nhan_chuyen_khoan(don, nhan_vien, so_tien_thuc_nhan, ma_giao_dich_ngan_hang,
                              ghi_chu="", ly_do_dieu_chinh=""):
        """Đối soát chuyển khoản hoặc đính chính bản ghi trước đó (M3-UC11)."""
        if don.phuong_thuc_thanh_toan_id != PhuongThucThanhToan.MA_CHUYEN_KHOAN:
            raise LoiNghiepVuDonHang("Đơn hàng này không thanh toán bằng chuyển khoản.")
        da_thanh_toan = don.trang_thai_thanh_toan == TrangThaiThanhToan.DA_THANH_TOAN
        if don.trang_thai == T.DA_HUY and not da_thanh_toan:
            raise LoiNghiepVuDonHang("Không thể ghi nhận thanh toán cho đơn đã hủy.")

        giao_dich = DichVuThanhToan.lay_giao_dich(don)
        if giao_dich is None:
            raise LoiNghiepVuDonHang("Không tìm thấy giao dịch thanh toán của đơn hàng.")
        ma_giao_dich_ngan_hang = (ma_giao_dich_ngan_hang or "").strip()
        if not ma_giao_dich_ngan_hang:
            raise LoiNghiepVuDonHang("Vui lòng nhập mã giao dịch ngân hàng.")
        if GiaoDichThanhToan.objects.filter(
            ma_giao_dich_ngan_hang=ma_giao_dich_ngan_hang,
        ).exclude(ma_giao_dich=giao_dich.ma_giao_dich).exists():
            raise LoiNghiepVuDonHang("Mã giao dịch ngân hàng đã được ghi nhận.")

        so_tien_thuc_nhan = Decimal(so_tien_thuc_nhan)
        if so_tien_thuc_nhan < giao_dich.so_tien_phai_thu:
            raise LoiNghiepVuDonHang(
                f"Số tiền thực nhận thấp hơn số tiền phải thu ({giao_dich.so_tien_phai_thu} đ)."
            )

        bay_gio = timezone.now()
        try:
            with transaction.atomic():
                if da_thanh_toan:
                    ly_do = (ly_do_dieu_chinh or "").strip()
                    if not ly_do:
                        raise LoiNghiepVuDonHang("Vui lòng nhập lý do đính chính ghi nhận thanh toán.")
                    ghi_chu_dieu_chinh = (
                        f"Đính chính {giao_dich.so_tien_thuc_nhan}/{giao_dich.ma_giao_dich_ngan_hang or '—'} "
                        f"thành {so_tien_thuc_nhan}/{ma_giao_dich_ngan_hang}. Lý do: {ly_do}. {ghi_chu}"
                    ).strip()
                    if len(ghi_chu_dieu_chinh) > 255:
                        raise LoiNghiepVuDonHang("Rút gọn ghi chú hoặc lý do đính chính để lưu được lịch sử.")
                    giao_dich.so_tien_thuc_nhan = so_tien_thuc_nhan
                    giao_dich.ma_giao_dich_ngan_hang = ma_giao_dich_ngan_hang
                    giao_dich.nhan_vien_ghi_nhan = nhan_vien
                    giao_dich.thoi_diem_thanh_toan = bay_gio
                    giao_dich.ghi_chu = ghi_chu_dieu_chinh
                    giao_dich.save(update_fields=[
                        "so_tien_thuc_nhan", "ma_giao_dich_ngan_hang", "nhan_vien_ghi_nhan",
                        "thoi_diem_thanh_toan", "ghi_chu",
                    ])
                    DichVuTrangThai.ghi_lich_su(
                        don, don.trang_thai, don.trang_thai, TacNhan.NHAN_VIEN,
                        nhan_vien=nhan_vien, ghi_chu=ghi_chu_dieu_chinh,
                    )
                else:
                    DichVuXuLyDon.kiem_tra_trang_thai(don, {T.CHO_THANH_TOAN}, "ghi nhận thanh toán")
                    ghi_chu_thanh_toan = ghi_chu
                    if so_tien_thuc_nhan > giao_dich.so_tien_phai_thu:
                        ghi_chu_thanh_toan = (
                            f"Nhận thừa {so_tien_thuc_nhan - giao_dich.so_tien_phai_thu} đ, "
                            f"chờ hoàn phần thừa. {ghi_chu}"
                        ).strip()
                    DichVuThanhToan.ghi_da_thanh_toan(
                        don,
                        so_tien_thuc_nhan,
                        bay_gio,
                        nhan_vien=nhan_vien,
                        ma_giao_dich_ngan_hang=ma_giao_dich_ngan_hang,
                        ghi_chu=ghi_chu_thanh_toan,
                    )
                    DichVuTrangThai.ghi_lich_su(
                        don, don.trang_thai, don.trang_thai, TacNhan.NHAN_VIEN,
                        nhan_vien=nhan_vien,
                        ghi_chu=f"Đã ghi nhận chuyển khoản {ma_giao_dich_ngan_hang}. {ghi_chu}".strip(),
                    )
        except DatabaseError as loi:
            raise LoiNghiepVuDonHang(CAU_LOI_LUU) from loi
        return don

    # ----- Hủy đơn chuyển khoản quá hạn (A2, tác vụ định kỳ) -----
    @staticmethod
    def huy_don_qua_han_thanh_toan():
        """Hủy mọi đơn chuyển khoản ở "Chờ thanh toán" chưa trả tiền quá 24 giờ.

        Chỉ lọc đơn chưa xử lý nên chạy lại nhiều lần không đổi kết quả. Trả về số đơn đã hủy.
        """
        bay_gio = timezone.now()
        cac_don = DonHang.objects.filter(
            phuong_thuc_thanh_toan_id=PhuongThucThanhToan.MA_CHUYEN_KHOAN,
            trang_thai=T.CHO_THANH_TOAN,
            trang_thai_thanh_toan__in=CHUA_TRA_TIEN,
            thoi_diem_xac_nhan__lte=bay_gio - THOI_HAN_THANH_TOAN,
        )
        so_don = 0
        for don in cac_don:
            DichVuTrangThai.chuyen_trang_thai(
                don, T.DA_HUY, TacNhan.HE_THONG,
                ghi_chu="Quá hạn thanh toán 24 giờ, hệ thống tự hủy.", thoi_diem=bay_gio,
            )
            so_don += 1
        return so_don

    # ----- Xét hoàn thành đơn (M3-BR22) -----
    @staticmethod
    def xet_hoan_thanh(don):
        """Chuyển "Hoàn thành" nếu đủ 3 điều kiện; trả về True nếu đã chuyển.

        Được gọi sau mỗi sự kiện có thể làm đơn đủ điều kiện: thu tiền COD (UC11),
        khách xác nhận đã nhận (UC06), hệ thống tự xác nhận sau 7 ngày, M4 đóng đổi/trả.
        """
        du_dieu_kien = (
            don.trang_thai == T.GIAO_THANH_CONG
            and don.thoi_diem_xac_nhan_nhan_hang is not None          # cửa sổ đổi/trả đã đóng
            and don.trang_thai_hau_mai != MA_HAU_MAI_CHO_DOI_TRA       # không còn đổi/trả đang mở
            and don.trang_thai_thanh_toan == TrangThaiThanhToan.DA_THANH_TOAN  # COD đã thu
        )
        if not du_dieu_kien:
            return False
        bay_gio = timezone.now()
        DichVuTrangThai.chuyen_trang_thai(
            don, T.HOAN_THANH, TacNhan.HE_THONG, ghi_chu="Đơn đủ điều kiện hoàn thành.",
            thoi_diem=bay_gio, cap_nhat_them={"thoi_diem_hoan_thanh": bay_gio},
        )
        return True


# ==========================================================
# 12. CHUẨN BỊ VÀ BÀN GIAO HÀNG – M3-UC12 (giai đoạn 4E)
#     Đã xác nhận / Chờ thanh toán → Đang chuẩn bị hàng → Sẵn sàng giao
#     → Đang giao (tạo bản ghi GiaoHang lần 1). Giao lại do M4 yêu cầu
#     tạo bản ghi giao mới trên cùng đơn, đơn vẫn "Đang giao".
#     Quy tắc: M3-BR15 (mốc bắt đầu chuẩn bị ghi một lần), BR17, BR18,
#     BR19 (chặn khi có yêu cầu hủy), BR20 (hình thức giao, lần giao).
# ==========================================================
DON_VI_XE_NOI_BO = "Xe nội bộ Quý Thu"


class DichVuGiaoHang:

    @staticmethod
    def goi_y_hinh_thuc_giao(don):
        """BR20: khách sỉ gợi ý xe tải, khách lẻ gợi ý shipper; nhân viên được đổi."""
        if don.loai_khach_hang_ap_dung_id == MA_LOAI_KHACH_SI:
            return HinhThucGiao.XE_TAI
        return HinhThucGiao.SHIPPER

    @staticmethod
    def kiem_tra_thong_tin_giao(hinh_thuc_giao, don_vi_van_chuyen):
        """E3: bắt buộc chọn hình thức giao. Trả về tên đơn vị vận chuyển sẽ lưu."""
        if hinh_thuc_giao not in HinhThucGiao.values:
            raise LoiNghiepVuDonHang("Vui lòng chọn hình thức giao trước khi bàn giao.")
        if not don_vi_van_chuyen:
            if hinh_thuc_giao != HinhThucGiao.XE_TAI:
                raise LoiNghiepVuDonHang("Vui lòng nhập đơn vị vận chuyển.")
            don_vi_van_chuyen = DON_VI_XE_NOI_BO
        return don_vi_van_chuyen

    # ----- Bước 1: bắt đầu chuẩn bị -----
    @staticmethod
    def bat_dau_chuan_bi(don, nhan_vien, ghi_chu=""):
        DichVuXuLyDon.kiem_tra_trang_thai(don, {T.DA_XAC_NHAN, T.CHO_THANH_TOAN}, "bắt đầu chuẩn bị hàng")  # E4
        if (don.phuong_thuc_thanh_toan_id == PhuongThucThanhToan.MA_CHUYEN_KHOAN
                and don.trang_thai_thanh_toan != TrangThaiThanhToan.DA_THANH_TOAN):  # E1, BR17
            raise LoiNghiepVuDonHang("Đơn chuyển khoản chưa được thanh toán, chưa thể bắt đầu chuẩn bị hàng.")
        DichVuXuLyDon.kiem_tra_khong_cho_huy(don)  # E2, BR19

        cap_nhat = {}
        if don.thoi_diem_bat_dau_chuan_bi is None:  # BR15: mốc này chỉ ghi một lần
            cap_nhat["thoi_diem_bat_dau_chuan_bi"] = timezone.now()
        try:
            DichVuTrangThai.chuyen_trang_thai(
                don, T.DANG_CHUAN_BI, TacNhan.NHAN_VIEN, nhan_vien=nhan_vien,
                ghi_chu=ghi_chu, cap_nhat_them=cap_nhat,
            )
        except DatabaseError as loi:
            raise LoiNghiepVuDonHang(CAU_LOI_LUU) from loi
        return don

    # ----- Bước 2: sẵn sàng giao -----
    @staticmethod
    def san_sang_giao(don, nhan_vien, ghi_chu=""):
        DichVuXuLyDon.kiem_tra_trang_thai(don, {T.DANG_CHUAN_BI}, "chuyển sẵn sàng giao")  # E4
        try:
            DichVuTrangThai.chuyen_trang_thai(don, T.SAN_SANG_GIAO, TacNhan.NHAN_VIEN,
                                              nhan_vien=nhan_vien, ghi_chu=ghi_chu)
        except DatabaseError as loi:
            raise LoiNghiepVuDonHang(CAU_LOI_LUU) from loi
        return don

    # ----- Bước 3–4: bàn giao vận chuyển -----
    @staticmethod
    def ban_giao(don, nhan_vien, hinh_thuc_giao, don_vi_van_chuyen="", sdt_shipper="",
                 ma_van_don="", ghi_chu=""):
        DichVuXuLyDon.kiem_tra_trang_thai(don, {T.SAN_SANG_GIAO}, "bàn giao vận chuyển")  # E4
        DichVuXuLyDon.kiem_tra_khong_cho_huy(don)  # E2, BR19
        don_vi_van_chuyen = DichVuGiaoHang.kiem_tra_thong_tin_giao(hinh_thuc_giao, don_vi_van_chuyen)  # E3

        bay_gio = timezone.now()
        try:
            with transaction.atomic():
                DichVuTrangThai.chuyen_trang_thai(
                    don, T.DANG_GIAO, TacNhan.NHAN_VIEN, nhan_vien=nhan_vien, ghi_chu=ghi_chu,
                    thoi_diem=bay_gio, cap_nhat_them={"thoi_diem_ban_giao": bay_gio},
                )
                GiaoHang.objects.create(
                    ma_giao_hang=sinh_ma(GiaoHang),
                    don_hang=don,
                    lan_giao=1,
                    hinh_thuc_giao=hinh_thuc_giao,
                    don_vi_van_chuyen=don_vi_van_chuyen,
                    sdt_shipper=sdt_shipper or None,
                    ma_van_don=ma_van_don or None,
                    thoi_diem_ban_giao=bay_gio,
                )
        except DatabaseError as loi:  # E5
            raise LoiNghiepVuDonHang(CAU_LOI_LUU) from loi
        return don

    @staticmethod
    def lay_lan_giao_hien_tai(don):
        """Bản ghi giao có số lần giao lớn nhất của đơn."""
        return don.giao_hang.order_by("-lan_giao").first()

    # ----- A2: giao lại theo yêu cầu của M4 -----
    @staticmethod
    def tao_lan_giao_lai(don, nhan_vien, ket_qua_lan_truoc, ly_do, hinh_thuc_giao,
                         don_vi_van_chuyen="", sdt_shipper="", ma_van_don=""):
        """M4 gọi hàm này khi quyết định giao lại.

        Đóng lần giao hiện tại với kết quả THAT_BAI hoặc KHACH_TU_CHOI kèm lý do,
        rồi tạo lần giao mới. Đơn giữ "Đang giao", số lần giao lại tăng 1 (tối đa 2).
        """
        DichVuXuLyDon.kiem_tra_trang_thai(don, {T.DANG_GIAO}, "tạo lần giao lại")
        if ket_qua_lan_truoc not in (KetQuaGiao.THAT_BAI, KetQuaGiao.KHACH_TU_CHOI):
            raise LoiNghiepVuDonHang("Kết quả lần giao trước phải là thất bại hoặc khách từ chối nhận.")
        if don.so_lan_giao_lai >= GiaoHang.SO_LAN_GIAO_TOI_DA - 1:
            raise LoiNghiepVuDonHang(f"Đơn hàng {don.ma_dh} đã giao lại tối đa {GiaoHang.SO_LAN_GIAO_TOI_DA - 1} lần.")
        don_vi_van_chuyen = DichVuGiaoHang.kiem_tra_thong_tin_giao(hinh_thuc_giao, don_vi_van_chuyen)

        lan_hien_tai = DichVuGiaoHang.lay_lan_giao_hien_tai(don)
        bay_gio = timezone.now()
        try:
            with transaction.atomic():
                GiaoHang.objects.filter(ma_giao_hang=lan_hien_tai.ma_giao_hang).update(
                    ket_qua_giao=ket_qua_lan_truoc,
                    ly_do_that_bai=ly_do or None,
                    thoi_diem_giao_xong=bay_gio,
                    nhan_vien_xac_nhan=nhan_vien,
                )
                GiaoHang.objects.create(
                    ma_giao_hang=sinh_ma(GiaoHang),
                    don_hang=don,
                    lan_giao=lan_hien_tai.lan_giao + 1,
                    hinh_thuc_giao=hinh_thuc_giao,
                    don_vi_van_chuyen=don_vi_van_chuyen,
                    sdt_shipper=sdt_shipper or None,
                    ma_van_don=ma_van_don or None,
                    thoi_diem_ban_giao=bay_gio,
                )
                # Mốc bàn giao trên đơn giữ lần đầu (BR19: M4 dựa vào mốc này để xét hủy)
                DonHang.objects.filter(ma_dh=don.ma_dh).update(so_lan_giao_lai=don.so_lan_giao_lai + 1)
        except DatabaseError as loi:
            raise LoiNghiepVuDonHang(CAU_LOI_LUU) from loi
        don.so_lan_giao_lai += 1
        return don


# ==========================================================
# 13. GIAO THÀNH CÔNG, NHẬN HÀNG, HỦY ĐƠN – giai đoạn 4F
#     M3-UC13 ghi nhận giao thành công (mở cửa sổ đổi/trả 7 ngày),
#     M3-UC06 khách xác nhận đã nhận hàng (đóng cửa sổ), hệ thống tự xác
#     nhận khi hết 7 ngày, hàm hủy đơn để M4 gọi, và tác vụ định kỳ.
#     Quy tắc: M3-BR14, BR15, BR20, BR21 (cửa sổ 7 ngày), BR22, BR24.
#     Cửa sổ đổi/trả "đóng" khi thoi_diem_xac_nhan_nhan_hang khác null.
# ==========================================================
CUA_SO_DOI_TRA = timedelta(days=7)  # BR21, tính từ thoi_diem_giao_thanh_cong


class DichVuKetThucDon:

    # ----- M3-UC13: ghi nhận giao thành công -----
    @staticmethod
    def giao_thanh_cong(don, nhan_vien, thoi_diem_giao=None, ghi_chu=""):
        DichVuXuLyDon.kiem_tra_trang_thai(don, {T.DANG_GIAO}, "ghi nhận giao thành công")  # E1
        bay_gio = timezone.now()
        thoi_diem_giao = thoi_diem_giao or bay_gio  # mặc định là thời điểm hiện tại
        lan_giao = DichVuGiaoHang.lay_lan_giao_hien_tai(don)
        if thoi_diem_giao > bay_gio:  # E2
            raise LoiNghiepVuDonHang("Thời điểm giao không được ở tương lai.")
        if thoi_diem_giao < lan_giao.thoi_diem_ban_giao:  # E2: so với lần giao hiện tại
            raise LoiNghiepVuDonHang("Thời điểm giao không được trước thời điểm bàn giao.")

        try:
            with transaction.atomic():
                DichVuTrangThai.chuyen_trang_thai(
                    don, T.GIAO_THANH_CONG, TacNhan.NHAN_VIEN, nhan_vien=nhan_vien, ghi_chu=ghi_chu,
                    thoi_diem=bay_gio, cap_nhat_them={"thoi_diem_giao_thanh_cong": thoi_diem_giao},
                )
                # Đóng lần giao hiện tại với kết quả thành công
                GiaoHang.objects.filter(ma_giao_hang=lan_giao.ma_giao_hang).update(
                    ket_qua_giao=KetQuaGiao.THANH_CONG,
                    thoi_diem_giao_xong=thoi_diem_giao,
                    nhan_vien_xac_nhan=nhan_vien,
                )
        except DatabaseError as loi:  # E4
            raise LoiNghiepVuDonHang(CAU_LOI_LUU) from loi
        return don

    # ----- M3-UC06: khách xác nhận đã nhận hàng -----
    @staticmethod
    def khach_xac_nhan_da_nhan(don, khach_hang):
        if don.khach_hang_id != khach_hang.ma_kh:  # E3, BR24
            raise LoiQuyenDonHang("Bạn không có quyền thao tác trên đơn hàng này.")
        if don.thoi_diem_xac_nhan_nhan_hang is not None:  # E1: cửa sổ đã đóng
            raise LoiNghiepVuDonHang("Đơn đã được xác nhận nhận hàng.")
        DichVuXuLyDon.kiem_tra_trang_thai(don, {T.GIAO_THANH_CONG}, "xác nhận đã nhận hàng")  # E2
        if don.thoi_diem_giao_thanh_cong + CUA_SO_DOI_TRA <= timezone.now():
            # Hết 7 ngày nhưng tác vụ định kỳ chưa chạy: chạy ngay để kết quả giống nhau
            DichVuKetThucDon.tu_xac_nhan_nhan_hang()
            raise LoiNghiepVuDonHang("Đơn đã được xác nhận nhận hàng.")

        bay_gio = timezone.now()
        try:
            with transaction.atomic():
                # Compare-and-set: một đơn chỉ đóng cửa sổ một lần
                so_dong = DonHang.objects.filter(
                    ma_dh=don.ma_dh, trang_thai=T.GIAO_THANH_CONG, thoi_diem_xac_nhan_nhan_hang__isnull=True
                ).update(thoi_diem_xac_nhan_nhan_hang=bay_gio)
                if so_dong == 0:
                    raise LoiNghiepVuDonHang("Đơn đã được xác nhận nhận hàng.")
                don.thoi_diem_xac_nhan_nhan_hang = bay_gio
                DichVuThanhToan.xet_hoan_thanh(don)  # bước 3: đủ điều kiện thì "Hoàn thành"
        except DatabaseError as loi:  # E4
            raise LoiNghiepVuDonHang(CAU_LOI_LUU) from loi
        return don

    # ----- M3-UC13 A2: hệ thống tự xác nhận khi hết cửa sổ 7 ngày (tác vụ định kỳ) -----
    @staticmethod
    def tu_xac_nhan_nhan_hang():
        """Đóng cửa sổ của mọi đơn "Giao thành công" đã quá 7 ngày mà khách chưa xác nhận.

        Mốc đóng cửa sổ là đúng thời điểm hết hạn, không phụ thuộc lúc tác vụ chạy.
        Chỉ lọc đơn chưa đóng nên chạy lại nhiều lần không đổi kết quả. Trả về số đơn đã xử lý.
        """
        cac_don = DonHang.objects.filter(
            trang_thai=T.GIAO_THANH_CONG,
            thoi_diem_xac_nhan_nhan_hang__isnull=True,
            thoi_diem_giao_thanh_cong__lte=timezone.now() - CUA_SO_DOI_TRA,
        )
        so_don = 0
        for don in cac_don:
            het_han = don.thoi_diem_giao_thanh_cong + CUA_SO_DOI_TRA
            with transaction.atomic():
                DonHang.objects.filter(ma_dh=don.ma_dh).update(
                    thoi_diem_xac_nhan_nhan_hang=het_han, xac_nhan_tu_dong=True
                )
                don.thoi_diem_xac_nhan_nhan_hang = het_han
                don.xac_nhan_tu_dong = True
                # COD chưa thu tiền hoặc còn đổi/trả đang mở thì đơn giữ "Giao thành công"
                DichVuThanhToan.xet_hoan_thanh(don)
            so_don += 1
        return so_don

    # ----- Hủy đơn: M4 gọi khi duyệt yêu cầu hủy hoặc quyết định hủy sau giao thất bại -----
    @staticmethod
    def huy_don(don, nhan_vien=None, ghi_chu="", ket_qua_lan_giao=KetQuaGiao.THAT_BAI):
        """Chuyển đơn sang "Đã hủy" (BR22). M3 chỉ chặn những gì bảng cạnh chặn:
        trạng thái cuối và "Giao thành công" không có cạnh sang "Đã hủy".

        Đơn đang giao thì đóng luôn lần giao hiện tại với ket_qua_lan_giao
        (THAT_BAI hoặc KHACH_TU_CHOI), lý do lấy từ ghi_chu.
        Điều kiện được hủy (chưa bàn giao, giao thất bại...) do M4 kiểm tra trước khi gọi.
        """
        dang_giao = don.trang_thai == T.DANG_GIAO
        if dang_giao and ket_qua_lan_giao not in (KetQuaGiao.THAT_BAI, KetQuaGiao.KHACH_TU_CHOI):
            raise LoiNghiepVuDonHang("Kết quả lần giao trước phải là thất bại hoặc khách từ chối nhận.")

        bay_gio = timezone.now()
        tac_nhan = TacNhan.NHAN_VIEN if nhan_vien else TacNhan.HE_THONG
        try:
            with transaction.atomic():
                DichVuTrangThai.chuyen_trang_thai(
                    don, T.DA_HUY, tac_nhan, nhan_vien=nhan_vien, ghi_chu=ghi_chu, thoi_diem=bay_gio,
                )
                if dang_giao:
                    lan_giao = DichVuGiaoHang.lay_lan_giao_hien_tai(don)
                    GiaoHang.objects.filter(ma_giao_hang=lan_giao.ma_giao_hang).update(
                        ket_qua_giao=ket_qua_lan_giao,
                        ly_do_that_bai=ghi_chu or None,
                        thoi_diem_giao_xong=bay_gio,
                        nhan_vien_xac_nhan=nhan_vien,
                    )
        except DatabaseError as loi:
            raise LoiNghiepVuDonHang(CAU_LOI_LUU) from loi
        return don

    # ----- Tác vụ định kỳ: lệnh xu_ly_don_dinh_ky và đầu các API danh sách đơn gọi hàm này -----
    @staticmethod
    def chay_tac_vu_dinh_ky():
        """BR17 (hủy đơn quá hạn thanh toán 24 giờ) và BR21 (tự xác nhận sau 7 ngày)."""
        return {
            "so_don_huy_qua_han": DichVuThanhToan.huy_don_qua_han_thanh_toan(),
            "so_don_tu_xac_nhan": DichVuKetThucDon.tu_xac_nhan_nhan_hang(),
        }


# ==========================================================
# 14. THEO DÕI VÀ TRA CỨU ĐƠN HÀNG – giai đoạn 4G
#     M3-UC05 (khách xem đơn của mình), M3-UC07 (nhân viên tìm, lọc, xem đơn).
#     Chỉ ĐỌC dữ liệu. Trước khi đọc, chạy tác vụ định kỳ (UC11 A2, UC13 A2)
#     để trạng thái hiển thị luôn đúng dù lệnh định kỳ chưa chạy theo lịch.
#     Quy tắc: M3-BR13, BR17 (thông tin chuyển khoản), BR21 (cửa sổ 7 ngày),
#     BR23 (hai trục trạng thái), BR24 (khách chỉ xem đơn của mình).
# ==========================================================
SO_DON_MOI_TRANG = 20  # UC07: danh sách nhân viên có phân trang


class DichVuTraCuuDon:

    @staticmethod
    def lay_don(ma_dh):
        """Lấy một đơn theo mã sau khi chạy tác vụ định kỳ; không có thì báo lỗi."""
        DichVuKetThucDon.chay_tac_vu_dinh_ky()
        don = DonHang.objects.filter(ma_dh=ma_dh).first()
        if don is None:
            raise LoiNghiepVuDonHang(f"Không tìm thấy đơn hàng {ma_dh}.")
        return don

    # ----- M3-UC05: phía khách hàng -----
    @staticmethod
    def danh_sach_don_cua_khach(khach_hang, trang_thai=None):
        """Bước 1–2: các đơn của khách, mới nhất trước; lọc theo trạng thái nếu có."""
        DichVuKetThucDon.chay_tac_vu_dinh_ky()
        cac_don = DonHang.objects.filter(khach_hang=khach_hang)
        if trang_thai:
            cac_don = cac_don.filter(trang_thai=trang_thai)
        return cac_don.order_by("-ngay_dat", "-ma_dh")

    @staticmethod
    def chi_tiet_don_cua_khach(khach_hang, ma_dh):
        """Bước 3. E2: đơn không thuộc khách thì từ chối (BR24)."""
        don = DichVuTraCuuDon.lay_don(ma_dh)
        if don.khach_hang_id != khach_hang.ma_kh:
            raise LoiQuyenDonHang("Bạn không có quyền xem đơn hàng này.")
        return don

    @staticmethod
    def thong_tin_chuyen_khoan(don):
        """BR17: thông tin để hiện mã QR, chỉ có khi đơn chuyển khoản đang chờ khách trả tiền."""
        if not (don.phuong_thuc_thanh_toan_id == PhuongThucThanhToan.MA_CHUYEN_KHOAN
                and don.trang_thai == T.CHO_THANH_TOAN
                and don.trang_thai_thanh_toan in CHUA_TRA_TIEN):
            return None
        return {
            "so_tien": don.tong_thanh_toan,
            "noi_dung": don.ma_dh,
            "tai_khoan": don.phuong_thuc_thanh_toan.thong_tin_tai_khoan,
            "han_thanh_toan": don.thoi_diem_xac_nhan + THOI_HAN_THANH_TOAN,
        }

    @staticmethod
    def han_cua_so_doi_tra(don):
        """BR21: cửa sổ đang mở thì trả thời điểm hết hạn (giao diện hiện [Đã nhận hàng]
        và [Yêu cầu đổi/trả]); cửa sổ chưa mở hoặc đã đóng thì trả None."""
        if don.trang_thai == T.GIAO_THANH_CONG and don.thoi_diem_xac_nhan_nhan_hang is None:
            return don.thoi_diem_giao_thanh_cong + CUA_SO_DOI_TRA
        return None

    # ----- M3-UC07: phía nhân viên -----
    @staticmethod
    def tra_cuu_don(tu_khoa="", trang_thai=None, tu_ngay=None, den_ngay=None, ma_loai_kh=None, trang=1):
        """Tìm theo mã đơn, tên khách, tên người nhận, số điện thoại; lọc theo trạng thái,
        khoảng ngày đặt, loại khách áp dụng. Trả về một trang kết quả (Page của Django)."""
        DichVuKetThucDon.chay_tac_vu_dinh_ky()
        cac_don = DonHang.objects.select_related("khach_hang")
        tu_khoa = (tu_khoa or "").strip()
        if tu_khoa:
            cac_don = cac_don.filter(
                Q(ma_dh__icontains=tu_khoa)
                | Q(khach_hang__ho_ten__icontains=tu_khoa)
                | Q(ho_ten_nguoi_nhan__icontains=tu_khoa)
                | Q(sdt_nguoi_nhan__icontains=tu_khoa)
                | Q(khach_hang__so_dien_thoai__icontains=tu_khoa)
            )
        if trang_thai:
            cac_don = cac_don.filter(trang_thai=trang_thai)
        if tu_ngay:
            cac_don = cac_don.filter(ngay_dat__date__gte=tu_ngay)
        if den_ngay:
            cac_don = cac_don.filter(ngay_dat__date__lte=den_ngay)
        if ma_loai_kh:
            cac_don = cac_don.filter(loai_khach_hang_ap_dung_id=ma_loai_kh)
        # get_page: số trang sai hoặc vượt quá thì trả trang gần nhất, không báo lỗi
        return Paginator(cac_don.order_by("-ngay_dat", "-ma_dh"), SO_DON_MOI_TRANG).get_page(trang)