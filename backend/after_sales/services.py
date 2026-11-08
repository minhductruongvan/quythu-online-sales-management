# File: backend/after_sales/services.py
# Module 4 – Nghiệp vụ hậu mãi: hủy đơn, giao không thành công, đổi/trả, hoàn tiền,
# danh mục nguyên nhân, thống kê, lịch sử và timeline.
#
# Quy ước (theo M1, M3):
# - View không tự xử lý nghiệp vụ, chỉ gọi hàm ở file này.
# - Vi phạm quy tắc nghiệp vụ thì raise LoiNghiepVuHauMai kèm câu báo lỗi tiếng Việt.
# - M4 KHÔNG sửa code M3. Muốn đổi đơn gốc, M4 gọi hàm M3 đã mở sẵn:
#     DichVuKetThucDon.huy_don, DichVuGiaoHang.tao_lan_giao_lai,
#     DichVuThanhToan.xet_hoan_thanh, DichVuTraCuuDon.han_cua_so_doi_tra.
# - Ngoài ra M4 chỉ ghi duy nhất cột DonHang.trang_thai_hau_mai (M3 chừa cho M4).
# - Mọi thao tác ghi nhiều bảng chạy trong transaction.atomic(); lỗi thì hoàn tác toàn bộ.
# - Mọi số tiền dùng Decimal.

import base64
import csv
import hashlib
import io
import json
from datetime import timedelta
from decimal import Decimal

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.paginator import Paginator
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Count, Max, Q, Sum
from django.utils import timezone

from orders.models import (
    ChiTietDonHang,
    DonHang,
    GiaoDichThanhToan,
    GiaoHang,
    KetQuaGiao,
    LoaiGia,
    PhuongThucThanhToan,
    TacNhan,
    TrangThaiDonHang,
    TrangThaiThanhToan,
)
from orders.services import (
    MA_HAU_MAI_CHO_DOI_TRA,
    MA_HAU_MAI_CHO_HUY,
    DichVuGiaoHang,
    DichVuKetThucDon,
    DichVuThanhToan,
    DichVuTraCuuDon,
    LoiNghiepVuDonHang,
    LoiQuyenDonHang,
)

from .models import (
    TRANG_THAI_DOI_TRA_GIU_SO_LUONG,
    AnhMinhChung,
    BenChiuPhi,
    BienDongKho,
    DongDoiTra,
    GiaoDichHoanTien,
    HinhThucDoiTra,
    HuongXuLyGiao,
    KetQuaKiemTraTra,
    KhoNhap,
    LichSuHauMai,
    LichSuNguyenNhan,
    LoaiXuLy,
    LoaiYeuCau,
    LyDoBienDongKho,
    NguyenNhan,
    NguonHoanTien,
    PhuongThucHoan,
    ThongBaoHauMai,
    TrangThaiDoiTra,
    TrangThaiHoanTien,
    TrangThaiYeuCauHuy,
    XuLyGiaoThatBai,
    YeuCauDoiTra,
    YeuCauHuy,
)


# ==========================================================
# 1. LỖI NGHIỆP VỤ
#    Kế thừa lỗi của M3 để view chỉ cần bắt một loại lỗi, cả khi hàm M3 báo lỗi.
# ==========================================================
class LoiNghiepVuHauMai(LoiNghiepVuDonHang):
    """Vi phạm quy tắc nghiệp vụ của M4."""


class LoiQuyenHauMai(LoiNghiepVuHauMai):
    """Không có quyền thao tác trên yêu cầu hoặc đơn hàng."""


CAU_LOI_LUU = "Không thể lưu thao tác, vui lòng thử lại."
SO_DONG_MOI_TRANG = 20  # UC09: phân trang 20 dòng/trang

# ----- Giá trị DonHang.trang_thai_hau_mai (khớp NHAN_HAU_MAI trong orders/serializers.py) -----
HM_CHO_HUY = MA_HAU_MAI_CHO_HUY
HM_CHO_DOI_TRA = MA_HAU_MAI_CHO_DOI_TRA
HM_CHO_GIAO_LAI = "CHO_GIAO_LAI"
HM_DANG_HOAN_VE_KHO = "DANG_HOAN_VE_KHO"
HM_DA_HOAN_HANG = "DA_HOAN_HANG"
HM_DA_DOI_TRA = "DA_DOI_TRA"
HM_DA_HOAN_TIEN = "DA_HOAN_TIEN"

T = TrangThaiDonHang

# M4-BR01: đơn chưa giao cho đơn vị vận chuyển mới được yêu cầu hủy.
# CHO_THANH_TOAN là trạng thái M3 thêm cho đơn chuyển khoản; tài liệu M4 chưa liệt kê.
# ĐANG GIẢ ĐỊNH cho phép hủy (đơn chưa giao). Nếu nhóm chốt khác, chỉ cần bỏ dòng này.
TRANG_THAI_DUOC_HUY = {T.CHO_XAC_NHAN, T.DA_XAC_NHAN, T.CHO_THANH_TOAN, T.DANG_CHUAN_BI, T.CHO_BO_SUNG}

HAN_GUI_HANG_DOI_TRA = timedelta(days=7)   # M4-BR16
HAN_XU_LY_HUY = timedelta(hours=24)        # UC02 "nhắc yêu cầu quá hạn": ngưỡng 24 giờ chờ nhóm xác nhận
SO_LAN_GIAO_TOI_DA = GiaoHang.SO_LAN_GIAO_TOI_DA  # M4-BR05: 3 lần

# Các trạng thái yêu cầu đổi/trả còn đang mở
DOI_TRA_DANG_MO = [
    TrangThaiDoiTra.CHO_XU_LY, TrangThaiDoiTra.DA_DUYET,
    TrangThaiDoiTra.DANG_CHO_NHAN_HANG, TrangThaiDoiTra.DA_NHAN_HANG,
]


# ==========================================================
# 2. SINH MÃ KHÓA CHÍNH (theo cách M1, M3: đếm + 1, trùng thì tăng tiếp)
# ==========================================================
TIEN_TO_MA = {
    NguyenNhan: "NN",
    LichSuNguyenNhan: "LN",
    YeuCauHuy: "YH",
    XuLyGiaoThatBai: "XT",
    YeuCauDoiTra: "DT",
    DongDoiTra: "DD",
    AnhMinhChung: "AM",
    GiaoDichHoanTien: "HT",
    BienDongKho: "BD",
    LichSuHauMai: "LH",
    ThongBaoHauMai: "TB",
}


def sinh_ma(model):
    """Trả về mã chưa dùng cho model, ví dụ sinh_ma(YeuCauHuy) -> "YH001"."""
    tien_to = TIEN_TO_MA[model]
    ten_khoa_chinh = model._meta.pk.name
    so_thu_tu = model.objects.count() + 1
    while True:
        ma = f"{tien_to}{so_thu_tu:03d}"
        if not model.objects.filter(**{ten_khoa_chinh: ma}).exists():
            return ma
        so_thu_tu += 1


# ==========================================================
# 3. HÀM DÙNG CHUNG: đơn gốc, timeline, thông báo
# ==========================================================
def lay_don(ma_dh):
    don = DonHang.objects.filter(ma_dh=ma_dh).first()
    if don is None:
        raise LoiNghiepVuHauMai(f"Không tìm thấy đơn hàng {ma_dh}.")
    return don


def lay_don_cua_khach(ma_dh, khach_hang):
    """Đơn phải thuộc khách hàng (M4-BR12, quyền kiểm tra ở máy chủ)."""
    don = lay_don(ma_dh)
    if don.khach_hang_id != khach_hang.ma_kh:
        raise LoiQuyenHauMai("Bạn không có quyền thao tác trên đơn hàng này.")
    return don


def dat_hau_mai(don, gia_tri):
    """Ghi DonHang.trang_thai_hau_mai (cột duy nhất M4 được ghi trực tiếp lên đơn gốc)."""
    DonHang.objects.filter(ma_dh=don.ma_dh).update(trang_thai_hau_mai=gia_tri)
    don.trang_thai_hau_mai = gia_tri


def hau_mai_sau_khi_dong_doi_tra(don, hau_mai_truoc):
    """Khi một yêu cầu đổi/trả đóng (thu hồi, từ chối, hết hạn): còn yêu cầu khác đang mở thì giữ
    "Chờ đổi/trả"; không còn thì trả về giá trị trước đó (bỏ "Chờ đổi/trả")."""
    con_mo = YeuCauDoiTra.objects.filter(don_hang=don, trang_thai__in=DOI_TRA_DANG_MO).exists()
    if con_mo:
        return HM_CHO_DOI_TRA
    return None if hau_mai_truoc == HM_CHO_DOI_TRA else hau_mai_truoc


def ghi_moc(don, loai, ma_yeu_cau, moc, trang_thai, tac_nhan, nhan_vien=None,
            ghi_chu=None, ghi_chu_noi_bo=None, thoi_diem=None, anh=None):
    """M4-BR13: thêm một mốc timeline. Chỉ thêm, không có hàm sửa hay xóa."""
    return LichSuHauMai.objects.create(
        ma_lich_su=sinh_ma(LichSuHauMai), don_hang=don, loai_yeu_cau=loai, ma_yeu_cau=ma_yeu_cau,
        moc=moc, trang_thai=trang_thai, tac_nhan=tac_nhan, nhan_vien=nhan_vien,
        thoi_diem=thoi_diem or timezone.now(), ghi_chu=ghi_chu or None,
        ghi_chu_noi_bo=ghi_chu_noi_bo or None, anh_minh_chung=anh,
    )


class DichVuThongBao:
    """M4-BR18: thông báo cho khách và nhân viên."""

    @staticmethod
    def gui_khach(don, tieu_de, noi_dung):
        return ThongBaoHauMai.objects.create(
            ma_thong_bao=sinh_ma(ThongBaoHauMai), khach_hang_id=don.khach_hang_id, nhan_vien_chung=False,
            don_hang=don, tieu_de=tieu_de, noi_dung=noi_dung[:500],
        )

    @staticmethod
    def gui_nhan_vien(don, tieu_de, noi_dung):
        return ThongBaoHauMai.objects.create(
            ma_thong_bao=sinh_ma(ThongBaoHauMai), khach_hang=None, nhan_vien_chung=True,
            don_hang=don, tieu_de=tieu_de, noi_dung=noi_dung[:500],
        )

    @staticmethod
    def cua_khach(khach_hang, chi_chua_doc=False):
        ds = ThongBaoHauMai.objects.filter(khach_hang=khach_hang)
        return ds.filter(da_doc=False) if chi_chua_doc else ds

    @staticmethod
    def cua_nhan_vien(chi_chua_doc=False):
        ds = ThongBaoHauMai.objects.filter(nhan_vien_chung=True)
        return ds.filter(da_doc=False) if chi_chua_doc else ds

    @staticmethod
    def danh_dau_da_doc(ma_thong_bao, khach_hang=None):
        """Khách chỉ đánh dấu được thông báo của mình; nhân viên đánh dấu thông báo chung."""
        ds = ThongBaoHauMai.objects.filter(ma_thong_bao=ma_thong_bao)
        ds = ds.filter(khach_hang=khach_hang) if khach_hang else ds.filter(nhan_vien_chung=True)
        if ds.update(da_doc=True) == 0:
            raise LoiNghiepVuHauMai("Không tìm thấy thông báo.")


# ==========================================================
# 4. MÃ HÓA THÔNG TIN TÀI KHOẢN NHẬN HOÀN TIỀN (UC06 phi chức năng)
#    Khóa lấy từ settings.HAU_MAI_KHOA_MA_HOA, nếu chưa khai báo thì dùng SECRET_KEY.
# ==========================================================
def _fernet():
    khoa = getattr(settings, "HAU_MAI_KHOA_MA_HOA", None) or settings.SECRET_KEY
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(khoa.encode("utf-8")).digest()))


def ma_hoa(van_ban):
    return _fernet().encrypt(van_ban.encode("utf-8")).decode("ascii")


