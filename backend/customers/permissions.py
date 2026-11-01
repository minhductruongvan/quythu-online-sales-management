from rest_framework.permissions import BasePermission

from .models import TaiKhoan


class QuyenKhachHang:
    XEM_DANH_SACH = "XEM_DANH_SACH"
    XEM_CHI_TIET = "XEM_CHI_TIET"
    TAO_KHACH_HANG = "TAO_KHACH_HANG"
    CAP_NHAT_KHACH_HANG = "CAP_NHAT_KHACH_HANG"
    PHAN_LOAI = "PHAN_LOAI"
    DOI_TRANG_THAI = "DOI_TRANG_THAI"
    KHOA_MO_TAI_KHOAN = "KHOA_MO_TAI_KHOAN"


MA_TRAN_QUYEN_KHACH_HANG = {
    TaiKhoan.VaiTro.CUSTOMER: set(),

    TaiKhoan.VaiTro.EMPLOYEE: {
        QuyenKhachHang.XEM_DANH_SACH,
        QuyenKhachHang.XEM_CHI_TIET,
        QuyenKhachHang.TAO_KHACH_HANG,
        QuyenKhachHang.CAP_NHAT_KHACH_HANG,
        QuyenKhachHang.PHAN_LOAI,
        QuyenKhachHang.DOI_TRANG_THAI,
        QuyenKhachHang.KHOA_MO_TAI_KHOAN,
    },

    TaiKhoan.VaiTro.MANAGER: {
        QuyenKhachHang.XEM_DANH_SACH,
        QuyenKhachHang.XEM_CHI_TIET,
        QuyenKhachHang.TAO_KHACH_HANG,
        QuyenKhachHang.CAP_NHAT_KHACH_HANG,
        QuyenKhachHang.PHAN_LOAI,
        QuyenKhachHang.DOI_TRANG_THAI,
        QuyenKhachHang.KHOA_MO_TAI_KHOAN,
    },
}


def co_quyen_khach_hang(tai_khoan, quyen):
    """
    Kiểm tra tài khoản có một quyền nghiệp vụ
    trong module quản lý khách hàng hay không.
    """
    if not tai_khoan or not tai_khoan.is_authenticated:
        return False

    cac_quyen = MA_TRAN_QUYEN_KHACH_HANG.get(
        tai_khoan.vai_tro,
        set(),
    )

    return quyen in cac_quyen


class CoQuyenKhachHang(BasePermission):
    message = "Bạn không có quyền thực hiện chức năng này."

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        quyen_yeu_cau = getattr(
            view,
            "quyen_yeu_cau",
            None,
        )
        quyen_theo_method = getattr(
            view,
            "quyen_theo_method",
            {},
        )

        if request.method in quyen_theo_method:
            return co_quyen_khach_hang(
                request.user,
                quyen_theo_method[request.method],
            )
        if quyen_yeu_cau is None:
            return False

        return co_quyen_khach_hang(
            request.user,
            quyen_yeu_cau,
        )


class IsCustomer(BasePermission):
    message = "Chức năng này chỉ dành cho khách hàng."

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.vai_tro == TaiKhoan.VaiTro.CUSTOMER
        )


class IsEmployeeOrManager(BasePermission):
    message = "Bạn không có quyền thực hiện chức năng này."

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.vai_tro
            in [
                TaiKhoan.VaiTro.EMPLOYEE,
                TaiKhoan.VaiTro.MANAGER,
            ]
        )