from django.urls import path
from . import views

# Đặt tên ứng dụng để tiện gọi trong HTML
app_name = 'products'

urlpatterns = [
    # Đường dẫn xem danh sách: http://127.0.0.1:8000/products/
    path('', views.danh_sach_san_pham, name='danh_sach'),

    # Đường dẫn xem chi tiết: http://127.0.0.1:8000/products/SP001/
    path('<str:ma_sp>/', views.chi_tiet_san_pham, name='chi_tiet'),
]