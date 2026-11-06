from django.shortcuts import render

from .decorators import role_required
from django.db.models import Prefetch
from customers.models import TaiKhoan, KhachHang, DiaChiKH
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

def dashboard(request):
    return render(request, "dashboard/index.html")


@role_required(
    TaiKhoan.VaiTro.EMPLOYEE,
    TaiKhoan.VaiTro.MANAGER
)
def order_list(request):
    return render(request, "orders/danh_sach.html", {
        "orders": []
    })

# Giao diện đăng nhập M1
def login_page(request):
    return render(request, "storefront/accounts/login.html")


# Giao diện đăng ký M1
def register_page(request):
    return render(request, "storefront/accounts/register.html")

@role_required(TaiKhoan.VaiTro.CUSTOMER)
def customer_address_page(request):
    khach_hang = request.user.khach_hang

    addresses = khach_hang.dia_chi.all().order_by(
        "-mac_dinh",
        "-ngay_cap_nhat",
    )

    return render(
        request,
        "storefront/accounts/addresses.html",
        {
            "addresses": addresses,
        }
    )

@role_required(TaiKhoan.VaiTro.CUSTOMER)
def customer_profile_page(request):
    khach_hang = request.user.khach_hang

    return render(
        request,
        "storefront/accounts/profile.html",
        {
            "customer": {
                "ma_kh": khach_hang.ma_kh,
                "ho_ten": khach_hang.ho_ten,
                "email": request.user.email,
                "so_dien_thoai": request.user.so_dien_thoai,
                "loai_khach_hang": str(khach_hang.loai_khach_hang),
            }
        }
    )

@role_required(TaiKhoan.VaiTro.CUSTOMER)
def customer_purchase_history_page(request):
    demo_orders = [
        {
            "ma_don_hang": "DH2026001",
            "ngay_dat": "01/11/2026",
            "san_pham": "Áo sơ mi nam, Quần kaki",
            "tong_tien": 650000,
            "trang_thai": "Hoàn thành",
            "status_key": "completed",
            "status_class": "status-completed",
            "dia_chi": "123 Nguyễn Văn Linh, Hải Châu, Đà Nẵng",
        },
        {
            "ma_don_hang": "DH2026002",
            "ngay_dat": "02/11/2026",
            "san_pham": "Giày thể thao",
            "tong_tien": 850000,
            "trang_thai": "Đang giao",
            "status_key": "shipping",
            "status_class": "status-shipping",
            "dia_chi": "123 Nguyễn Văn Linh, Hải Châu, Đà Nẵng",
        },
        {
            "ma_don_hang": "DH2026003",
            "ngay_dat": "03/11/2026",
            "san_pham": "Áo thun nam",
            "tong_tien": 250000,
            "trang_thai": "Chờ xác nhận",
            "status_key": "pending",
            "status_class": "status-pending",
            "dia_chi": "45 Lê Duẩn, Hải Châu, Đà Nẵng",
        },
        {
            "ma_don_hang": "DH2026004",
            "ngay_dat": "04/11/2026",
            "san_pham": "Balo thời trang",
            "tong_tien": 420000,
            "trang_thai": "Đã hủy",
            "status_key": "cancelled",
            "status_class": "status-cancelled",
            "dia_chi": "123 Nguyễn Văn Linh, Hải Châu, Đà Nẵng",
        },
    ]

    completed_orders = [
        order for order in demo_orders
        if order["status_key"] == "completed"
    ]

    return render(
        request,
        "storefront/accounts/purchase_history.html",
        {
            "orders": demo_orders,
            "total_orders": len(demo_orders),
            "completed_orders": len(completed_orders),
            "total_spent": sum(
                order["tong_tien"] for order in completed_orders
            ),
        }
    )

