from django.shortcuts import render

from customers.models import TaiKhoan
from orders.models import TinhThanh

from .decorators import role_required


@role_required(TaiKhoan.VaiTro.CUSTOMER)
def cart_page(request):
    return render(request, "orders/cart.html")


@role_required(TaiKhoan.VaiTro.CUSTOMER)
def checkout_page(request):
    return render(
        request,
        "orders/checkout.html",
        {
            "shipping_provinces": TinhThanh.objects.filter(
                dang_hoat_dong=True
            ).order_by("ten_tinh")
        },
    )


@role_required(TaiKhoan.VaiTro.CUSTOMER)
def customer_orders_page(request):
    return render(request, "orders/customer_list.html")


@role_required(TaiKhoan.VaiTro.CUSTOMER)
def customer_order_detail_page(request, ma_dh):
    return render(request, "orders/customer_detail.html", {"ma_dh": ma_dh})


@role_required(TaiKhoan.VaiTro.CUSTOMER)
def customer_after_sales_page(request):
    return render(request, "after_sales/customer.html")


@role_required(TaiKhoan.VaiTro.EMPLOYEE, TaiKhoan.VaiTro.MANAGER)
def staff_order_detail_page(request, ma_dh):
    return render(request, "orders/staff_detail.html", {"ma_dh": ma_dh})


@role_required(TaiKhoan.VaiTro.EMPLOYEE, TaiKhoan.VaiTro.MANAGER)
def staff_after_sales_page(request):
    return render(request, "after_sales/staff.html")