def giai_ma(ma_hoa_van_ban):
    try:
        return _fernet().decrypt(ma_hoa_van_ban.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return ""


def che_bot(van_ban):
    """Chỉ để lộ 4 ký tự cuối, ví dụ ****6789."""
    if not van_ban:
        return None
    return "*" * max(len(van_ban) - 4, 0) + van_ban[-4:]


def tai_khoan_nhan_da_che(khoan):
    if not khoan.thong_tin_tai_khoan_nhan:
        return None
    return che_bot(giai_ma(khoan.thong_tin_tai_khoan_nhan))


# ==========================================================
# 5. KHO (M4-BR04, M4-BR17)
#    M1–M3 chưa có bảng tồn kho, nên M4 ghi sổ BienDongKho. Khi nhóm có bảng tồn kho thật,
#    chỉ sửa hàm ghi_nhan (và con_hang) ở đây; các nơi gọi không phải đổi.
# ==========================================================
class DichVuKho:

    @staticmethod
    def ghi_nhan(don, bien_the, so_luong, kho, ly_do, ma_yeu_cau=None, nhan_vien=None):
        return BienDongKho.objects.create(
            ma_bien_dong=sinh_ma(BienDongKho), don_hang=don, bien_the=bien_the, so_luong=so_luong,
            kho=kho, ly_do=ly_do, ma_yeu_cau=ma_yeu_cau, nhan_vien=nhan_vien,
        )

    @staticmethod
    def hoan_toan_bo_don(don, ly_do, ma_yeu_cau=None, nhan_vien=None):
        """Hủy đơn hoặc hoàn hàng về kho: cộng lại toàn bộ số lượng vào kho bán."""
        for dong in ChiTietDonHang.objects.filter(don_hang=don).select_related("bien_the"):
            DichVuKho.ghi_nhan(don, dong.bien_the, dong.so_luong, KhoNhap.KHO_BAN, ly_do, ma_yeu_cau, nhan_vien)

    @staticmethod
    def con_hang(bien_the, so_luong):
        """M4-BR17: sản phẩm đổi phải còn đủ tồn kho. Hiện chỉ kiểm tra biến thể còn bán (ACTIVE),
        vì chưa có bảng tồn kho để so số lượng."""
        return bien_the.trang_thai == "ACTIVE"


# ==========================================================
# 6. DANH MỤC NGUYÊN NHÂN – M4-UC07 (M4-BR02, M4-BR10, M4-BR13)
# ==========================================================
class DichVuNguyenNhan:

    @staticmethod
    def so_lan_su_dung(nn):
        return (YeuCauHuy.objects.filter(nguyen_nhan=nn).count()
                + YeuCauDoiTra.objects.filter(nguyen_nhan=nn).count()
                + XuLyGiaoThatBai.objects.filter(nguyen_nhan=nn).count())

    @staticmethod
    def danh_sach(loai_xu_ly=None, dang_ap_dung=None):
        ds = NguyenNhan.objects.all()
        if loai_xu_ly:
            ds = ds.filter(loai_xu_ly=loai_xu_ly)
        if dang_ap_dung is not None:
            ds = ds.filter(dang_ap_dung=dang_ap_dung)
        return ds

    @staticmethod
    def lay_nguyen_nhan_ap_dung(ma_nguyen_nhan, loai_xu_ly, cau_thieu="Vui lòng chọn nguyên nhân."):
        """M4-BR02: chỉ chọn nguyên nhân đang áp dụng của đúng loại xử lý."""
        if not ma_nguyen_nhan:
            raise LoiNghiepVuHauMai(cau_thieu)
        nn = NguyenNhan.objects.filter(
            ma_nguyen_nhan=ma_nguyen_nhan, loai_xu_ly=loai_xu_ly, dang_ap_dung=True
        ).first()
        if nn is None:
            raise LoiNghiepVuHauMai("Nguyên nhân không hợp lệ hoặc đã ngưng sử dụng.")
        return nn

    @staticmethod
    def kiem_tra_ghi_chu(nn, ghi_chu):
        """M4-BR02: nguyên nhân "Khác" (bat_buoc_ghi_chu) bắt buộc nhập ghi chú mô tả lý do."""
        if nn.bat_buoc_ghi_chu and not (ghi_chu or "").strip():
            raise LoiNghiepVuHauMai("Vui lòng nhập ghi chú mô tả lý do.")

    # ----- ghi lịch sử (BR13) -----
    @staticmethod
    def _chup(nn):
        return json.dumps({
            "loai_xu_ly": nn.loai_xu_ly, "ten_nguyen_nhan": nn.ten_nguyen_nhan, "mo_ta": nn.mo_ta,
            "thu_tu_hien_thi": nn.thu_tu_hien_thi, "bat_buoc_anh": nn.bat_buoc_anh,
            "bat_buoc_ghi_chu": nn.bat_buoc_ghi_chu, "loi_do_cua_hang": nn.loi_do_cua_hang,
            "dang_ap_dung": nn.dang_ap_dung,
        }, ensure_ascii=False)

    @staticmethod
    def _ghi_lich_su(ma, hanh_dong, tai_khoan, cu, moi):
        LichSuNguyenNhan.objects.create(
            ma_lich_su=sinh_ma(LichSuNguyenNhan), ma_nguyen_nhan=ma, hanh_dong=hanh_dong,
            nguoi_thuc_hien=tai_khoan, gia_tri_cu=cu, gia_tri_moi=moi,
        )

    @staticmethod
    def _kiem_tra_du_lieu(loai_xu_ly, ten, mo_ta, bo_qua_ma=None):
        ten = (ten or "").strip()
        if not ten:
            raise LoiNghiepVuHauMai("Tên nguyên nhân không được để trống.")
        if len(ten) > 100:
            raise LoiNghiepVuHauMai("Tên nguyên nhân tối đa 100 ký tự.")
        if mo_ta and len(mo_ta) > 255:
            raise LoiNghiepVuHauMai("Mô tả tối đa 255 ký tự.")
        if loai_xu_ly not in LoaiXuLy.values:
            raise LoiNghiepVuHauMai("Loại xử lý không hợp lệ.")
        trung = NguyenNhan.objects.filter(loai_xu_ly=loai_xu_ly, ten_nguyen_nhan__iexact=ten)
        if bo_qua_ma:
            trung = trung.exclude(ma_nguyen_nhan=bo_qua_ma)
        if trung.exists():
            raise LoiNghiepVuHauMai("Tên nguyên nhân đã tồn tại trong loại xử lý này.")  # BR10
        return ten

    @staticmethod
    def them(tai_khoan, loai_xu_ly, ten_nguyen_nhan, mo_ta="", thu_tu_hien_thi=0,
             bat_buoc_anh=False, bat_buoc_ghi_chu=False, loi_do_cua_hang=False):
        ten = DichVuNguyenNhan._kiem_tra_du_lieu(loai_xu_ly, ten_nguyen_nhan, mo_ta)
        try:
            with transaction.atomic():
                nn = NguyenNhan.objects.create(
                    ma_nguyen_nhan=sinh_ma(NguyenNhan), loai_xu_ly=loai_xu_ly, ten_nguyen_nhan=ten,
                    mo_ta=mo_ta or None, thu_tu_hien_thi=thu_tu_hien_thi, bat_buoc_anh=bat_buoc_anh,
                    bat_buoc_ghi_chu=bat_buoc_ghi_chu, loi_do_cua_hang=loi_do_cua_hang,
                )
                DichVuNguyenNhan._ghi_lich_su(
                    nn.ma_nguyen_nhan, LichSuNguyenNhan.HanhDong.THEM, tai_khoan, None, DichVuNguyenNhan._chup(nn))
        except DatabaseError as loi:  # E5
            raise LoiNghiepVuHauMai("Không thể lưu thay đổi.") from loi
        return nn

    @staticmethod
    def sua(tai_khoan, ma_nguyen_nhan, **thay_doi):
        nn = NguyenNhan.objects.filter(ma_nguyen_nhan=ma_nguyen_nhan).first()
        if nn is None:
            raise LoiNghiepVuHauMai("Không tìm thấy nguyên nhân.")
        cu = DichVuNguyenNhan._chup(nn)
        loai = thay_doi.get("loai_xu_ly", nn.loai_xu_ly)
        if loai != nn.loai_xu_ly and DichVuNguyenNhan.so_lan_su_dung(nn) > 0:
            raise LoiNghiepVuHauMai("Nguyên nhân đã được sử dụng, không thể đổi loại xử lý.")
        nn.ten_nguyen_nhan = DichVuNguyenNhan._kiem_tra_du_lieu(
            loai, thay_doi.get("ten_nguyen_nhan", nn.ten_nguyen_nhan), thay_doi.get("mo_ta", nn.mo_ta), ma_nguyen_nhan)
        nn.loai_xu_ly = loai
        for truong in ("mo_ta", "thu_tu_hien_thi", "bat_buoc_anh", "bat_buoc_ghi_chu", "loi_do_cua_hang"):
            if truong in thay_doi:
                setattr(nn, truong, thay_doi[truong] if thay_doi[truong] != "" else None)
        try:
            with transaction.atomic():
                nn.save()
                DichVuNguyenNhan._ghi_lich_su(
                    nn.ma_nguyen_nhan, LichSuNguyenNhan.HanhDong.SUA, tai_khoan, cu, DichVuNguyenNhan._chup(nn))
        except DatabaseError as loi:
            raise LoiNghiepVuHauMai("Không thể lưu thay đổi.") from loi
        return nn

    @staticmethod
    def _doi_trang_thai(tai_khoan, ma_nguyen_nhan, dang_ap_dung, hanh_dong):
        nn = NguyenNhan.objects.filter(ma_nguyen_nhan=ma_nguyen_nhan).first()
        if nn is None:
            raise LoiNghiepVuHauMai("Không tìm thấy nguyên nhân.")
        if not dang_ap_dung:
            con_lai = NguyenNhan.objects.filter(
                loai_xu_ly=nn.loai_xu_ly, dang_ap_dung=True).exclude(ma_nguyen_nhan=ma_nguyen_nhan).count()
            if nn.dang_ap_dung and con_lai == 0:  # E4, BR10
                raise LoiNghiepVuHauMai("Mỗi loại xử lý cần ít nhất một nguyên nhân đang áp dụng.")
        cu = DichVuNguyenNhan._chup(nn)
        nn.dang_ap_dung = dang_ap_dung
        try:
            with transaction.atomic():
                nn.save()
                DichVuNguyenNhan._ghi_lich_su(nn.ma_nguyen_nhan, hanh_dong, tai_khoan, cu, DichVuNguyenNhan._chup(nn))
        except DatabaseError as loi:
            raise LoiNghiepVuHauMai("Không thể lưu thay đổi.") from loi
        return nn

    @staticmethod
    def ngung_su_dung(tai_khoan, ma_nguyen_nhan):
        return DichVuNguyenNhan._doi_trang_thai(tai_khoan, ma_nguyen_nhan, False, LichSuNguyenNhan.HanhDong.NGUNG)

    @staticmethod
    def kich_hoat(tai_khoan, ma_nguyen_nhan):
        return DichVuNguyenNhan._doi_trang_thai(tai_khoan, ma_nguyen_nhan, True, LichSuNguyenNhan.HanhDong.KICH_HOAT)

    @staticmethod
    def xoa(tai_khoan, ma_nguyen_nhan):
        """UC07 A2: chỉ xóa nguyên nhân chưa từng dùng (BR10)."""
        nn = NguyenNhan.objects.filter(ma_nguyen_nhan=ma_nguyen_nhan).first()
        if nn is None:
            raise LoiNghiepVuHauMai("Không tìm thấy nguyên nhân.")
        if DichVuNguyenNhan.so_lan_su_dung(nn) > 0:  # E3
            raise LoiNghiepVuHauMai("Nguyên nhân đã được sử dụng, chỉ có thể ngưng sử dụng.")
        if nn.dang_ap_dung and not NguyenNhan.objects.filter(
                loai_xu_ly=nn.loai_xu_ly, dang_ap_dung=True).exclude(ma_nguyen_nhan=ma_nguyen_nhan).exists():
            raise LoiNghiepVuHauMai("Mỗi loại xử lý cần ít nhất một nguyên nhân đang áp dụng.")
        cu = DichVuNguyenNhan._chup(nn)
        try:
            with transaction.atomic():
                DichVuNguyenNhan._ghi_lich_su(ma_nguyen_nhan, LichSuNguyenNhan.HanhDong.XOA, tai_khoan, cu, None)
                nn.delete()
        except DatabaseError as loi:
            raise LoiNghiepVuHauMai("Không thể lưu thay đổi.") from loi


# ==========================================================
# 7. HOÀN TIỀN – M4-UC06 (M4-BR08, M4-BR09)
# ==========================================================
def tong_da_thanh_toan(don):
    """Số tiền khách đã thanh toán thành công. Đơn chưa thanh toán thì 0 (BR08)."""
    if don.trang_thai_thanh_toan != TrangThaiThanhToan.DA_THANH_TOAN:
        return Decimal(0)
    tong = Decimal(0)
    for gd in GiaoDichThanhToan.objects.filter(don_hang=don, trang_thai=TrangThaiThanhToan.DA_THANH_TOAN):
        tong += gd.so_tien_thuc_nhan if gd.so_tien_thuc_nhan is not None else gd.so_tien_phai_thu
    return tong if tong > 0 else Decimal(don.tong_thanh_toan)


def tong_da_giu_cho_hoan(don, bo_qua_ma=None):
    """Tiền đã hoàn + tiền đang chờ hoàn (kể cả khoản thất bại chờ thử lại) của đơn."""
    tong = Decimal(0)
    for k in GiaoDichHoanTien.objects.filter(don_hang=don).exclude(ma_hoan_tien=bo_qua_ma):
        if k.trang_thai == TrangThaiHoanTien.DA_HOAN:
            tong += k.so_tien_hoan or 0
        else:
            tong += k.so_tien_de_xuat
    return tong


class DichVuHoanTien:

    @staticmethod
    def tao_khoan_hoan(don, nguon, so_tien_de_xuat=None, yeu_cau_huy=None, yeu_cau_doi_tra=None, xu_ly=None):
        """Tạo khoản hoàn "Chờ hoàn". Trả về None nếu đơn chưa thanh toán (BR08) hoặc không còn gì để hoàn.
        Gọi bên trong transaction của use case gọi nó."""
        da_tt = tong_da_thanh_toan(don)
        if da_tt <= 0:
            return None
        con_lai = da_tt - tong_da_giu_cho_hoan(don)
        so_tien = min(Decimal(so_tien_de_xuat) if so_tien_de_xuat is not None else da_tt, con_lai)
        if so_tien <= 0:
            return None
        khoan = GiaoDichHoanTien.objects.create(
            ma_hoan_tien=sinh_ma(GiaoDichHoanTien), don_hang=don, nguon=nguon, yeu_cau_huy=yeu_cau_huy,
            yeu_cau_doi_tra=yeu_cau_doi_tra, xu_ly_giao_that_bai=xu_ly, so_tien_da_thanh_toan=da_tt,
            so_tien_de_xuat=so_tien,
        )
        ma_yc = (yeu_cau_huy.ma_yc_huy if yeu_cau_huy else yeu_cau_doi_tra.ma_yc_doi_tra if yeu_cau_doi_tra
                 else xu_ly.ma_xu_ly if xu_ly else khoan.ma_hoan_tien)
        ghi_moc(don, LoaiYeuCau.HOAN_TIEN, khoan.ma_hoan_tien, "Tạo khoản hoàn tiền",
                TrangThaiHoanTien.CHO_HOAN, TacNhan.HE_THONG, ghi_chu=f"Phát sinh từ {ma_yc}, số tiền đề xuất {so_tien:,.0f}đ.")
        return khoan

    @staticmethod
    def tao_tu_thanh_toan_thua(don, nhan_vien):
        """Khách chuyển thừa (M3-UC11 E2): hoàn phần vượt tổng thanh toán của đơn."""
        thua = tong_da_thanh_toan(don) - Decimal(don.tong_thanh_toan)
        if thua <= 0:
            raise LoiNghiepVuHauMai("Đơn hàng không có khoản thanh toán thừa.")
        if GiaoDichHoanTien.objects.filter(don_hang=don, nguon=NguonHoanTien.THANH_TOAN_THUA).exists():
            raise LoiNghiepVuHauMai("Đơn hàng đã có khoản hoàn cho phần thanh toán thừa.")
        try:
            with transaction.atomic():
                khoan = DichVuHoanTien.tao_khoan_hoan(don, NguonHoanTien.THANH_TOAN_THUA, thua)
        except DatabaseError as loi:
            raise LoiNghiepVuHauMai(CAU_LOI_LUU) from loi
        if khoan is None:
            raise LoiNghiepVuHauMai("Không còn số tiền để hoàn.")
        return khoan

    @staticmethod
    def danh_sach(trang_thai=None, nguon=None, tu_ngay=None, den_ngay=None, trang=1):
        """UC06 bước 1: mặc định "Chờ hoàn" (cũ nhất trước)."""
        ds = GiaoDichHoanTien.objects.select_related("don_hang")
        ds = ds.filter(trang_thai=trang_thai or TrangThaiHoanTien.CHO_HOAN)
        if nguon:
            ds = ds.filter(nguon=nguon)
        if tu_ngay:
            ds = ds.filter(thoi_diem_tao__date__gte=tu_ngay)
        if den_ngay:
            ds = ds.filter(thoi_diem_tao__date__lte=den_ngay)
        return Paginator(ds.order_by("thoi_diem_tao", "ma_hoan_tien"), SO_DONG_MOI_TRANG).get_page(trang)

    @staticmethod
    def lay_khoan(ma_hoan_tien):
        khoan = GiaoDichHoanTien.objects.select_related("don_hang").filter(ma_hoan_tien=ma_hoan_tien).first()
        if khoan is None:
            raise LoiNghiepVuHauMai("Không tìm thấy khoản hoàn tiền.")
        return khoan

    @staticmethod
    def chi_tiet(ma_hoan_tien):
        """UC06 bước 2: đơn gốc, số đã thanh toán, số đã hoàn trước đó, số đề xuất."""
        khoan = DichVuHoanTien.lay_khoan(ma_hoan_tien)
        da_hoan_truoc = tong_da_giu_cho_hoan(khoan.don_hang, bo_qua_ma=khoan.ma_hoan_tien)
        return khoan, da_hoan_truoc

    @staticmethod
    def xac_nhan_da_hoan(ma_hoan_tien, nhan_vien, ma_giao_dich_hoan, so_tien=None, ly_do_dieu_chinh="",
                         phuong_thuc=None, thong_tin_tai_khoan=""):
        """UC06 bước 3–5, A1 (khấu trừ), A2 (COD), A3 (làm lại khoản thất bại)."""
        khoan = DichVuHoanTien.lay_khoan(ma_hoan_tien)
        if khoan.trang_thai not in (TrangThaiHoanTien.CHO_HOAN, TrangThaiHoanTien.THAT_BAI):
            raise LoiNghiepVuHauMai("Khoản hoàn đã được xử lý.")  # E6
        don = khoan.don_hang

        # ----- Số tiền (M4-BR08) -----
        so_tien = Decimal(so_tien) if so_tien is not None else khoan.so_tien_de_xuat
        if so_tien <= 0:
            raise LoiNghiepVuHauMai("Số tiền hoàn phải lớn hơn 0.")
        da_giu = tong_da_giu_cho_hoan(don, bo_qua_ma=khoan.ma_hoan_tien)
        if so_tien > khoan.so_tien_da_thanh_toan - da_giu:  # E2
            raise LoiNghiepVuHauMai("Số tiền hoàn vượt quá số đã thanh toán.")
        if so_tien > khoan.so_tien_de_xuat:  # chỉ được giảm khi có khấu trừ
            raise LoiNghiepVuHauMai("Số tiền hoàn không được lớn hơn số tiền đề xuất.")
        if so_tien < khoan.so_tien_de_xuat and not (ly_do_dieu_chinh or "").strip():  # E3
            raise LoiNghiepVuHauMai("Vui lòng nhập lý do điều chỉnh.")

        # ----- Phương thức hoàn (M4-BR08): về phương thức gốc; COD hoàn bằng chuyển khoản -----
        la_cod = don.phuong_thuc_thanh_toan_id == PhuongThucThanhToan.MA_COD
        phuong_thuc = phuong_thuc or (PhuongThucHoan.CHUYEN_KHOAN if la_cod else PhuongThucHoan.PHUONG_THUC_GOC)
        if phuong_thuc not in PhuongThucHoan.values:
            raise LoiNghiepVuHauMai("Phương thức hoàn không hợp lệ.")
        if la_cod and phuong_thuc != PhuongThucHoan.CHUYEN_KHOAN:
            raise LoiNghiepVuHauMai("Đơn thanh toán khi nhận hàng phải hoàn bằng chuyển khoản.")
        if phuong_thuc == PhuongThucHoan.CHUYEN_KHOAN and not (thong_tin_tai_khoan or "").strip():
            raise LoiNghiepVuHauMai("Vui lòng nhập thông tin tài khoản nhận tiền.")

        # ----- Mã giao dịch (M4-BR09) -----
        ma_giao_dich_hoan = (ma_giao_dich_hoan or "").strip()
        if not ma_giao_dich_hoan:  # E4
            raise LoiNghiepVuHauMai("Vui lòng nhập mã giao dịch hoàn.")
        if GiaoDichHoanTien.objects.filter(ma_giao_dich_hoan=ma_giao_dich_hoan).exclude(
                ma_hoan_tien=khoan.ma_hoan_tien).exists():
            raise LoiNghiepVuHauMai("Mã giao dịch hoàn đã tồn tại.")

        bay_gio = timezone.now()
        try:
            with transaction.atomic():
                # Compare-and-set: một khoản chỉ được ghi nhận "Đã hoàn" một lần (BR09, BR18)
                so_dong = GiaoDichHoanTien.objects.filter(
                    ma_hoan_tien=khoan.ma_hoan_tien,
                    trang_thai__in=[TrangThaiHoanTien.CHO_HOAN, TrangThaiHoanTien.THAT_BAI],
                ).update(
                    trang_thai=TrangThaiHoanTien.DA_HOAN, so_tien_hoan=so_tien,
                    ly_do_dieu_chinh=(ly_do_dieu_chinh or None) if so_tien < khoan.so_tien_de_xuat else khoan.ly_do_dieu_chinh,
                    phuong_thuc_hoan=phuong_thuc,
                    thong_tin_tai_khoan_nhan=ma_hoa(thong_tin_tai_khoan.strip()) if thong_tin_tai_khoan else None,
                    ma_giao_dich_hoan=ma_giao_dich_hoan, thoi_diem_hoan=bay_gio, nhan_vien_xu_ly=nhan_vien,
                    ly_do_that_bai=None,
                )
                if so_dong == 0:
                    raise LoiNghiepVuHauMai("Khoản hoàn đã được xử lý.")
                if DonHang.objects.filter(ma_dh=don.ma_dh).values_list("trang_thai_hau_mai", flat=True).first() != HM_CHO_DOI_TRA:
                    dat_hau_mai(don, HM_DA_HOAN_TIEN)
                ghi_moc(don, LoaiYeuCau.HOAN_TIEN, khoan.ma_hoan_tien, "Đã hoàn tiền", TrangThaiHoanTien.DA_HOAN,
                        TacNhan.NHAN_VIEN, nhan_vien, ghi_chu=f"Đã hoàn {so_tien:,.0f}đ, mã giao dịch {ma_giao_dich_hoan}.",
                        ghi_chu_noi_bo=ly_do_dieu_chinh, thoi_diem=bay_gio)
                DichVuThongBao.gui_khach(don, "Đã hoàn tiền", f"Đơn {don.ma_dh}: đã hoàn {so_tien:,.0f}đ cho bạn.")
        except IntegrityError as loi:  # trùng mã giao dịch do hai người bấm cùng lúc
            raise LoiNghiepVuHauMai("Mã giao dịch hoàn đã tồn tại.") from loi
        except DatabaseError as loi:
            raise LoiNghiepVuHauMai(CAU_LOI_LUU) from loi
        return GiaoDichHoanTien.objects.get(pk=khoan.pk)

    @staticmethod
    def ghi_nhan_that_bai(ma_hoan_tien, nhan_vien, ly_do):
        """UC06 E5: cổng thanh toán/ngân hàng từ chối. Lưu lý do, cho phép xử lý lại (A3)."""
        if not (ly_do or "").strip():
            raise LoiNghiepVuHauMai("Vui lòng nhập lý do thất bại.")
        khoan = DichVuHoanTien.lay_khoan(ma_hoan_tien)
        try:
            with transaction.atomic():
                so_dong = GiaoDichHoanTien.objects.filter(
                    ma_hoan_tien=ma_hoan_tien, trang_thai=TrangThaiHoanTien.CHO_HOAN
                ).update(trang_thai=TrangThaiHoanTien.THAT_BAI, ly_do_that_bai=ly_do.strip(), nhan_vien_xu_ly=nhan_vien)
                if so_dong == 0:
                    raise LoiNghiepVuHauMai("Khoản hoàn đã được xử lý.")
                ghi_moc(khoan.don_hang, LoaiYeuCau.HOAN_TIEN, ma_hoan_tien, "Hoàn tiền thất bại",
                        TrangThaiHoanTien.THAT_BAI, TacNhan.NHAN_VIEN, nhan_vien, ghi_chu_noi_bo=ly_do.strip())
        except DatabaseError as loi:
            raise LoiNghiepVuHauMai(CAU_LOI_LUU) from loi
        return GiaoDichHoanTien.objects.get(pk=ma_hoan_tien)

    @staticmethod
    def dieu_chinh(ma_hoan_tien_goc, nhan_vien, so_tien, ly_do):
        """BR09: giao dịch đã hoàn không sửa; sai sót xử lý bằng giao dịch điều chỉnh có lý do."""
        goc = DichVuHoanTien.lay_khoan(ma_hoan_tien_goc)
        if goc.trang_thai != TrangThaiHoanTien.DA_HOAN:
            raise LoiNghiepVuHauMai("Chỉ điều chỉnh được giao dịch đã hoàn.")
        if not (ly_do or "").strip():
            raise LoiNghiepVuHauMai("Vui lòng nhập lý do điều chỉnh.")
        so_tien = Decimal(so_tien)
        con_lai = tong_da_thanh_toan(goc.don_hang) - tong_da_giu_cho_hoan(goc.don_hang)
        if so_tien <= 0 or so_tien > con_lai:
            raise LoiNghiepVuHauMai("Số tiền hoàn vượt quá số đã thanh toán.")
        try:
            with transaction.atomic():
                khoan = GiaoDichHoanTien.objects.create(
                    ma_hoan_tien=sinh_ma(GiaoDichHoanTien), don_hang=goc.don_hang, nguon=goc.nguon,
                    yeu_cau_huy=goc.yeu_cau_huy, yeu_cau_doi_tra=goc.yeu_cau_doi_tra,
                    xu_ly_giao_that_bai=goc.xu_ly_giao_that_bai, giao_dich_goc=goc, la_dieu_chinh=True,
                    so_tien_da_thanh_toan=tong_da_thanh_toan(goc.don_hang), so_tien_de_xuat=so_tien,
                    ly_do_dieu_chinh=ly_do.strip(),
                )
                ghi_moc(goc.don_hang, LoaiYeuCau.HOAN_TIEN, khoan.ma_hoan_tien, "Tạo giao dịch điều chỉnh",
                        TrangThaiHoanTien.CHO_HOAN, TacNhan.NHAN_VIEN, nhan_vien,
                        ghi_chu_noi_bo=f"Điều chỉnh {goc.ma_hoan_tien}: {ly_do.strip()}")
        except DatabaseError as loi:
            raise LoiNghiepVuHauMai(CAU_LOI_LUU) from loi
        return khoan


# ==========================================================
# 8. HỦY ĐƠN – M4-UC01 (khách gửi), M4-UC02 (nhân viên xử lý)
# ==========================================================
def _cau_loi_khong_duoc_huy(don):
    if don.trang_thai in (T.GIAO_THANH_CONG, T.HOAN_THANH):
        return "Đơn hàng không còn ở trạng thái cho phép hủy. Nếu đã nhận hàng, bạn có thể dùng chức năng đổi/trả."
    if don.trang_thai == T.DA_HUY:
        return "Đơn hàng đã được hủy."
    return "Đơn hàng không còn ở trạng thái cho phép hủy."


class DichVuHuyDon:

    # ----- UC01 -----
    @staticmethod
    def gui_yeu_cau(ma_dh, khach_hang, ma_nguyen_nhan, ghi_chu=""):
        don = lay_don_cua_khach(ma_dh, khach_hang)
        if don.trang_thai not in TRANG_THAI_DUOC_HUY:  # E1, BR01
            raise LoiNghiepVuHauMai(_cau_loi_khong_duoc_huy(don))
        nn = DichVuNguyenNhan.lay_nguyen_nhan_ap_dung(
            ma_nguyen_nhan, LoaiXuLy.HUY_DON, "Vui lòng chọn nguyên nhân hủy")  # E2
        DichVuNguyenNhan.kiem_tra_ghi_chu(nn, ghi_chu)  # A2
        if YeuCauHuy.objects.filter(don_hang=don, trang_thai=TrangThaiYeuCauHuy.CHO_XU_LY).exists():  # E3
            raise LoiNghiepVuHauMai("Đơn hàng đã có yêu cầu hủy đang được xử lý")

        try:
            with transaction.atomic():
                yc = YeuCauHuy.objects.create(
                    ma_yc_huy=sinh_ma(YeuCauHuy), don_hang=don, nguyen_nhan=nn,
                    ghi_chu_khach=(ghi_chu or "").strip() or None, hau_mai_truoc=don.trang_thai_hau_mai,
                )
                dat_hau_mai(don, HM_CHO_HUY)  # M3 hiển thị "Chờ hủy" và chặn xác nhận/bàn giao (M3-BR19)
                ghi_moc(don, LoaiYeuCau.HUY_DON, yc.ma_yc_huy, "Khách gửi yêu cầu hủy đơn", yc.trang_thai,
                        TacNhan.KHACH_HANG, ghi_chu=f"Nguyên nhân: {nn.ten_nguyen_nhan}. {yc.ghi_chu_khach or ''}".strip())
                DichVuThongBao.gui_nhan_vien(don, "Yêu cầu hủy đơn mới", f"Đơn {don.ma_dh} có yêu cầu hủy chờ xử lý ({yc.ma_yc_huy}).")
                DichVuThongBao.gui_khach(don, "Đã gửi yêu cầu hủy đơn", f"Yêu cầu {yc.ma_yc_huy} cho đơn {don.ma_dh} đã được gửi.")
        except IntegrityError as loi:  # bấm gửi nhiều lần: ràng buộc CSDL chặn bản trùng (BR03)
            raise LoiNghiepVuHauMai("Đơn hàng đã có yêu cầu hủy đang được xử lý") from loi
        except DatabaseError as loi:  # E4
            raise LoiNghiepVuHauMai("Không thể gửi yêu cầu") from loi
        return yc

    @staticmethod
    def thu_hoi(ma_yc_huy, khach_hang):
        """M4-BR15: chỉ thu hồi khi còn "Chờ xử lý"; trả đơn về trạng thái trước đó."""
        yc = YeuCauHuy.objects.select_related("don_hang").filter(ma_yc_huy=ma_yc_huy).first()
        if yc is None:
            raise LoiNghiepVuHauMai("Không tìm thấy yêu cầu hủy.")
        don = yc.don_hang
        if don.khach_hang_id != khach_hang.ma_kh:
            raise LoiQuyenHauMai("Bạn không có quyền thao tác trên yêu cầu này.")
        try:
            with transaction.atomic():
                so_dong = YeuCauHuy.objects.filter(
                    ma_yc_huy=ma_yc_huy, trang_thai=TrangThaiYeuCauHuy.CHO_XU_LY
                ).update(trang_thai=TrangThaiYeuCauHuy.THU_HOI, thoi_diem_xu_ly=timezone.now())
                if so_dong == 0:
                    raise LoiNghiepVuHauMai("Yêu cầu đã được duyệt hoặc đang xử lý, không thể thu hồi.")
                dat_hau_mai(don, yc.hau_mai_truoc)
                ghi_moc(don, LoaiYeuCau.HUY_DON, ma_yc_huy, "Khách thu hồi yêu cầu hủy", TrangThaiYeuCauHuy.THU_HOI,
                        TacNhan.KHACH_HANG)
        except DatabaseError as loi:
            raise LoiNghiepVuHauMai(CAU_LOI_LUU) from loi
        return YeuCauHuy.objects.get(pk=ma_yc_huy)

    # ----- UC02 -----
    @staticmethod
    def danh_sach(trang_thai=None, tu_ngay=None, den_ngay=None, trang=1):
        """Bước 1: mặc định "Chờ xử lý", cũ nhất trước."""
        ds = YeuCauHuy.objects.select_related("don_hang", "nguyen_nhan")
        ds = ds.filter(trang_thai=trang_thai or TrangThaiYeuCauHuy.CHO_XU_LY)
        if tu_ngay:
            ds = ds.filter(thoi_diem_gui__date__gte=tu_ngay)
        if den_ngay:
            ds = ds.filter(thoi_diem_gui__date__lte=den_ngay)
        return Paginator(ds.order_by("thoi_diem_gui", "ma_yc_huy"), SO_DONG_MOI_TRANG).get_page(trang)

    @staticmethod
    def la_qua_han(yc):
        """Nhắc yêu cầu quá hạn xử lý (4.2, nhóm 1)."""
        return yc.trang_thai == TrangThaiYeuCauHuy.CHO_XU_LY and timezone.now() - yc.thoi_diem_gui > HAN_XU_LY_HUY

    @staticmethod
    def chi_tiet(ma_yc_huy):
        yc = YeuCauHuy.objects.select_related("don_hang", "nguyen_nhan").filter(ma_yc_huy=ma_yc_huy).first()
        if yc is None:
            raise LoiNghiepVuHauMai("Không tìm thấy yêu cầu hủy.")
        return yc

    @staticmethod
    def xu_ly(ma_yc_huy, nhan_vien, quyet_dinh, ly_do_tu_choi="", ghi_chu=""):
        """quyet_dinh: "DUYET" hoặc "TU_CHOI"."""
        yc = DichVuHuyDon.chi_tiet(ma_yc_huy)
        if yc.trang_thai != TrangThaiYeuCauHuy.CHO_XU_LY:  # E3
            raise LoiNghiepVuHauMai("Yêu cầu đã được xử lý")
        if quyet_dinh == "TU_CHOI":
            return DichVuHuyDon._tu_choi(yc, nhan_vien, ly_do_tu_choi, ghi_chu)
        if quyet_dinh == "DUYET":
            return DichVuHuyDon._duyet(yc, nhan_vien, ghi_chu)
        raise LoiNghiepVuHauMai("Quyết định không hợp lệ.")

    @staticmethod
    def _tu_choi(yc, nhan_vien, ly_do, ghi_chu):
        if not (ly_do or "").strip():  # E4
            raise LoiNghiepVuHauMai("Vui lòng nhập lý do từ chối")
        don, bay_gio = yc.don_hang, timezone.now()
        try:
            with transaction.atomic():
                so_dong = YeuCauHuy.objects.filter(
                    ma_yc_huy=yc.ma_yc_huy, trang_thai=TrangThaiYeuCauHuy.CHO_XU_LY
                ).update(trang_thai=TrangThaiYeuCauHuy.TU_CHOI, nhan_vien_xu_ly=nhan_vien, thoi_diem_xu_ly=bay_gio,
                         ly_do_tu_choi=ly_do.strip(), ghi_chu_noi_bo=ghi_chu or None)
                if so_dong == 0:
                    raise LoiNghiepVuHauMai("Yêu cầu đã được xử lý")
                dat_hau_mai(don, yc.hau_mai_truoc)
                ghi_moc(don, LoaiYeuCau.HUY_DON, yc.ma_yc_huy, "Nhân viên từ chối yêu cầu hủy",
                        TrangThaiYeuCauHuy.TU_CHOI, TacNhan.NHAN_VIEN, nhan_vien,
                        ghi_chu=f"Lý do: {ly_do.strip()}", ghi_chu_noi_bo=ghi_chu, thoi_diem=bay_gio)
                DichVuThongBao.gui_khach(don, "Yêu cầu hủy bị từ chối", f"Đơn {don.ma_dh}: {ly_do.strip()}")
        except DatabaseError as loi:
            raise LoiNghiepVuHauMai(CAU_LOI_LUU) from loi
        return YeuCauHuy.objects.get(pk=yc.pk)

    @staticmethod
    def _duyet(yc, nhan_vien, ghi_chu):
        bay_gio = timezone.now()
        try:
            with transaction.atomic():
                so_dong = YeuCauHuy.objects.filter(
                    ma_yc_huy=yc.ma_yc_huy, trang_thai=TrangThaiYeuCauHuy.CHO_XU_LY
                ).update(trang_thai=TrangThaiYeuCauHuy.DA_DUYET, nhan_vien_xu_ly=nhan_vien, thoi_diem_xu_ly=bay_gio,
                         ghi_chu_noi_bo=ghi_chu or None)
                if so_dong == 0:  # E3
                    raise LoiNghiepVuHauMai("Yêu cầu đã được xử lý")
                # BR01: kiểm tra lại trạng thái đơn tại thời điểm duyệt (E2)
                don = DonHang.objects.get(pk=yc.don_hang_id)
                if don.trang_thai not in TRANG_THAI_DUOC_HUY:
                    if don.trang_thai in (T.SAN_SANG_GIAO, T.DANG_GIAO):
                        raise LoiNghiepVuHauMai("Đơn hàng đã chuyển sang vận chuyển")
                    raise LoiNghiepVuHauMai(_cau_loi_khong_duoc_huy(don))
                # Hủy đơn qua hàm của M3 (cùng transaction): đổi trạng thái đơn + ghi lịch sử M3
                DichVuKetThucDon.huy_don(
                    don, nhan_vien=nhan_vien, ghi_chu=f"Hủy theo yêu cầu {yc.ma_yc_huy}: {yc.nguyen_nhan.ten_nguyen_nhan}")
                DichVuKho.hoan_toan_bo_don(don, LyDoBienDongKho.HUY_DON, yc.ma_yc_huy, nhan_vien)  # BR04
                khoan = DichVuHoanTien.tao_khoan_hoan(don, NguonHoanTien.HUY_DON, yeu_cau_huy=yc)  # BR08, A2
                dat_hau_mai(don, None)
                ghi_moc(don, LoaiYeuCau.HUY_DON, yc.ma_yc_huy, "Nhân viên duyệt yêu cầu hủy",
                        TrangThaiYeuCauHuy.DA_DUYET, TacNhan.NHAN_VIEN, nhan_vien, ghi_chu_noi_bo=ghi_chu, thoi_diem=bay_gio)
                noi_dung = f"Đơn {don.ma_dh} đã được hủy."
                if khoan:
                    noi_dung += " Khoản hoàn tiền sẽ được xử lý."
                DichVuThongBao.gui_khach(don, "Yêu cầu hủy đã được duyệt", noi_dung)
        except LoiNghiepVuDonHang:
            raise  # lỗi nghiệp vụ (của M4 hoặc M3): transaction đã hoàn tác, yêu cầu vẫn "Chờ xử lý" (E5)
        except DatabaseError as loi:
            raise LoiNghiepVuHauMai(CAU_LOI_LUU) from loi
        return YeuCauHuy.objects.get(pk=yc.pk)

    @staticmethod
    def xu_ly_hang_loat(danh_sach_ma, nhan_vien, ghi_chu=""):
        """A1: duyệt nhiều yêu cầu, báo kết quả từng yêu cầu."""
        ket_qua = []
        for ma in danh_sach_ma:
            try:
                DichVuHuyDon.xu_ly(ma, nhan_vien, "DUYET", ghi_chu=ghi_chu)
                ket_qua.append({"ma_yeu_cau": ma, "thanh_cong": True, "thong_bao": "Đã duyệt."})
            except LoiNghiepVuDonHang as loi:
                ket_qua.append({"ma_yeu_cau": ma, "thanh_cong": False, "thong_bao": str(loi)})
        return ket_qua


# ==========================================================
# 9. GIAO HÀNG KHÔNG THÀNH CÔNG – M4-UC03 (M4-BR02, M4-BR04, M4-BR05, M4-BR08)
#    Bảng GiaoHang của M3 giữ các lần giao; M4 ghi phần xử lý vào XuLyGiaoThatBai.
#    Đơn giữ "Đang giao" bên M3 khi giao lại; hoàn hàng thì M3 chuyển "Đã hủy" (hàm huy_don).
# ==========================================================
class DichVuGiaoThatBai:

    @staticmethod
    def danh_sach_don(trang=1):
        """Bước 1: các đơn đang giao (M3 chưa có trạng thái "Giao thất bại"), cũ nhất trước."""
        ds = DonHang.objects.filter(trang_thai=T.DANG_GIAO).order_by("thoi_diem_ban_giao", "ma_dh")
        return Paginator(ds, SO_DONG_MOI_TRANG).get_page(trang)

    @staticmethod
    def thong_tin_don(ma_dh):
        """Bước 1: thông tin đơn, lịch sử các lần giao và số lần đã thất bại."""
        don = lay_don(ma_dh)
        cac_lan = list(don.giao_hang.order_by("lan_giao"))
        so_that_bai = XuLyGiaoThatBai.objects.filter(don_hang=don).count()
        return don, cac_lan, so_that_bai

    @staticmethod
    def xu_ly(ma_dh, nhan_vien, ma_nguyen_nhan, huong_xu_ly, ghi_chu="", phan_hoi_khach="",
              ben_chiu_phi=BenChiuPhi.CUA_HANG, ngay_giao_lai=None, ten_nguoi_nhan_moi="",
              sdt_nguoi_nhan_moi="", dia_chi_giao_moi="", hinh_thuc_giao=None, don_vi_van_chuyen="",
              sdt_shipper="", ma_van_don="", khach_tu_choi=False):
        don = lay_don(ma_dh)
        if don.trang_thai != T.DANG_GIAO:
            raise LoiNghiepVuHauMai("Chỉ xử lý được đơn đang ở trạng thái đang giao.")
        lan_hien_tai = DichVuGiaoHang.lay_lan_giao_hien_tai(don)
        if lan_hien_tai is None or lan_hien_tai.ket_qua_giao != KetQuaGiao.DANG_GIAO:
            raise LoiNghiepVuHauMai("Đơn hàng không có lần giao nào đang chờ xử lý.")
        if XuLyGiaoThatBai.objects.filter(giao_hang=lan_hien_tai).exists():
            raise LoiNghiepVuHauMai("Lần giao này đã được xử lý.")

        nn = DichVuNguyenNhan.lay_nguyen_nhan_ap_dung(
            ma_nguyen_nhan, LoaiXuLy.GIAO_THAT_BAI, "Vui lòng chọn nguyên nhân giao không thành công.")  # E3
        DichVuNguyenNhan.kiem_tra_ghi_chu(nn, ghi_chu)
        if huong_xu_ly not in HuongXuLyGiao.values:
            raise LoiNghiepVuHauMai("Hướng xử lý không hợp lệ.")
        if ben_chiu_phi not in BenChiuPhi.values:
            raise LoiNghiepVuHauMai("Bên chịu phí không hợp lệ.")

        so_lan_that_bai = XuLyGiaoThatBai.objects.filter(don_hang=don).count() + 1
        giao_lai = huong_xu_ly != HuongXuLyGiao.HOAN_VE_KHO
        if giao_lai and (so_lan_that_bai >= SO_LAN_GIAO_TOI_DA or lan_hien_tai.lan_giao >= SO_LAN_GIAO_TOI_DA):
            raise LoiNghiepVuHauMai(  # E2, BR05
                f"Đơn đã giao không thành công {SO_LAN_GIAO_TOI_DA} lần, bắt buộc chọn hoàn hàng về kho.")
        if giao_lai:
            if ngay_giao_lai is None:
                raise LoiNghiepVuHauMai("Vui lòng nhập ngày giao lại.")  # E3
            if ngay_giao_lai < timezone.localdate():
                raise LoiNghiepVuHauMai("Ngày giao lại không hợp lệ.")  # E4
        if huong_xu_ly == HuongXuLyGiao.DOI_THONG_TIN_GIAO_LAI and not (dia_chi_giao_moi or "").strip():
            raise LoiNghiepVuHauMai("Vui lòng nhập địa chỉ giao hàng mới.")  # E3

        ket_qua_lan = KetQuaGiao.KHACH_TU_CHOI if khach_tu_choi else KetQuaGiao.THAT_BAI
        ly_do = f"{nn.ten_nguyen_nhan}. {ghi_chu or ''}".strip()[:255]
        bay_gio = timezone.now()
        try:
            with transaction.atomic():
                if giao_lai:
                    # Mặc định giao lại bằng cách giao của lần trước; M3 kiểm tra và tạo lần giao mới
                    DichVuGiaoHang.tao_lan_giao_lai(
                        don, nhan_vien, ket_qua_lan, ly_do,
                        hinh_thuc_giao or lan_hien_tai.hinh_thuc_giao,
                        don_vi_van_chuyen or lan_hien_tai.don_vi_van_chuyen,
                        sdt_shipper or (lan_hien_tai.sdt_shipper or ""), ma_van_don)
                    dat_hau_mai(don, HM_CHO_GIAO_LAI)
                else:
                    DichVuKetThucDon.huy_don(don, nhan_vien=nhan_vien, ghi_chu=f"Giao không thành công, hoàn về kho: {ly_do}",
                                            ket_qua_lan_giao=ket_qua_lan)
                    dat_hau_mai(don, HM_DANG_HOAN_VE_KHO)
                xl = XuLyGiaoThatBai.objects.create(
                    ma_xu_ly=sinh_ma(XuLyGiaoThatBai), don_hang=don, giao_hang=lan_hien_tai,
                    lan_giao=lan_hien_tai.lan_giao, nguyen_nhan=nn, ghi_chu=ghi_chu or None,
                    phan_hoi_khach=phan_hoi_khach or None, huong_xu_ly=huong_xu_ly, ben_chiu_phi=ben_chiu_phi,
                    ngay_giao_lai_du_kien=ngay_giao_lai if giao_lai else None,
                    ten_nguoi_nhan_moi=ten_nguoi_nhan_moi or None, sdt_nguoi_nhan_moi=sdt_nguoi_nhan_moi or None,
                    dia_chi_giao_moi=dia_chi_giao_moi or None, nhan_vien=nhan_vien, thoi_diem=bay_gio,
                )
                huong_ten = dict(HuongXuLyGiao.choices)[huong_xu_ly]
                ghi_moc(don, LoaiYeuCau.GIAO_THAT_BAI, xl.ma_xu_ly, f"Giao không thành công lần {xl.lan_giao}",
                        huong_xu_ly, TacNhan.NHAN_VIEN, nhan_vien, ghi_chu=f"{nn.ten_nguyen_nhan}. Hướng xử lý: {huong_ten}.",
                        ghi_chu_noi_bo=phan_hoi_khach or None, thoi_diem=bay_gio)
                DichVuThongBao.gui_khach(
                    don, "Giao hàng không thành công",
                    f"Đơn {don.ma_dh}: " + ("sẽ được giao lại." if giao_lai else "đang được hoàn về kho."))
        except LoiNghiepVuDonHang:
            raise
        except DatabaseError as loi:  # E5
            raise LoiNghiepVuHauMai("Không thể lưu xử lý") from loi
        return xl

    @staticmethod
    def xac_nhan_nhap_kho(ma_xu_ly, nhan_vien):
        """A1: hàng đã về kho -> hoàn tồn kho, tạo hoàn tiền nếu đơn đã thanh toán trước."""
        xl = XuLyGiaoThatBai.objects.select_related("don_hang").filter(ma_xu_ly=ma_xu_ly).first()
        if xl is None:
            raise LoiNghiepVuHauMai("Không tìm thấy xử lý giao hàng.")
        if xl.huong_xu_ly != HuongXuLyGiao.HOAN_VE_KHO:
            raise LoiNghiepVuHauMai("Chỉ xác nhận nhập kho cho đơn đã chọn hoàn hàng về kho.")
        don, bay_gio = xl.don_hang, timezone.now()
        try:
            with transaction.atomic():
                so_dong = XuLyGiaoThatBai.objects.filter(ma_xu_ly=ma_xu_ly, da_nhap_kho=False).update(
                    da_nhap_kho=True, thoi_diem_nhap_kho=bay_gio)
                if so_dong == 0:
                    raise LoiNghiepVuHauMai("Hàng của đơn này đã được xác nhận nhập kho.")
                DichVuKho.hoan_toan_bo_don(don, LyDoBienDongKho.HOAN_HANG, ma_xu_ly, nhan_vien)
                khoan = DichVuHoanTien.tao_khoan_hoan(don, NguonHoanTien.GIAO_THAT_BAI, xu_ly=xl)
                dat_hau_mai(don, HM_DA_HOAN_HANG)
                ghi_moc(don, LoaiYeuCau.GIAO_THAT_BAI, ma_xu_ly, "Hàng đã hoàn về kho", HM_DA_HOAN_HANG,
                        TacNhan.NHAN_VIEN, nhan_vien, thoi_diem=bay_gio)
                DichVuThongBao.gui_khach(don, "Đã hoàn hàng về kho", f"Đơn {don.ma_dh}: hàng đã về kho."
                                         + (" Khoản hoàn tiền sẽ được xử lý." if khoan else ""))
        except LoiNghiepVuDonHang:
            raise
        except DatabaseError as loi:
            raise LoiNghiepVuHauMai(CAU_LOI_LUU) from loi
        return XuLyGiaoThatBai.objects.get(pk=ma_xu_ly)


# ==========================================================
# 10. ĐỔI/TRẢ HÀNG – M4-UC04 (khách gửi), M4-UC05 (nhân viên xử lý)
#     (M4-BR04, BR06, BR07, BR08, BR15, BR16, BR17)
#     Điều kiện gửi dùng cửa sổ 7 ngày của M3 (han_cua_so_doi_tra): đơn "Giao thành công"
#     và khách chưa xác nhận đã nhận hàng. Lưu ý: tài liệu M4-BR06 ghi "Hoàn thành",
#     nhưng bên M3 đơn chỉ sang "Hoàn thành" SAU khi cửa sổ đổi/trả đóng.
# ==========================================================
MAX_ANH = 5
MAX_DUNG_LUONG_ANH = 5 * 1024 * 1024


def so_luong_da_giu(chi_tiet, bo_qua_yeu_cau=None):
    """M4-BR06: số lượng của dòng đã nằm trong các yêu cầu đổi/trả còn hiệu lực."""
    tong = 0
    ds = DongDoiTra.objects.filter(
        chi_tiet_don_hang=chi_tiet, yeu_cau__trang_thai__in=TRANG_THAI_DOI_TRA_GIU_SO_LUONG
    ).select_related("yeu_cau")
    if bo_qua_yeu_cau:
        ds = ds.exclude(yeu_cau=bo_qua_yeu_cau)
    for d in ds:
        tong += d.so_luong_dat if d.yeu_cau.trang_thai == TrangThaiDoiTra.HOAN_TAT else d.so_luong
    return tong


def gia_hien_hanh(dong_goc, bien_the_moi):
    """M4-BR17: giá hiện hành của sản phẩm đổi (khách sỉ giữ giá sỉ nếu sản phẩm đó có giá sỉ)."""
    if dong_goc.loai_gia_ap_dung == LoaiGia.GIA_SI and bien_the_moi.gia_ban_si is not None:
        return Decimal(bien_the_moi.gia_ban_si)
    return Decimal(bien_the_moi.gia_ban_le)


class DichVuDoiTra:

    # ----- UC04 -----
    @staticmethod
    def cac_dong_du_dieu_kien(don):
        """Bước 2: các dòng còn có thể yêu cầu, kèm số lượng còn lại."""
        ket_qua = []
        for ct in ChiTietDonHang.objects.filter(don_hang=don).select_related("bien_the").order_by("ma_ctdh"):
            con_lai = ct.so_luong - so_luong_da_giu(ct)
            if con_lai > 0:
                ket_qua.append((ct, con_lai))
        return ket_qua

    @staticmethod
    def kiem_tra_thoi_han(don):
        han = DichVuTraCuuDon.han_cua_so_doi_tra(don)  # M3: chỉ có giá trị khi cửa sổ đang mở
        if don.trang_thai != T.GIAO_THANH_CONG and don.trang_thai != T.HOAN_THANH:
            raise LoiNghiepVuHauMai("Đơn hàng chưa giao thành công, không thể đổi/trả.")
        if han is None or timezone.now() > han:  # E1, BR06
            raise LoiNghiepVuHauMai("Đơn hàng đã quá thời hạn đổi/trả.")

    @staticmethod
    def _kiem_tra_anh(anh, nn):
        anh = list(anh or [])
        if nn.bat_buoc_anh and not anh:  # E4, BR07
            raise LoiNghiepVuHauMai("Nguyên nhân này bắt buộc đính kèm ảnh minh chứng.")
        if len(anh) > MAX_ANH:
            raise LoiNghiepVuHauMai(f"Chỉ được đính kèm tối đa {MAX_ANH} ảnh.")
        for tep in anh:
            ten = (getattr(tep, "name", "") or "").lower()
            if not ten.endswith((".jpg", ".jpeg", ".png")):  # E3
                raise LoiNghiepVuHauMai("Ảnh phải có định dạng JPG hoặc PNG.")
            if getattr(tep, "size", 0) > MAX_DUNG_LUONG_ANH:
                raise LoiNghiepVuHauMai("Mỗi ảnh không được quá 5 MB.")
        return anh

    @staticmethod
    def gui_yeu_cau(ma_dh, khach_hang, hinh_thuc, ma_nguyen_nhan, mo_ta, dong, anh=None):
        """dong: danh sách dict {"ma_ctdh", "so_luong", "ma_bien_the_doi" (chỉ khi đổi)}."""
        don = lay_don_cua_khach(ma_dh, khach_hang)
        DichVuDoiTra.kiem_tra_thoi_han(don)
        if hinh_thuc not in HinhThucDoiTra.values:
            raise LoiNghiepVuHauMai("Hình thức đổi/trả không hợp lệ.")
        if not dong:
            raise LoiNghiepVuHauMai("Vui lòng chọn ít nhất một sản phẩm.")
        nn = DichVuNguyenNhan.lay_nguyen_nhan_ap_dung(ma_nguyen_nhan, LoaiXuLy.DOI_TRA, "Vui lòng chọn nguyên nhân.")
        DichVuNguyenNhan.kiem_tra_ghi_chu(nn, mo_ta)
        anh = DichVuDoiTra._kiem_tra_anh(anh, nn)

        # Kiểm tra từng dòng (E2, E5, BR06, BR17)
        cac_dong = []
        da_thay = set()
        for d in dong:
            ct = ChiTietDonHang.objects.filter(ma_ctdh=d.get("ma_ctdh"), don_hang=don).select_related("bien_the").first()
            if ct is None:
                raise LoiNghiepVuHauMai("Sản phẩm không thuộc đơn hàng này.")
            if ct.ma_ctdh in da_thay:
                raise LoiNghiepVuHauMai("Mỗi sản phẩm chỉ được chọn một lần.")
            da_thay.add(ct.ma_ctdh)
            so_luong = d.get("so_luong") or 0
            if so_luong <= 0 or so_luong > ct.so_luong - so_luong_da_giu(ct):
                raise LoiNghiepVuHauMai("Số lượng vượt quá số đã mua")
            if DongDoiTra.objects.filter(
                    chi_tiet_don_hang=ct, yeu_cau__trang_thai=TrangThaiDoiTra.CHO_XU_LY).exists():
                raise LoiNghiepVuHauMai("Sản phẩm này đã có yêu cầu đổi/trả đang chờ xử lý.")
            bien_the_doi = None
            if hinh_thuc == HinhThucDoiTra.DOI:
                from products.models import BienTheSanPham
                bien_the_doi = BienTheSanPham.objects.filter(ma_bien_the=d.get("ma_bien_the_doi")).first()
                if bien_the_doi is None:
                    raise LoiNghiepVuHauMai("Vui lòng chọn sản phẩm/phân loại muốn nhận.")
                if not DichVuKho.con_hang(bien_the_doi, so_luong):  # E5
                    raise LoiNghiepVuHauMai("Sản phẩm thay thế hiện không đủ tồn kho")
            cac_dong.append((ct, so_luong, bien_the_doi))

        try:
            with transaction.atomic():
                yc = YeuCauDoiTra.objects.create(
                    ma_yc_doi_tra=sinh_ma(YeuCauDoiTra), don_hang=don, hinh_thuc=hinh_thuc, nguyen_nhan=nn,
                    mo_ta=(mo_ta or "").strip() or None, hau_mai_truoc=don.trang_thai_hau_mai,
                    ben_chiu_phi_van_chuyen=BenChiuPhi.CUA_HANG if nn.loi_do_cua_hang else BenChiuPhi.KHACH_HANG,
                )
                for ct, so_luong, bien_the_doi in cac_dong:
                    DongDoiTra.objects.create(
                        ma_dong=sinh_ma(DongDoiTra), yeu_cau=yc, chi_tiet_don_hang=ct, so_luong=so_luong,
                        bien_the_doi=bien_the_doi)
                anh_dau = None
                for tep in anh:
                    a = AnhMinhChung.objects.create(ma_anh=sinh_ma(AnhMinhChung), yeu_cau=yc, tep=tep)
                    anh_dau = anh_dau or a
                dat_hau_mai(don, HM_CHO_DOI_TRA)  # M3: đơn chưa được "Hoàn thành" khi còn yêu cầu mở
                ghi_moc(don, LoaiYeuCau.DOI_TRA, yc.ma_yc_doi_tra, "Khách gửi yêu cầu đổi/trả", yc.trang_thai,
                        TacNhan.KHACH_HANG, ghi_chu=f"{dict(HinhThucDoiTra.choices)[hinh_thuc]} - {nn.ten_nguyen_nhan}. {yc.mo_ta or ''}".strip(),
                        anh=anh_dau)
                DichVuThongBao.gui_nhan_vien(don, "Yêu cầu đổi/trả mới", f"Đơn {don.ma_dh} có yêu cầu đổi/trả chờ xử lý ({yc.ma_yc_doi_tra}).")
                DichVuThongBao.gui_khach(don, "Đã gửi yêu cầu đổi/trả", f"Yêu cầu {yc.ma_yc_doi_tra} cho đơn {don.ma_dh} đã được gửi.")
        except DatabaseError as loi:  # E6
            raise LoiNghiepVuHauMai("Không thể gửi yêu cầu") from loi
        return yc

    @staticmethod
    def thu_hoi(ma_yc_doi_tra, khach_hang):
        """M4-BR15: thu hồi khi còn "Chờ xử lý"; số lượng đã giữ được giải phóng (không còn tính vào BR06)."""
        yc = DichVuDoiTra.lay_yeu_cau(ma_yc_doi_tra)
        don = yc.don_hang
        if don.khach_hang_id != khach_hang.ma_kh:
            raise LoiQuyenHauMai("Bạn không có quyền thao tác trên yêu cầu này.")
        try:
            with transaction.atomic():
                so_dong = YeuCauDoiTra.objects.filter(
                    ma_yc_doi_tra=ma_yc_doi_tra, trang_thai=TrangThaiDoiTra.CHO_XU_LY
                ).update(trang_thai=TrangThaiDoiTra.THU_HOI)
                if so_dong == 0:
                    raise LoiNghiepVuHauMai("Yêu cầu đã được duyệt hoặc đang xử lý, không thể thu hồi.")
                dat_hau_mai(don, hau_mai_sau_khi_dong_doi_tra(don, yc.hau_mai_truoc))
                ghi_moc(don, LoaiYeuCau.DOI_TRA, ma_yc_doi_tra, "Khách thu hồi yêu cầu đổi/trả",
                        TrangThaiDoiTra.THU_HOI, TacNhan.KHACH_HANG)
                DichVuThanhToan.xet_hoan_thanh(DonHang.objects.get(pk=don.pk))
        except DatabaseError as loi:
            raise LoiNghiepVuHauMai(CAU_LOI_LUU) from loi
        return YeuCauDoiTra.objects.get(pk=ma_yc_doi_tra)

    # ----- UC05 -----
    @staticmethod
    def lay_yeu_cau(ma_yc_doi_tra):
        yc = YeuCauDoiTra.objects.select_related("don_hang", "nguyen_nhan").filter(ma_yc_doi_tra=ma_yc_doi_tra).first()
        if yc is None:
            raise LoiNghiepVuHauMai("Không tìm thấy yêu cầu đổi/trả.")
        return yc

    @staticmethod
    def danh_sach(trang_thai=None, hinh_thuc=None, tu_ngay=None, den_ngay=None, trang=1):
        DichVuDoiTra.dong_yeu_cau_het_han()  # BR16: tự đóng yêu cầu quá hạn trước khi hiển thị
        ds = YeuCauDoiTra.objects.select_related("don_hang", "nguyen_nhan")
        if trang_thai:
            ds = ds.filter(trang_thai=trang_thai)
        if hinh_thuc:
            ds = ds.filter(hinh_thuc=hinh_thuc)
        if tu_ngay:
            ds = ds.filter(thoi_diem_gui__date__gte=tu_ngay)
        if den_ngay:
            ds = ds.filter(thoi_diem_gui__date__lte=den_ngay)
        return Paginator(ds.order_by("thoi_diem_gui", "ma_yc_doi_tra"), SO_DONG_MOI_TRANG).get_page(trang)

    @staticmethod
    def chi_tiet(ma_yc_doi_tra):
        DichVuDoiTra.dong_yeu_cau_het_han()
        return DichVuDoiTra.lay_yeu_cau(ma_yc_doi_tra)

    @staticmethod
    def tu_choi(ma_yc_doi_tra, nhan_vien, ly_do, ghi_chu=""):
        yc = DichVuDoiTra.lay_yeu_cau(ma_yc_doi_tra)
        if yc.trang_thai != TrangThaiDoiTra.CHO_XU_LY:  # E2
            raise LoiNghiepVuHauMai("Yêu cầu đã được xử lý")
        if not (ly_do or "").strip():  # E3
            raise LoiNghiepVuHauMai("Vui lòng nhập lý do từ chối")
        don, bay_gio = yc.don_hang, timezone.now()
        try:
            with transaction.atomic():
                so_dong = YeuCauDoiTra.objects.filter(
                    ma_yc_doi_tra=ma_yc_doi_tra, trang_thai=TrangThaiDoiTra.CHO_XU_LY
                ).update(trang_thai=TrangThaiDoiTra.TU_CHOI, nhan_vien_xu_ly=nhan_vien, thoi_diem_xu_ly=bay_gio,
                         ly_do_tu_choi=ly_do.strip(), ghi_chu_noi_bo=ghi_chu or None)
                if so_dong == 0:
                    raise LoiNghiepVuHauMai("Yêu cầu đã được xử lý")
                dat_hau_mai(don, hau_mai_sau_khi_dong_doi_tra(don, yc.hau_mai_truoc))
                ghi_moc(don, LoaiYeuCau.DOI_TRA, ma_yc_doi_tra, "Nhân viên từ chối yêu cầu đổi/trả",
                        TrangThaiDoiTra.TU_CHOI, TacNhan.NHAN_VIEN, nhan_vien, ghi_chu=f"Lý do: {ly_do.strip()}",
                        ghi_chu_noi_bo=ghi_chu, thoi_diem=bay_gio)
                DichVuThongBao.gui_khach(don, "Yêu cầu đổi/trả bị từ chối", f"Đơn {don.ma_dh}: {ly_do.strip()}")
                DichVuThanhToan.xet_hoan_thanh(DonHang.objects.get(pk=don.pk))
        except DatabaseError as loi:
            raise LoiNghiepVuHauMai(CAU_LOI_LUU) from loi
        return YeuCauDoiTra.objects.get(pk=ma_yc_doi_tra)

    @staticmethod
    def duyet(ma_yc_doi_tra, nhan_vien, khong_thu_hoi_hang=False, ghi_chu="", ma_van_don_doi=""):
        """Bước 3. A1: không thu hồi hàng -> bỏ qua bước nhận hàng, hoàn tất ngay."""
        yc = DichVuDoiTra.lay_yeu_cau(ma_yc_doi_tra)
        if yc.trang_thai != TrangThaiDoiTra.CHO_XU_LY:  # E2
            raise LoiNghiepVuHauMai("Yêu cầu đã được xử lý")
        don, bay_gio = yc.don_hang, timezone.now()
        try:
            with transaction.atomic():
                so_dong = YeuCauDoiTra.objects.filter(
                    ma_yc_doi_tra=ma_yc_doi_tra, trang_thai=TrangThaiDoiTra.CHO_XU_LY
                ).update(trang_thai=TrangThaiDoiTra.DA_DUYET, nhan_vien_xu_ly=nhan_vien, thoi_diem_xu_ly=bay_gio,
                         khong_thu_hoi_hang=khong_thu_hoi_hang, ghi_chu_noi_bo=ghi_chu or None)
                if so_dong == 0:
                    raise LoiNghiepVuHauMai("Yêu cầu đã được xử lý")
                ghi_moc(don, LoaiYeuCau.DOI_TRA, ma_yc_doi_tra, "Nhân viên duyệt yêu cầu đổi/trả",
                        TrangThaiDoiTra.DA_DUYET, TacNhan.NHAN_VIEN, nhan_vien, ghi_chu_noi_bo=ghi_chu, thoi_diem=bay_gio)
                if khong_thu_hoi_hang:
                    for d in DongDoiTra.objects.filter(yeu_cau=yc):
                        DongDoiTra.objects.filter(pk=d.pk).update(
                            ket_qua_kiem_tra=KetQuaKiemTraTra.DAT, so_luong_dat=d.so_luong)
                    DichVuDoiTra._hoan_tat(ma_yc_doi_tra, nhan_vien, ma_van_don_doi, bay_gio)
                else:
                    han = bay_gio + HAN_GUI_HANG_DOI_TRA
                    YeuCauDoiTra.objects.filter(ma_yc_doi_tra=ma_yc_doi_tra).update(
                        trang_thai=TrangThaiDoiTra.DANG_CHO_NHAN_HANG, han_gui_hang=han)
                    ghi_moc(don, LoaiYeuCau.DOI_TRA, ma_yc_doi_tra, "Chờ khách gửi hàng về", TrangThaiDoiTra.DANG_CHO_NHAN_HANG,
                            TacNhan.HE_THONG, ghi_chu=f"Vui lòng gửi hàng về trước {timezone.localtime(han):%d/%m/%Y}.",
                            thoi_diem=bay_gio)
                    DichVuThongBao.gui_khach(
                        don, "Yêu cầu đổi/trả đã được duyệt",
                        f"Đơn {don.ma_dh}: vui lòng gửi hàng về trong {HAN_GUI_HANG_DOI_TRA.days} ngày.")
        except LoiNghiepVuDonHang:
            raise
        except DatabaseError as loi:
            raise LoiNghiepVuHauMai(CAU_LOI_LUU) from loi
        return YeuCauDoiTra.objects.get(pk=ma_yc_doi_tra)

    @staticmethod
    def nhan_hang(ma_yc_doi_tra, nhan_vien, ket_qua_dong, ghi_chu="", ma_van_don_gui_lai=""):
        """Bước 4. ket_qua_dong: [{"ma_dong", "ket_qua": "DAT"|"KHONG_DAT", "so_luong_dat", "kho_nhap", "ghi_chu"}].
        A3: hàng đạt một phần -> chỉ xử lý số lượng đạt. E5: không đạt hết -> từ chối, gửi trả lại khách."""
        DichVuDoiTra.dong_yeu_cau_het_han()
        yc = DichVuDoiTra.lay_yeu_cau(ma_yc_doi_tra)
        if yc.trang_thai == TrangThaiDoiTra.HET_HAN_GUI_HANG:  # E4
            raise LoiNghiepVuHauMai("Yêu cầu đã quá hạn gửi hàng và bị đóng.")
        if yc.trang_thai != TrangThaiDoiTra.DANG_CHO_NHAN_HANG:
            raise LoiNghiepVuHauMai("Yêu cầu không ở trạng thái chờ nhận hàng.")
        don, bay_gio = yc.don_hang, timezone.now()
        dong_theo_ma = {d.ma_dong: d for d in DongDoiTra.objects.filter(yeu_cau=yc)}
        theo_ma = {k.get("ma_dong"): k for k in ket_qua_dong or []}
        if set(theo_ma) != set(dong_theo_ma):
            raise LoiNghiepVuHauMai("Vui lòng ghi kết quả kiểm tra cho tất cả các dòng sản phẩm.")

        cap_nhat, co_dat = [], False
        for ma, d in dong_theo_ma.items():
            k = theo_ma[ma]
            ket_qua = k.get("ket_qua")
            if ket_qua == KetQuaKiemTraTra.KHONG_DAT:
                cap_nhat.append((d, ket_qua, 0, None, k.get("ghi_chu")))
            elif ket_qua == KetQuaKiemTraTra.DAT:
                so_dat = k.get("so_luong_dat", d.so_luong)
                if not 1 <= so_dat <= d.so_luong:
                    raise LoiNghiepVuHauMai("Số lượng đạt không hợp lệ.")
                kho = k.get("kho_nhap") or (KhoNhap.KHO_LOI if yc.nguyen_nhan.loi_do_cua_hang else KhoNhap.KHO_BAN)
                if kho not in KhoNhap.values:
                    raise LoiNghiepVuHauMai("Kho nhập không hợp lệ.")
                cap_nhat.append((d, ket_qua, so_dat, kho, k.get("ghi_chu")))
                co_dat = True
            else:
                raise LoiNghiepVuHauMai("Kết quả kiểm tra không hợp lệ.")

        try:
            with transaction.atomic():
                if not co_dat:  # E5, BR16
                    if not (ghi_chu or "").strip():
                        raise LoiNghiepVuHauMai("Vui lòng nhập lý do hàng không đạt.")
                    YeuCauDoiTra.objects.filter(pk=ma_yc_doi_tra).update(
                        trang_thai=TrangThaiDoiTra.TU_CHOI, ly_do_tu_choi=ghi_chu.strip(),
                        ma_van_don_gui_lai=ma_van_don_gui_lai or None, thoi_diem_nhan_hang=bay_gio)
                    dat_hau_mai(don, hau_mai_sau_khi_dong_doi_tra(don, yc.hau_mai_truoc))
                    ghi_moc(don, LoaiYeuCau.DOI_TRA, ma_yc_doi_tra, "Hàng nhận về không đạt, từ chối yêu cầu",
                            TrangThaiDoiTra.TU_CHOI, TacNhan.NHAN_VIEN, nhan_vien, ghi_chu=ghi_chu.strip(), thoi_diem=bay_gio)
                    DichVuThongBao.gui_khach(don, "Yêu cầu đổi/trả bị từ chối",
                                             f"Đơn {don.ma_dh}: hàng nhận về không đạt. Hàng sẽ được gửi trả lại bạn.")
                    DichVuThanhToan.xet_hoan_thanh(DonHang.objects.get(pk=don.pk))
                else:
                    for d, ket_qua, so_dat, kho, gc in cap_nhat:
                        DongDoiTra.objects.filter(pk=d.pk).update(
                            ket_qua_kiem_tra=ket_qua, so_luong_dat=so_dat, kho_nhap=kho, ghi_chu_kiem_tra=gc or None)
                    YeuCauDoiTra.objects.filter(pk=ma_yc_doi_tra).update(
                        trang_thai=TrangThaiDoiTra.DA_NHAN_HANG, thoi_diem_nhan_hang=bay_gio)
                    ghi_moc(don, LoaiYeuCau.DOI_TRA, ma_yc_doi_tra, "Đã nhận hàng trả về", TrangThaiDoiTra.DA_NHAN_HANG,
                            TacNhan.NHAN_VIEN, nhan_vien, ghi_chu_noi_bo=ghi_chu, thoi_diem=bay_gio)
        except LoiNghiepVuDonHang:
            raise
        except DatabaseError as loi:
            raise LoiNghiepVuHauMai(CAU_LOI_LUU) from loi
        return YeuCauDoiTra.objects.get(pk=ma_yc_doi_tra)

    @staticmethod
    def hoan_tat(ma_yc_doi_tra, nhan_vien, ma_van_don_doi=""):
        """Bước 5: nhập kho, tạo hoàn tiền hoặc giao hàng đổi, đóng yêu cầu."""
        yc = DichVuDoiTra.lay_yeu_cau(ma_yc_doi_tra)
        if yc.trang_thai != TrangThaiDoiTra.DA_NHAN_HANG:
            raise LoiNghiepVuHauMai("Yêu cầu chưa ở trạng thái đã nhận hàng.")
        try:
            with transaction.atomic():
                DichVuDoiTra._hoan_tat(ma_yc_doi_tra, nhan_vien, ma_van_don_doi, timezone.now())
        except LoiNghiepVuDonHang:
            raise  # E6, E7: hoàn tác, giữ trạng thái trước đó
        except DatabaseError as loi:
            raise LoiNghiepVuHauMai(CAU_LOI_LUU) from loi
        return YeuCauDoiTra.objects.get(pk=ma_yc_doi_tra)

    @staticmethod
    def _hoan_tat(ma_yc_doi_tra, nhan_vien, ma_van_don_doi, bay_gio):
        """Gọi bên trong transaction. Dùng chung cho hoan_tat và duyet (A1)."""
        yc = DichVuDoiTra.lay_yeu_cau(ma_yc_doi_tra)
        don = yc.don_hang
        so_dong = YeuCauDoiTra.objects.filter(
            ma_yc_doi_tra=ma_yc_doi_tra, trang_thai__in=[TrangThaiDoiTra.DA_NHAN_HANG, TrangThaiDoiTra.DA_DUYET]
        ).update(trang_thai=TrangThaiDoiTra.HOAN_TAT, thoi_diem_hoan_tat=bay_gio,
                 ma_van_don_doi=ma_van_don_doi or None)
        if so_dong == 0:
            raise LoiNghiepVuHauMai("Yêu cầu đã được xử lý")

        tien_tra = Decimal(0)
        chenh_lech = Decimal(0)
        for d in DongDoiTra.objects.filter(yeu_cau=yc).select_related("chi_tiet_don_hang__bien_the", "bien_the_doi"):
            if d.so_luong_dat <= 0:
                continue
            ct = d.chi_tiet_don_hang
            if not yc.khong_thu_hoi_hang:  # BR04: hàng thật sự về kho mới ghi nhập
                DichVuKho.ghi_nhan(
                    don, ct.bien_the, d.so_luong_dat, d.kho_nhap or KhoNhap.KHO_BAN,
                    LyDoBienDongKho.DOI_HANG_NHAN_VE if yc.hinh_thuc == HinhThucDoiTra.DOI else LyDoBienDongKho.TRA_HANG,
                    yc.ma_yc_doi_tra, nhan_vien)
            if yc.hinh_thuc == HinhThucDoiTra.TRA:
                tien_tra += Decimal(ct.don_gia) * d.so_luong_dat
            else:
                if not DichVuKho.con_hang(d.bien_the_doi, d.so_luong_dat):  # E6, BR17
                    raise LoiNghiepVuHauMai("Sản phẩm đổi không đủ tồn kho")
                DichVuKho.ghi_nhan(don, d.bien_the_doi, -d.so_luong_dat, KhoNhap.KHO_BAN,
                                   LyDoBienDongKho.DOI_HANG_XUAT, yc.ma_yc_doi_tra, nhan_vien)
                chenh_lech += (gia_hien_hanh(ct, d.bien_the_doi) - Decimal(ct.don_gia)) * d.so_luong_dat  # BR17

        khoan = None
        if yc.hinh_thuc == HinhThucDoiTra.TRA:
            khoan = DichVuHoanTien.tao_khoan_hoan(don, NguonHoanTien.TRA_HANG, tien_tra, yeu_cau_doi_tra=yc)
        elif chenh_lech < 0:  # A2: chênh lệch giảm -> hoàn phần chênh theo BR08
            khoan = DichVuHoanTien.tao_khoan_hoan(don, NguonHoanTien.CHENH_LECH_DOI, -chenh_lech, yeu_cau_doi_tra=yc)
        YeuCauDoiTra.objects.filter(pk=yc.pk).update(chenh_lech_gia=chenh_lech)

        ghi_chu = None
        if chenh_lech > 0:  # chênh lệch tăng: khách thanh toán thêm (thu tiền nằm ngoài M4)
            ghi_chu = f"Khách thanh toán thêm {chenh_lech:,.0f}đ chênh lệch giá."
        ghi_moc(don, LoaiYeuCau.DOI_TRA, ma_yc_doi_tra, "Hoàn tất xử lý đổi/trả", TrangThaiDoiTra.HOAN_TAT,
                TacNhan.NHAN_VIEN, nhan_vien, ghi_chu=ghi_chu, thoi_diem=bay_gio)
        dat_hau_mai(don, HM_CHO_DOI_TRA if YeuCauDoiTra.objects.filter(
            don_hang=don, trang_thai__in=DOI_TRA_DANG_MO).exists() else HM_DA_DOI_TRA)
        noi_dung = f"Đơn {don.ma_dh}: yêu cầu đổi/trả {ma_yc_doi_tra} đã hoàn tất."
        if khoan:
            noi_dung += " Khoản hoàn tiền sẽ được xử lý."
        if ghi_chu:
            noi_dung += " " + ghi_chu
        DichVuThongBao.gui_khach(don, "Yêu cầu đổi/trả đã hoàn tất", noi_dung)
        DichVuThanhToan.xet_hoan_thanh(DonHang.objects.get(pk=don.pk))  # M3-BR22

    @staticmethod
    def dong_yeu_cau_het_han():
        """M4-BR16: khách không gửi hàng về trong 7 ngày kể từ khi duyệt -> tự đóng "Hết hạn gửi hàng".
        Chạy lại nhiều lần không đổi kết quả. Trả về số yêu cầu đã đóng."""
        so = 0
        qua_han = YeuCauDoiTra.objects.select_related("don_hang").filter(
            trang_thai=TrangThaiDoiTra.DANG_CHO_NHAN_HANG, han_gui_hang__lt=timezone.now())
        for yc in qua_han:
            don = yc.don_hang
            with transaction.atomic():
                if YeuCauDoiTra.objects.filter(
                        pk=yc.pk, trang_thai=TrangThaiDoiTra.DANG_CHO_NHAN_HANG
                ).update(trang_thai=TrangThaiDoiTra.HET_HAN_GUI_HANG) == 0:
                    continue
                dat_hau_mai(don, hau_mai_sau_khi_dong_doi_tra(don, yc.hau_mai_truoc))
                ghi_moc(don, LoaiYeuCau.DOI_TRA, yc.ma_yc_doi_tra, "Hết hạn gửi hàng", TrangThaiDoiTra.HET_HAN_GUI_HANG,
                        TacNhan.HE_THONG, ghi_chu="Quá hạn khách gửi hàng về, yêu cầu tự đóng.", thoi_diem=yc.han_gui_hang)
                DichVuThongBao.gui_khach(don, "Yêu cầu đổi/trả hết hạn",
                                         f"Đơn {don.ma_dh}: yêu cầu {yc.ma_yc_doi_tra} đã đóng do quá hạn gửi hàng.")
                DichVuThanhToan.xet_hoan_thanh(DonHang.objects.get(pk=don.pk))
            so += 1
        return so


# ==========================================================
# 11. THỐNG KÊ NGUYÊN NHÂN – M4-UC08 (M4-BR11). Chỉ đọc, không sửa dữ liệu.
# ==========================================================
SO_NGAY_TOI_DA = 366


def kiem_tra_khoang_ngay(tu_ngay, den_ngay):
    """Dùng chung cho UC08 (BR11) và UC09: bắt đầu không sau kết thúc, không chọn ngày tương lai, tối đa 366 ngày."""
    if tu_ngay and den_ngay and tu_ngay > den_ngay:
        raise LoiNghiepVuHauMai("Từ ngày không được lớn hơn Đến ngày.")
    hom_nay = timezone.localdate()
    if (tu_ngay and tu_ngay > hom_nay) or (den_ngay and den_ngay > hom_nay):
        raise LoiNghiepVuHauMai("Không được chọn ngày trong tương lai.")
    if tu_ngay and den_ngay and (den_ngay - tu_ngay).days + 1 > SO_NGAY_TOI_DA:
        raise LoiNghiepVuHauMai(f"Khoảng thời gian tối đa {SO_NGAY_TOI_DA} ngày.")


class DichVuThongKe:

    @staticmethod
    def _dem_theo_nguyen_nhan(loai, tu_ngay, den_ngay):
        """Trả về {ma_nguyen_nhan: (số lượng, tổng giá trị đơn)} cho yêu cầu đã xử lý xong trong kỳ."""
        if loai == LoaiXuLy.HUY_DON:
            ds = YeuCauHuy.objects.filter(
                trang_thai__in=[TrangThaiYeuCauHuy.DA_DUYET, TrangThaiYeuCauHuy.TU_CHOI],
                thoi_diem_xu_ly__date__gte=tu_ngay, thoi_diem_xu_ly__date__lte=den_ngay)
        elif loai == LoaiXuLy.GIAO_THAT_BAI:
            ds = XuLyGiaoThatBai.objects.filter(thoi_diem__date__gte=tu_ngay, thoi_diem__date__lte=den_ngay)
        else:
            ds = YeuCauDoiTra.objects.filter(
                trang_thai__in=[TrangThaiDoiTra.DA_DUYET, TrangThaiDoiTra.DANG_CHO_NHAN_HANG,
                                TrangThaiDoiTra.DA_NHAN_HANG, TrangThaiDoiTra.HOAN_TAT, TrangThaiDoiTra.TU_CHOI],
                thoi_diem_xu_ly__date__gte=tu_ngay, thoi_diem_xu_ly__date__lte=den_ngay)
        dong = ds.values("nguyen_nhan_id").annotate(so=Count("pk"), gia_tri=Sum("don_hang__tong_thanh_toan"))
        return {d["nguyen_nhan_id"]: (d["so"], d["gia_tri"] or Decimal(0)) for d in dong}

    @staticmethod
    def thong_ke(tu_ngay=None, den_ngay=None, loai_xu_ly=None):
        hom_nay = timezone.localdate()
        if tu_ngay is None and den_ngay is None:  # mặc định: tháng hiện tại
            tu_ngay, den_ngay = hom_nay.replace(day=1), hom_nay
        tu_ngay, den_ngay = tu_ngay or den_ngay.replace(day=1), den_ngay or hom_nay
        kiem_tra_khoang_ngay(tu_ngay, den_ngay)
        if loai_xu_ly and loai_xu_ly not in LoaiXuLy.values:
            raise LoiNghiepVuHauMai("Loại xử lý không hợp lệ.")

        so_ngay = (den_ngay - tu_ngay).days + 1
        truoc_den = tu_ngay - timedelta(days=1)
        truoc_tu = truoc_den - timedelta(days=so_ngay - 1)
        cac_loai = [loai_xu_ly] if loai_xu_ly else list(LoaiXuLy.values)
        ten_nn = {n.ma_nguyen_nhan: n for n in NguyenNhan.objects.all()}  # gồm cả nguyên nhân đã ngưng (BR11)

        the_tong_hop, chi_tiet = [], []
        for loai in cac_loai:
            ky_nay = DichVuThongKe._dem_theo_nguyen_nhan(loai, tu_ngay, den_ngay)
            ky_truoc = DichVuThongKe._dem_theo_nguyen_nhan(loai, truoc_tu, truoc_den)
            tong = sum(v[0] for v in ky_nay.values())
            tong_truoc = sum(v[0] for v in ky_truoc.values())
            the_tong_hop.append({
                "loai_xu_ly": loai, "ten_loai_xu_ly": dict(LoaiXuLy.choices)[loai], "tong": tong,
                "ky_truoc": tong_truoc,
                "thay_doi_phan_tram": None if tong_truoc == 0 else round((tong - tong_truoc) / tong_truoc * 100, 1),
            })
            for ma, (so, gia_tri) in sorted(ky_nay.items(), key=lambda x: -x[1][0]):
                nn = ten_nn.get(ma)
                chi_tiet.append({
                    "ma_nguyen_nhan": ma, "ten_nguyen_nhan": nn.ten_nguyen_nhan if nn else ma,
                    "loai_xu_ly": loai, "ten_loai_xu_ly": dict(LoaiXuLy.choices)[loai], "so_luong": so,
                    "ty_le": None if tong == 0 else round(so / tong * 100, 1),  # mẫu số 0 -> hiển thị "—"
                    "gia_tri_don": gia_tri, "dang_ap_dung": bool(nn and nn.dang_ap_dung),
                })
        khong_co = not chi_tiet
        return {
            "tu_ngay": tu_ngay, "den_ngay": den_ngay, "ky_truoc": {"tu_ngay": truoc_tu, "den_ngay": truoc_den},
            "the_tong_hop": the_tong_hop, "chi_tiet": chi_tiet, "khong_co_du_lieu": khong_co,
            "thong_bao": "Kỳ đã chọn chưa có dữ liệu." if khong_co else None,
        }

    @staticmethod
    def xuat_csv(ket_qua):
        """UC08 bước 5: xuất báo cáo theo bộ lọc hiện tại. Có BOM để Excel đọc đúng tiếng Việt."""
        dem = io.StringIO()
        dem.write("﻿")
        w = csv.writer(dem)
        w.writerow(["Nguyên nhân", "Loại xử lý", "Số lượng", "Tỷ lệ %", "Giá trị đơn liên quan", "Đang áp dụng"])
        for d in ket_qua["chi_tiet"]:
            w.writerow([d["ten_nguyen_nhan"], d["ten_loai_xu_ly"], d["so_luong"],
                        "—" if d["ty_le"] is None else d["ty_le"], d["gia_tri_don"],
                        "Có" if d["dang_ap_dung"] else "Không"])
        return dem.getvalue()


# ==========================================================
# 12. TRA CỨU LỊCH SỬ VÀ TIMELINE – M4-UC09 (M4-BR12, M4-BR13). Chỉ đọc.
#     Khách chỉ thấy yêu cầu của chính mình và không thấy ghi chú nội bộ (view dùng
#     serializer riêng cho khách). Phạm vi nhân viên: mọi yêu cầu, nếu có quyền XEM_LICH_SU.
# ==========================================================
NHAN_TRANG_THAI = {
    LoaiYeuCau.HUY_DON: dict(TrangThaiYeuCauHuy.choices),
    LoaiYeuCau.DOI_TRA: dict(TrangThaiDoiTra.choices),
    LoaiYeuCau.HOAN_TIEN: dict(TrangThaiHoanTien.choices),
    LoaiYeuCau.GIAO_THAT_BAI: dict(HuongXuLyGiao.choices),
}


def _hang(loai, ma, don, nn, trang_thai, thoi_diem_tao, nguoi=None):
    return {
        "loai_yeu_cau": loai, "ten_loai_yeu_cau": dict(LoaiYeuCau.choices)[loai], "ma_yeu_cau": ma,
        "ma_dh": don.ma_dh, "nguyen_nhan": nn.ten_nguyen_nhan if nn else None, "ma_nguyen_nhan": nn.ma_nguyen_nhan if nn else None,
        "trang_thai": trang_thai, "ten_trang_thai": NHAN_TRANG_THAI[loai].get(trang_thai, trang_thai),
        "thoi_diem_tao": thoi_diem_tao, "khach_hang": don.khach_hang.ho_ten,
    }


class DichVuLichSu:

    @staticmethod
    def tra_cuu(khach_hang=None, tu_khoa="", loai=None, trang_thai=None, tu_ngay=None, den_ngay=None,
                ma_nguyen_nhan=None, trang=1):
        """khach_hang != None: phạm vi khách (chỉ của mình). khach_hang = None: phạm vi nhân viên."""
        kiem_tra_khoang_ngay(tu_ngay, den_ngay)
        DichVuDoiTra.dong_yeu_cau_het_han()
        tu_khoa = (tu_khoa or "").strip()

        def loc(ds, truong_ngay, don_truong="don_hang"):
            if khach_hang is not None:
                ds = ds.filter(**{f"{don_truong}__khach_hang": khach_hang})
            if tu_ngay:
                ds = ds.filter(**{f"{truong_ngay}__date__gte": tu_ngay})
            if den_ngay:
                ds = ds.filter(**{f"{truong_ngay}__date__lte": den_ngay})
            if tu_khoa:
                dieu_kien = Q(**{f"{don_truong}__ma_dh__icontains": tu_khoa})
                if khach_hang is None:  # nhân viên tìm thêm theo tên/số điện thoại khách
                    dieu_kien |= Q(**{f"{don_truong}__khach_hang__ho_ten__icontains": tu_khoa}) | Q(
                        **{f"{don_truong}__khach_hang__so_dien_thoai__icontains": tu_khoa})
                ds = ds.filter(dieu_kien | Q(pk__icontains=tu_khoa))
            return ds

        hang = []
        if loai in (None, "", LoaiYeuCau.HUY_DON):
            ds = loc(YeuCauHuy.objects.select_related("don_hang__khach_hang", "nguyen_nhan"), "thoi_diem_gui")
            if trang_thai:
                ds = ds.filter(trang_thai=trang_thai)
            if ma_nguyen_nhan:
                ds = ds.filter(nguyen_nhan_id=ma_nguyen_nhan)
            hang += [_hang(LoaiYeuCau.HUY_DON, y.ma_yc_huy, y.don_hang, y.nguyen_nhan, y.trang_thai, y.thoi_diem_gui) for y in ds]
        if loai in (None, "", LoaiYeuCau.DOI_TRA):
            ds = loc(YeuCauDoiTra.objects.select_related("don_hang__khach_hang", "nguyen_nhan"), "thoi_diem_gui")
            if trang_thai:
                ds = ds.filter(trang_thai=trang_thai)
            if ma_nguyen_nhan:
                ds = ds.filter(nguyen_nhan_id=ma_nguyen_nhan)
            hang += [_hang(LoaiYeuCau.DOI_TRA, y.ma_yc_doi_tra, y.don_hang, y.nguyen_nhan, y.trang_thai, y.thoi_diem_gui) for y in ds]
        if loai in (None, "", LoaiYeuCau.GIAO_THAT_BAI):
            ds = loc(XuLyGiaoThatBai.objects.select_related("don_hang__khach_hang", "nguyen_nhan"), "thoi_diem")
            if trang_thai:
                ds = ds.filter(huong_xu_ly=trang_thai)
            if ma_nguyen_nhan:
                ds = ds.filter(nguyen_nhan_id=ma_nguyen_nhan)
            hang += [_hang(LoaiYeuCau.GIAO_THAT_BAI, x.ma_xu_ly, x.don_hang, x.nguyen_nhan, x.huong_xu_ly, x.thoi_diem) for x in ds]
        if loai in (None, "", LoaiYeuCau.HOAN_TIEN) and not ma_nguyen_nhan:
            ds = loc(GiaoDichHoanTien.objects.select_related("don_hang__khach_hang"), "thoi_diem_tao")
            if trang_thai:
                ds = ds.filter(trang_thai=trang_thai)
            hang += [_hang(LoaiYeuCau.HOAN_TIEN, h.ma_hoan_tien, h.don_hang, None, h.trang_thai, h.thoi_diem_tao) for h in ds]

        # Thời điểm cập nhật cuối = mốc timeline mới nhất của từng yêu cầu
        ma_ds = [h["ma_yeu_cau"] for h in hang]
        moi_nhat = {(m["loai_yeu_cau"], m["ma_yeu_cau"]): m["moi_nhat"] for m in
                    LichSuHauMai.objects.filter(ma_yeu_cau__in=ma_ds).values("loai_yeu_cau", "ma_yeu_cau")
                    .annotate(moi_nhat=Max("thoi_diem"))}
        for h in hang:
            h["cap_nhat_cuoi"] = moi_nhat.get((h["loai_yeu_cau"], h["ma_yeu_cau"]), h["thoi_diem_tao"])
        hang.sort(key=lambda h: (h["thoi_diem_tao"], h["ma_yeu_cau"]), reverse=True)  # mới nhất trước
        return Paginator(hang, SO_DONG_MOI_TRANG).get_page(trang)

    @staticmethod
    def _tim_yeu_cau(loai, ma):
        """Trả về (đơn hàng, đối tượng yêu cầu) theo loại."""
        mo_hinh = {LoaiYeuCau.HUY_DON: YeuCauHuy, LoaiYeuCau.DOI_TRA: YeuCauDoiTra,
                   LoaiYeuCau.GIAO_THAT_BAI: XuLyGiaoThatBai, LoaiYeuCau.HOAN_TIEN: GiaoDichHoanTien}.get(loai)
        if mo_hinh is None:
            raise LoiNghiepVuHauMai("Loại yêu cầu không hợp lệ.")
        doi_tuong = mo_hinh.objects.select_related("don_hang__khach_hang").filter(pk=ma).first()
        if doi_tuong is None:
            raise LoiNghiepVuHauMai("Không tìm thấy yêu cầu.")
        return doi_tuong.don_hang, doi_tuong

    @staticmethod
    def timeline(loai, ma, khach_hang=None):
        """Bước 4: kiểm tra quyền xem rồi trả timeline. khach_hang != None thì phải là chủ đơn (E2)."""
        don, doi_tuong = DichVuLichSu._tim_yeu_cau(loai, ma)
        if khach_hang is not None and don.khach_hang_id != khach_hang.ma_kh:
            raise LoiQuyenHauMai("Bạn không đủ quyền truy cập")
        cac_moc = LichSuHauMai.objects.filter(loai_yeu_cau=loai, ma_yeu_cau=ma).select_related("nhan_vien")
        lien_quan = []  # liên kết sang yêu cầu liên quan (ví dụ yêu cầu trả hàng và khoản hoàn tiền tương ứng)
        if loai == LoaiYeuCau.DOI_TRA:
            lien_quan += [(LoaiYeuCau.HOAN_TIEN, h.ma_hoan_tien) for h in doi_tuong.hoan_tien.all()]
        elif loai == LoaiYeuCau.HUY_DON:
            lien_quan += [(LoaiYeuCau.HOAN_TIEN, h.ma_hoan_tien) for h in doi_tuong.hoan_tien.all()]
        elif loai == LoaiYeuCau.GIAO_THAT_BAI:
            lien_quan += [(LoaiYeuCau.HOAN_TIEN, h.ma_hoan_tien) for h in doi_tuong.hoan_tien.all()]
        elif loai == LoaiYeuCau.HOAN_TIEN:
            if doi_tuong.yeu_cau_huy_id:
                lien_quan.append((LoaiYeuCau.HUY_DON, doi_tuong.yeu_cau_huy_id))
            if doi_tuong.yeu_cau_doi_tra_id:
                lien_quan.append((LoaiYeuCau.DOI_TRA, doi_tuong.yeu_cau_doi_tra_id))
            if doi_tuong.xu_ly_giao_that_bai_id:
                lien_quan.append((LoaiYeuCau.GIAO_THAT_BAI, doi_tuong.xu_ly_giao_that_bai_id))
        return don, doi_tuong, list(cac_moc), lien_quan
