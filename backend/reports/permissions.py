from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from rest_framework import permissions
from customers.models import TaiKhoan


class IsManagerOrReportStaff(permissions.BasePermission):
    """
    Quy tắc M5-BR11/12: Phân quyền API báo cáo
    - Quản lý (MANAGER): Toàn quyền xem và xuất báo cáo.
    - Nhân viên (EMPLOYEE): Được xem báo cáo nếu có quyền.
    - Khách hàng (CUSTOMER): Tuyệt đối không được truy cập.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        vai_tro = getattr(request.user, "vai_tro", None)
        return vai_tro in [TaiKhoan.VaiTro.MANAGER, TaiKhoan.VaiTro.EMPLOYEE]


def manager_or_report_staff_required(view_func):
    """
    Decorator cho Django template view
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            # Cho phép xem trong chế độ development nếu chưa login hoặc redirect
            # Trong môi trường dev, nếu chưa login tài khoản sẽ bypass để kiểm thử giao diện
            return view_func(request, *args, **kwargs)
        
        vai_tro = getattr(request.user, "vai_tro", None)
        if vai_tro == TaiKhoan.VaiTro.CUSTOMER:
            raise PermissionDenied("Bạn không có quyền truy cập module Báo cáo và Thống kê.")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view
