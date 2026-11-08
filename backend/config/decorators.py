
from functools import wraps

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.http import HttpResponseForbidden

from customers.models import TaiKhoan, KhachHang, NhanVien


def role_required(*allowed_roles):
    """
    Bảo vệ Django HTML views theo vai trò tài khoản.

    Kiểm tra:
    - Người dùng đã đăng nhập.
    - Tài khoản đang hoạt động.
    - Hồ sơ liên kết tồn tại.
    - Hồ sơ đang hoạt động.
    - Vai trò được phép truy cập trang.
    """

    def decorator(view_func):

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            user = request.user

            # 1. Kiểm tra đăng nhập
            if not user.is_authenticated:
                return redirect("login-page")

            # 2. Kiểm tra trạng thái tài khoản
            if (
                user.trang_thai != TaiKhoan.TrangThai.ACTIVE
                or not user.is_active
            ):
                logout(request)
                return redirect("login-page")

            # 3. Kiểm tra hồ sơ theo vai trò
            if user.vai_tro in [
                TaiKhoan.VaiTro.EMPLOYEE,
                TaiKhoan.VaiTro.MANAGER,
            ]:
                nhan_vien = NhanVien.objects.filter(
                    tai_khoan=user
                ).first()

                if (
                    nhan_vien is None
                    or nhan_vien.trang_thai
                    != NhanVien.TrangThai.ACTIVE
                ):
                    logout(request)
                    return redirect("login-page")

            elif user.vai_tro == TaiKhoan.VaiTro.CUSTOMER:
                khach_hang = KhachHang.objects.filter(
                    tai_khoan=user
                ).first()

                if (
                    khach_hang is None
                    or khach_hang.trang_thai
                    != KhachHang.TrangThai.ACTIVE
                ):
                    logout(request)
                    return redirect("login-page")

            else:
                logout(request)
                return redirect("login-page")

            # 4. Kiểm tra vai trò được phép truy cập
            if user.vai_tro not in allowed_roles:
                return HttpResponseForbidden(
                    "Bạn không có quyền truy cập trang này."
                )

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
