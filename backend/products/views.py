from django.shortcuts import render, get_object_or_404
from .models import SanPham, DanhMucSanPham, BienTheSanPham, HinhAnhSanPham


# ====================================================================
# CHỨC NĂNG 1: XEM DANH SÁCH SẢN PHẨM (M2-UC01)
# ====================================================================
def danh_sach_san_pham(request):
    # 1. Kiểm tra xem người dùng có bấm chọn lọc theo danh mục nào không
    ma_danh_muc_chon = request.GET.get('category')

    # 2. Lấy danh sách sản phẩm ĐANG BÁN (trang_thai = 'ACTIVE') theo quy tắc M2-BR11
    if ma_danh_muc_chon:
        # Nếu có chọn danh mục thì chỉ lấy sản phẩm của danh mục đó
        danh_sach_sp = SanPham.objects.filter(trang_thai='ACTIVE', danh_muc__ma_dm=ma_danh_muc_chon)
    else:
        # Nếu không chọn thì lấy tất cả sản phẩm đang bán
        danh_sach_sp = SanPham.objects.filter(trang_thai='ACTIVE')

    # 3. Lấy tất cả các danh mục đang hoạt động để làm menu bấm chọn
    danh_sach_dm = DanhMucSanPham.objects.filter(trang_thai='ACTIVE')

    # 4. Đóng gói dữ liệu để gửi sang file giao diện HTML
    du_lieu_gui_sang_giao_dien = {
        'danh_sach_sp': danh_sach_sp,
        'danh_sach_dm': danh_sach_dm,
        'ma_danh_muc_chon': ma_danh_muc_chon,
    }

    # 5. Mở file giao diện danh_sach.html và truyền dữ liệu vào
    return render(request, 'products/danh_sach.html', du_lieu_gui_sang_giao_dien)


# ====================================================================
# CHỨC NĂNG 2: XEM CHI TIẾT 1 SẢN PHẨM VÀ CÁC BIẾN THỂ (M2-UC01)
# ====================================================================
def chi_tiet_san_pham(request, ma_sp):
    # 1. Tìm đúng sản phẩm có mã này và phải đang bán (nếu không thấy sẽ báo lỗi 404 trang không tồn tại)
    san_pham = get_object_or_404(SanPham, ma_sp=ma_sp, trang_thai='ACTIVE')

    # 2. Tìm tất cả các biến thể (vị, khối lượng, giá) của sản phẩm này
    danh_sach_bien_the = BienTheSanPham.objects.filter(san_pham=san_pham, trang_thai='ACTIVE')

    # 3. Tìm các hình ảnh của sản phẩm này
    danh_sach_anh = HinhAnhSanPham.objects.filter(san_pham=san_pham)

    # 4. Đóng gói dữ liệu gửi sang giao diện chi tiết
    du_lieu_gui_sang_giao_dien = {
        'san_pham': san_pham,
        'danh_sach_bien_the': danh_sach_bien_the,
        'danh_sach_anh': danh_sach_anh,
    }

    # 5. Mở file chi_tiet.html
    return render(request, 'products/chi_tiet.html', du_lieu_gui_sang_giao_dien)