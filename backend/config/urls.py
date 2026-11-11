from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

from .views import (
    customer_purchase_history_page,
    employee_customer_list_page,
    order_list,
    login_page,
    register_page,
    customer_profile_page,
    customer_address_page,
    employee_customer_add_page,
    employee_customer_detail_page,
    employee_customer_export_page,
    employee_customer_import_page,
    storefront_home_page,
    employee_dashboard_page,
    manager_dashboard_page,
    manager_role_permissions_page,
    logout_page,
)
from .web_views import (
    cart_page,
    checkout_page,
    customer_after_sales_page,
    customer_order_detail_page,
    customer_orders_page,
    staff_after_sales_page,
    staff_order_detail_page,
)


urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),

    # Giao diện tài khoản M1
    path(
        "tai-khoan/dang-nhap/",
        login_page,
        name="login-page",
    ),
    path(
        "tai-khoan/dang-ky/",
        register_page,
        name="register-page",
    ),
    path(
        "tai-khoan/dang-xuat/",
        logout_page,
        name="dang-xuat-giao-dien",
    ),
    path(
        "tai-khoan/thong-tin/",
        customer_profile_page,
        name="customer-profile-page",
    ),
    path(
        "tai-khoan/dia-chi/",
        customer_address_page,
        name="customer-address-page",
    ),
    path(
        "tai-khoan/lich-su-mua-hang/",
        customer_purchase_history_page,
        name="customer-purchase-history-page",
    ),
    path("tai-khoan/hau-mai/", customer_after_sales_page, name="customer-after-sales"),
    path("gio-hang/", cart_page, name="cart-page"),
    path("thanh-toan/", checkout_page, name="checkout-page"),
    path("don-cua-toi/", customer_orders_page, name="customer-orders-page"),
    path(
        "don-cua-toi/<str:ma_dh>/",
        customer_order_detail_page,
        name="customer-order-detail-page",
    ),

    # Quản lý khách hàng M1
    path(
        "quan-ly/khach-hang/them/",
        employee_customer_add_page,
        name="employee-customer-add",
    ),
    path(
        "quan-ly/khach-hang/nhap/",
        employee_customer_import_page,
        name="employee-customer-import",
    ),
    path(
        "quan-ly/khach-hang/xuat/",
        employee_customer_export_page,
        name="employee-customer-export",
    ),
    path(
        "quan-ly/khach-hang/<str:ma_kh>/",
        employee_customer_detail_page,
        name="employee-customer-detail",
    ),
    path(
        "quan-ly/khach-hang/",
        employee_customer_list_page,
        name="employee-customer-list",
    ),
    path(
        "quan-ly/phan-quyen/",
        manager_role_permissions_page,
        name="manager-role-permissions",
    ),

    # Giao diện hệ thống
    path("", storefront_home_page, name="storefront-home"),
    path(
        "nhan-vien/",
        employee_dashboard_page,
        name="employee-dashboard",
    ),
    path(
        "quan-ly/",
        manager_dashboard_page,
        name="manager-dashboard",
    ),
    path("nhan-vien/hau-mai/", staff_after_sales_page, name="staff-after-sales"),
    path("quan-ly/hau-mai/", staff_after_sales_page, name="manager-after-sales"),
    path("don-hang/", order_list, name="order-list"),
    path("don-hang/<str:ma_dh>/", staff_order_detail_page, name="staff-order-detail"),

    # API M1, M2, M3
    path("api/customers/", include("customers.urls")),
    path("products/", include("products.urls")),
    path("api/orders/", include("orders.urls")),

    # API M4 - Quản lý hậu mãi
    path("api/after-sales/", include("after_sales.urls")),

    # M5 - Quản lý báo cáo và thống kê
    path("reports/", include("reports.urls")),
]


# Phục vụ file media trong môi trường development
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
