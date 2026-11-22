from customers.models import TaiKhoan
from config.decorators import role_required


def manager_or_report_staff_required(view_func):
    """
    Quy tắc M5-BR11/12: chỉ Quản lý (MANAGER) mới được xem và xuất báo cáo.
    """
    return role_required(TaiKhoan.VaiTro.MANAGER)(view_func)