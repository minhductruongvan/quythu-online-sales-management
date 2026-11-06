from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from .views import customer_purchase_history_page
from .views import employee_customer_list_page

from .views import (
    dashboard,
    order_list,
    login_page,
    register_page,
    customer_profile_page,
    customer_address_page,
    employee_customer_add_page,
    storefront_home_page,
    employee_dashboard_page,
    manager_dashboard_page,
    logout_page,
)
urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "tai-khoan/dang-xuat/",
        logout_page,
        name="dang-xuat-giao-dien",
    ),
    path(
        "tai-khoan/lich-su-mua-hang/",
        customer_purchase_history_page,
        name="customer-purchase-history-page"
    ),

    path(
        "quan-ly/khach-hang/them/",
        employee_customer_add_page,
        name="employee-customer-add"
    ),

    path(
        "quan-ly/khach-hang/",
        employee_customer_list_page,
        name="employee-customer-list"
    ),
    # Giao diện
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
    path("don-hang/", order_list, name="order-list"),

    # API
    path("api/customers/", include("customers.urls")),
    path("products/", include("products.urls")),
    path("api/orders/", include("orders.urls")),
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
        "tai-khoan/thong-tin/",
        customer_profile_page,
        name="customer-profile-page"
    ),
    path(
        "tai-khoan/dia-chi/",
        customer_address_page,
        name="customer-address-page"
    ),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )