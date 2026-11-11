# File: backend/after_sales/permissions.py
# Module 4 – Phân quyền (M4-BR14). Kiểm tra ở máy chủ, có hiệu lực ngay ở lần truy cập tiếp theo
# vì mỗi request đọc lại tài khoản và hồ sơ từ CSDL. Tài khoản bị khóa không thao tác được.
#
# Cách làm theo M1 (customers/permissions.py): một bảng "vai trò -> tập quyền" và một lớp
# permission đọc thuộc tính `quyen_yeu_cau` của view.
# Hiện tại EMPLOYEE và MANAGER được cấp đủ quyền như nhau vì M1 chưa có bảng phân quyền chi tiết
# theo chức năng; muốn tách (ví dụ chỉ MANAGER xem thống kê) chỉ cần sửa MA_TRAN_QUYEN_HAU_MAI.

from rest_framework.permissions import BasePermission

from customers.models import TaiKhoan
from orders.permissions import KhachHangCoHoSo, NhanVienCoHoSo


class QuyenHauMai:
    XU_LY_HUY_DON = "XU_LY_HUY_DON"
    XU_LY_GIAO_HANG = "XU_LY_GIAO_HANG"
    XU_LY_DOI_TRA = "XU_LY_DOI_TRA"
    XU_LY_HOAN_TIEN = "XU_LY_HOAN_TIEN"
    QUAN_LY_NGUYEN_NHAN = "QUAN_LY_NGUYEN_NHAN"
    XEM_THONG_KE = "XEM_THONG_KE"
    XEM_LICH_SU = "XEM_LICH_SU"


TAT_CA_QUYEN = {
    QuyenHauMai.XU_LY_HUY_DON, QuyenHauMai.XU_LY_GIAO_HANG, QuyenHauMai.XU_LY_DOI_TRA,
    QuyenHauMai.XU_LY_HOAN_TIEN, QuyenHauMai.QUAN_LY_NGUYEN_NHAN, QuyenHauMai.XEM_THONG_KE,
    QuyenHauMai.XEM_LICH_SU,
}

MA_TRAN_QUYEN_HAU_MAI = {
    TaiKhoan.VaiTro.CUSTOMER: set(),
    TaiKhoan.VaiTro.EMPLOYEE: set(TAT_CA_QUYEN),
    TaiKhoan.VaiTro.MANAGER: set(TAT_CA_QUYEN),
}


def tai_khoan_hoat_dong(tai_khoan):
    return bool(tai_khoan and tai_khoan.is_authenticated and tai_khoan.is_active
                and tai_khoan.trang_thai == TaiKhoan.TrangThai.ACTIVE)


def co_quyen_hau_mai(tai_khoan, quyen):
    if not tai_khoan_hoat_dong(tai_khoan):
        return False
    return quyen in MA_TRAN_QUYEN_HAU_MAI.get(tai_khoan.vai_tro, set())


class KhachHangHauMai(KhachHangCoHoSo):
    """Khách hàng có hồ sơ (của M3) và tài khoản không bị khóa: chỉ dùng chức năng gửi yêu cầu và tra cứu của mình."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if not tai_khoan_hoat_dong(request.user):
            self.message = "Tài khoản đã bị khóa."
            return False
        return True


class NhanVienHauMai(NhanVienCoHoSo):
    """Nhân viên có hồ sơ đang hoạt động (của M3) VÀ có quyền do view khai báo trong `quyen_yeu_cau`."""

    message = "Bạn không đủ quyền truy cập."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        quyen = getattr(view, "quyen_yeu_cau", None)
        if quyen is None or not co_quyen_hau_mai(request.user, quyen):
            self.message = "Bạn không đủ quyền truy cập."
            return False
        return True


class KhachHoacNhanVienXemLichSu(BasePermission):
    """M4-UC09: khách hàng (của chính mình) hoặc nhân viên có quyền XEM_LICH_SU."""

    message = "Bạn không đủ quyền truy cập."

    def has_permission(self, request, view):
        if not tai_khoan_hoat_dong(request.user):
            return False
        if request.user.vai_tro == TaiKhoan.VaiTro.CUSTOMER:
            return hasattr(request.user, "khach_hang")
        return (co_quyen_hau_mai(request.user, QuyenHauMai.XEM_LICH_SU)
                and hasattr(request.user, "nhan_vien") and request.user.nhan_vien.trang_thai == "ACTIVE")
