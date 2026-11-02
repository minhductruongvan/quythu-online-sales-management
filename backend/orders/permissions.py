# File: backend/orders/permissions.py
# Module 3 – Phân quyền cho API giỏ hàng, đặt hàng, đơn hàng.
#
# Phân quyền ở file này chỉ trả lời câu hỏi "AI được gọi API này?",
# dựa trên tài khoản đang đăng nhập. Câu hỏi "được thao tác trên DÒNG DỮ LIỆU
# NÀO?" (giỏ của chính mình, địa chỉ của chính mình – M3-BR24) nằm trong
# services.py, vì phải đọc dữ liệu lên mới biết chủ sở hữu.
#
# Dùng lại lớp của M1 (customers/permissions.py), không viết lại:
#   - IsCustomer: đã đăng nhập và vai_tro = CUSTOMER.
#   - IsEmployeeOrManager: đã đăng nhập và vai_tro = EMPLOYEE hoặc MANAGER.

from customers.models import NhanVien
from customers.permissions import IsCustomer, IsEmployeeOrManager


class KhachHangCoHoSo(IsCustomer):
    """
    Dùng cho M3-UC01 đến M3-UC06 (phía khách hàng).
    Điều kiện: đủ điều kiện IsCustomer của M1 VÀ tài khoản có hồ sơ KhachHang,
    vì mọi hàm trong services.py đều cần đối tượng KhachHang
    (lấy bằng request.user.khach_hang).
    """

    def has_permission(self, request, view):
        # Bước 1: điều kiện của M1. Sai thì DRF trả câu báo của M1:
        # "Chức năng này chỉ dành cho khách hàng."
        if not super().has_permission(request, view):
            return False

        # Bước 2: tài khoản CUSTOMER nhưng chưa có dòng KhachHang đi kèm
        if not hasattr(request.user, "khach_hang"):
            self.message = "Tài khoản không có hồ sơ khách hàng."
            return False

        return True


class NhanVienCoHoSo(IsEmployeeOrManager):
    """
    Dùng cho M3-UC07 đến M3-UC13 (phía nhân viên, quản lý).
    Điều kiện (tiền điều kiện của các UC, M1-BR14): vai trò EMPLOYEE hoặc MANAGER
    của M1, có hồ sơ NhanVien, và hồ sơ đang hoạt động. Các service phía nhân
    viên cần đối tượng NhanVien (lấy bằng request.user.nhan_vien) để ghi người thao tác.
    """

    message = "Bạn không đủ quyền truy cập."  # câu báo của M3-UC07 E1

    def has_permission(self, request, view):
        # Bước 1: điều kiện vai trò của M1
        if not super().has_permission(request, view):
            return False

        # Bước 2: tài khoản nhân viên nhưng chưa có dòng NhanVien đi kèm
        if not hasattr(request.user, "nhan_vien"):
            self.message = "Tài khoản không có hồ sơ nhân viên."
            return False

        # Bước 3: hồ sơ nhân viên đã ngừng hoạt động
        if request.user.nhan_vien.trang_thai != NhanVien.TrangThai.ACTIVE:
            self.message = "Hồ sơ nhân viên đang ngừng hoạt động."
            return False

        return True