@role_required(
    TaiKhoan.VaiTro.EMPLOYEE,
    TaiKhoan.VaiTro.MANAGER
)
@role_required(
    TaiKhoan.VaiTro.EMPLOYEE,
    TaiKhoan.VaiTro.MANAGER
)
def employee_customer_list_page(request):

    customers_queryset = (
        KhachHang.objects
        .select_related(
            "tai_khoan",
            "loai_khach_hang"
        )
        .prefetch_related(
            Prefetch(
                "dia_chi",
                queryset=DiaChiKH.objects.filter(
                    mac_dinh=True
                ),
                to_attr="dia_chi_mac_dinh_list"
            )
        )
        .order_by("-ngay_tao")
    )

    customers = []

    for kh in customers_queryset:

        # Email
        email = (
            kh.tai_khoan.email
            if kh.tai_khoan
            else "Chưa có email"
        )

        # Số điện thoại
        so_dien_thoai = (
            kh.tai_khoan.so_dien_thoai
            if kh.tai_khoan and kh.tai_khoan.so_dien_thoai
            else kh.so_dien_thoai or "Chưa cập nhật"
        )

        # Loại khách hàng
        loai_khach_hang = kh.loai_khach_hang.ten_loai_kh
        type_key = (
            "wholesale"
            if "sỉ" in loai_khach_hang.casefold()
            or "si" in loai_khach_hang.casefold()
            else "retail"
        )

        type_class = (
            "type-wholesale"
            if type_key == "wholesale"
            else "type-retail"
        )

        # Trạng thái khách hàng
        status_key = (
            "active"
            if kh.trang_thai == KhachHang.TrangThai.ACTIVE
            else "inactive"
        )

        status_class = (
            "status-active"
            if status_key == "active"
            else "status-inactive"
        )

        # Địa chỉ mặc định
        dia_chi_mac_dinh = (
            kh.dia_chi_mac_dinh_list[0]
            if kh.dia_chi_mac_dinh_list
            else None
        )

        if dia_chi_mac_dinh:
            dia_chi_parts = [
                dia_chi_mac_dinh.dia_chi_chi_tiet,
                dia_chi_mac_dinh.phuong_xa,
                dia_chi_mac_dinh.quan_huyen,
                dia_chi_mac_dinh.tinh_thanh,
            ]

            dia_chi = ", ".join(
                part for part in dia_chi_parts if part
            )
        else:
            dia_chi = "Chưa cập nhật"

        customers.append({
            "ma_kh": kh.ma_kh,
            "ho_ten": kh.ho_ten,
            "email": email,
            "so_dien_thoai": so_dien_thoai,

            "loai_khach_hang": loai_khach_hang,
            "type_key": type_key,
            "type_class": type_class,

            "ngay_tao": kh.ngay_tao.strftime("%d/%m/%Y"),

            "trang_thai": kh.get_trang_thai_display(),
            "status_key": status_key,
            "status_class": status_class,

            "dia_chi": dia_chi,
        })

    return render(
        request,
        "customers/customer_list.html",
        {
            "customers": customers,
            "total_customers": len(customers),
            "retail_customers": sum(
                c["type_key"] == "retail"
                for c in customers
            ),
            "wholesale_customers": sum(
                c["type_key"] == "wholesale"
                for c in customers
            ),
            "inactive_customers": sum(
                c["status_key"] == "inactive"
                for c in customers
            ),
        }
    )

@role_required(
    TaiKhoan.VaiTro.EMPLOYEE,
    TaiKhoan.VaiTro.MANAGER
)
def employee_customer_add_page(request):
    return render(
        request,
        "customers/customer_add.html"
    )
@role_required(TaiKhoan.VaiTro.CUSTOMER)
def storefront_home_page(request):
    return render(request, "storefront/home.html")


@role_required(TaiKhoan.VaiTro.EMPLOYEE)
def employee_dashboard_page(request):
    return render(request, "dashboard/employee.html")


@role_required(TaiKhoan.VaiTro.MANAGER)
def manager_dashboard_page(request):
    return render(request, "dashboard/manager.html")

@require_POST
def logout_page(request):
    logout(request)
    return redirect("login-page")