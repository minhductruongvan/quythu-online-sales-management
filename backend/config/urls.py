
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),

    # M1 - Quản lý tài khoản và khách hàng
    path("api/customers/", include("customers.urls")),

    # M2 - Quản lý sản phẩm và danh mục
    path("products/", include("products.urls")),

    # M3 - Quản lý bán hàng và đơn hàng
    path("api/orders/", include("orders.urls")),
]

# Phục vụ file media trong môi trường development
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
