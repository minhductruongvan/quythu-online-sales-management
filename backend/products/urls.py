# File: backend/products/urls.py
from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    # ==========================================================================
    # 1. DÀNH CHO KHÁCH HÀNG (USE CASE 1 - M2-UC01)
    # ==========================================================================
    # Trang danh sách sản phẩm
    path('', views.danh_sach_san_pham, name='danh_sach'),

    # Trang xem chi tiết một sản phẩm
    path('chi-tiet/<str:ma_sp>/', views.chi_tiet_san_pham, name='chi_tiet'),

    # ==========================================================================
    # 2. DÀNH CHO NHÂN VIÊN / QUẢN LÝ (USE CASE 2 - M2-UC02)
    # ==========================================================================
    # Quản lý danh sách sản phẩm
    path('quan-ly/', views.quan_ly_san_pham, name='quan_ly'),

    # Thêm sản phẩm mới
    path('quan-ly/them/', views.them_san_pham, name='them'),

    # Sửa sản phẩm
    path('quan-ly/sua/<str:ma_sp>/', views.sua_san_pham, name='sua'),

    # Bật/tắt trạng thái kinh doanh của sản phẩm
    path('quan-ly/doi-trang-thai/<str:ma_sp>/', views.doi_trang_thai_san_pham, name='doi_trang_thai'),

    # Xóa sản phẩm
    path('quan-ly/xoa/<str:ma_sp>/', views.xoa_san_pham, name='xoa'),

    # ==========================================================================
    # 3. QUẢN LÝ BIẾN THỂ SẢN PHẨM (USE CASE 3 - M2-UC03)
    # ==========================================================================
    # Xem danh sách các gói bánh (biến thể) của 1 sản phẩm
    path('quan-ly/bien-the/<str:ma_sp>/', views.danh_sach_bien_the, name='danh_sach_bien_the'),

    # Thêm gói bánh mới cho sản phẩm
    path('quan-ly/bien-the/<str:ma_sp>/them/', views.them_bien_the, name='them_bien_the'),

    # Sửa thông tin gói bánh đã có
    path('quan-ly/bien-the/sua/<str:ma_bien_the>/', views.sua_bien_the, name='sua_bien_the'),

    # Bật/tắt trạng thái kinh doanh của gói bánh
    path('quan-ly/bien-the/doi-trang-thai/<str:ma_bien_the>/', views.doi_trang_thai_bien_the,
         name='doi_trang_thai_bien_the'),

    # Xóa gói bánh
    path('quan-ly/bien-the/xoa/<str:ma_bien_the>/', views.xoa_bien_the, name='xoa_bien_the'),

    # USE CASE 4: Quản lý mã vạch EAN-13 (Wireframe M2-WF09)
    path('quan-ly/ma-vach/<str:ma_sp>/', views.quan_ly_ma_vach, name='quan_ly_ma_vach'),

    # USE CASE 5: Quản lý giá bán (Wireframe M2-WF10)
    path('quan-ly/gia/<str:ma_sp>/', views.quan_ly_gia, name='quan_ly_gia'),

    # USE CASE 6: Quản lý hình ảnh sản phẩm (Wireframe M2-WF11)
    path('quan-ly/hinh-anh/<str:ma_sp>/', views.quan_ly_hinh_anh, name='quan_ly_hinh_anh'),

    # USE CASE 9: Quản lý danh mục sản phẩm (M2-WF13)
    path('quan-ly/danh-muc/', views.quan_ly_danh_muc, name='quan_ly_danh_muc'),
    path('quan-ly/danh-muc/sua/<str:ma_dm>/', views.sua_danh_muc, name='sua_danh_muc'),
    path('quan-ly/danh-muc/doi-trang-thai/<str:ma_dm>/', views.doi_trang_thai_danh_muc, name='doi_trang_thai_danh_muc'),

]