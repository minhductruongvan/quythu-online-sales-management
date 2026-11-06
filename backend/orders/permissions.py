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

from customers.models import NhanVien, KhachHang, TaiKhoan
from customers.permissions import IsCustomer, IsEmployeeOrManager


class KhachHangCoHoSo(IsCustomer):
    """
    Dùng cho M3-UC01 đến M3-UC06.
    Yêu cầu tài khoản CUSTOMER hợp lệ, có hồ sơ KhachHang
    và hồ sơ khách hàng đang hoạt động.
    """

    def has_permission(self, request, view):
        user = request.user

        # Bước 1: Kiểm tra đăng nhập
        if not user.is_authenticated:
            return False

        # Bước 2: Kiểm tra trạng thái và vai trò tài khoản
        if (
            not user.is_active
            or user.vai_tro != TaiKhoan.VaiTro.CUSTOMER
            or user.trang_thai != TaiKhoan.TrangThai.ACTIVE
        ):
            self.message = IsCustomer.message
            return False

        # Bước 3: Kiểm tra hồ sơ khách hàng
        try:
            khach_hang = user.khach_hang
        except KhachHang.DoesNotExist:
            self.message = "Tài khoản không có hồ sơ khách hàng."
            return False

        # Bước 4: Kiểm tra trạng thái hồ sơ
        if khach_hang.trang_thai != KhachHang.TrangThai.ACTIVE:
            self.message = "Tài khoản khách hàng đang ngừng hoạt động."
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