# File: backend/products/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import SanPham, DanhMucSanPham, BienTheSanPham, HinhAnhSanPham
from .forms import SanPhamForm, BienTheForm
from django.db.models import Q

# ==============================================================================
# USE CASE 1 & USE CASE 8: XEM DANH SÁCH, TÌM KIẾM & LỌC SẢN PHẨM PHÍA KHÁCH HÀNG
# ==============================================================================

def danh_sach_san_pham(request):
    """
    Hiển thị danh sách sản phẩm cho Khách hàng:
    - Tìm kiếm theo tên sản phẩm, mã SP hoặc mã vạch 13 số (EAN-13).
    - Lọc theo danh mục, lọc theo hương vị, lọc theo quy cách đóng gói.
    - Khách hàng chỉ xem sản phẩm đang có trạng thái Đang kinh doanh (ACTIVE).
    """
    # 1. Nhận các tham số tìm kiếm và bộ lọc từ thanh địa chỉ (GET)
    tu_khoa = request.GET.get('q', '').strip()
    ma_dm_chon = request.GET.get('category', '').strip()
    huong_vi_chon = request.GET.get('flavor', '').strip()
    quy_cach_chon = request.GET.get('pack', '').strip()

    # 2. Khách hàng chỉ xem sản phẩm đang kinh doanh (ACTIVE)
    danh_sach_sp = SanPham.objects.filter(trang_thai='ACTIVE')

    # 3. Xử lý TÌM KIẾM (Use Case 8): tìm theo tên, mã SP hoặc mã vạch biến thể
    if tu_khoa:
        danh_sach_sp = danh_sach_sp.filter(
            Q(ten_sp__icontains=tu_khoa) |
            Q(ma_sp__icontains=tu_khoa) |
            Q(bienthesanpham__barcode__icontains=tu_khoa)
        ).distinct()

    # 4. Xử lý LỌC THEO DANH MỤC
    if ma_dm_chon:
        danh_sach_sp = danh_sach_sp.filter(danh_muc__ma_dm=ma_dm_chon)

    # 5. Xử lý LỌC THEO HƯƠNG VỊ (Truyền thống, Mè đen, Gừng, Lá dứa)
    if huong_vi_chon:
        danh_sach_sp = danh_sach_sp.filter(bienthesanpham__huong_vi=huong_vi_chon).distinct()

    # 6. Xử lý LỌC THEO QUY CÁCH (120g, 125g, 150g, 225g)
    if quy_cach_chon:
        danh_sach_sp = danh_sach_sp.filter(bienthesanpham__quy_cach=quy_cach_chon).distinct()

    # Sắp xếp sản phẩm mới nhất lên đầu
    danh_sach_sp = danh_sach_sp.order_by('-ngay_tao')

    # 7. Lấy danh sách các lựa chọn để hiển thị ra các ô chọn Dropdown
    danh_sach_dm = DanhMucSanPham.objects.filter(trang_thai='ACTIVE')
    danh_sach_huong_vi = ['Truyền thống', 'Mè đen', 'Gừng', 'Lá dứa']
    danh_sach_quy_cach = ['120g', '125g', '150g', '225g']

    # Kiểm tra xem người dùng có đang áp dụng bất kỳ bộ lọc nào không
    dang_loc = bool(tu_khoa or ma_dm_chon or huong_vi_chon or quy_cach_chon)

    # 8. Đóng gói dữ liệu gửi sang giao diện HTML
    du_lieu = {
        'danh_sach_sp': danh_sach_sp,
        'danh_sach_dm': danh_sach_dm,
        'danh_sach_huong_vi': danh_sach_huong_vi,
        'danh_sach_quy_cach': danh_sach_quy_cach,
        'tu_khoa': tu_khoa,
        'ma_dm_chon': ma_dm_chon,
        'huong_vi_chon': huong_vi_chon,
        'quy_cach_chon': quy_cach_chon,
        'dang_loc': dang_loc,
    }
    return render(request, 'products/danh_sach.html', du_lieu)


def chi_tiet_san_pham(request, ma_sp):
    """
    Xem chi tiết 1 sản phẩm: hiển thị các gói bánh (biến thể), hình ảnh và giá.
    """
    # 1. Tìm đúng sản phẩm đang bán
    san_pham = get_object_or_404(SanPham, ma_sp=ma_sp, trang_thai='ACTIVE')

    # 2. Lấy tất cả các biến thể đang bán của sản phẩm này
    danh_sach_bien_the = BienTheSanPham.objects.filter(san_pham=san_pham, trang_thai='ACTIVE')

    # 3. Lấy các hình ảnh của sản phẩm
    danh_sach_anh = HinhAnhSanPham.objects.filter(san_pham=san_pham)

    # 4. Kiểm tra loại khách hàng (Liên kết Module 1)
    # Mặc định là Khách lẻ, nếu đăng nhập là Khách sỉ thì sẽ được xem thêm giá sỉ
    loai_khach = request.session.get('loai_khach_hang', 'KHACH_LE')
    la_khach_si = (loai_khach == 'KHACH_SI')

    du_lieu = {
        'san_pham': san_pham,
        'danh_sach_bien_the': danh_sach_bien_the,
        'danh_sach_anh': danh_sach_anh,
        'la_khach_si': la_khach_si,
    }
    return render(request, 'products/chi_tiet.html', du_lieu)


# ==============================================================================
# PHẦN 2: DÀNH CHO NHÂN VIÊN / QUẢN LÝ (USE CASE 2 - M2-UC02)
# ==============================================================================

def quan_ly_san_pham(request):
    """
    Trang quản lý sản phẩm dành cho Nhân viên:
    - Tìm kiếm nhanh theo tên sản phẩm, mã SP, mã vạch.
    - Lọc theo trạng thái Đang bán / Ngừng bán.
    """
    tu_khoa = request.GET.get('q', '').strip()
    trang_thai_loc = request.GET.get('status', '').strip()

    danh_sach_sp = SanPham.objects.all()

    # Tìm kiếm theo từ khóa
    if tu_khoa:
        danh_sach_sp = danh_sach_sp.filter(
            Q(ten_sp__icontains=tu_khoa) |
            Q(ma_sp__icontains=tu_khoa) |
            Q(bienthesanpham__barcode__icontains=tu_khoa)
        ).distinct()

    # Lọc theo trạng thái
    if trang_thai_loc:
        danh_sach_sp = danh_sach_sp.filter(trang_thai=trang_thai_loc)

    danh_sach_sp = danh_sach_sp.order_by('-ngay_tao')

    du_lieu = {
        'danh_sach_sp': danh_sach_sp,
        'trang_thai_loc': trang_thai_loc,
        'tu_khoa': tu_khoa,
    }
    return render(request, 'products/quan_ly.html', du_lieu)

def them_san_pham(request):
    """
    Thêm sản phẩm mới vào hệ thống.
    """
    if request.method == 'POST':
        form = SanPhamForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Đã thêm sản phẩm mới thành công!')
            return redirect('products:quan_ly')
        else:
            messages.error(request, 'Dữ liệu không hợp lệ, vui lòng kiểm tra lại!')
    else:
        form = SanPhamForm()

    du_lieu = {
        'form': form,
        'tieu_de': 'Thêm sản phẩm mới',
    }
    return render(request, 'products/form_san_pham.html', du_lieu)


def sua_san_pham(request, ma_sp):
    """
    Chỉnh sửa thông tin sản phẩm.
    """
    san_pham = get_object_or_404(SanPham, ma_sp=ma_sp)

    if request.method == 'POST':
        form = SanPhamForm(request.POST, instance=san_pham)
        if form.is_valid():
            form.save()
            messages.success(request, f'Cập nhật sản phẩm "{san_pham.ten_sp}" thành công!')
            return redirect('products:quan_ly')
        else:
            messages.error(request, 'Có lỗi xảy ra khi sửa, vui lòng thử lại!')
    else:
        form = SanPhamForm(instance=san_pham)

    du_lieu = {
        'form': form,
        'tieu_de': f'Chỉnh sửa sản phẩm: {san_pham.ten_sp}',
        'san_pham': san_pham,
    }
    return render(request, 'products/form_san_pham.html', du_lieu)


def doi_trang_thai_san_pham(request, ma_sp):
    """
    Chuyển đổi trạng thái kinh doanh giữa 'ACTIVE' (Đang bán) và 'INACTIVE' (Ngừng bán).
    Không xóa dữ liệu để bảo toàn lịch sử đơn hàng và doanh thu.
    """
    san_pham = get_object_or_404(SanPham, ma_sp=ma_sp)

    if san_pham.trang_thai == 'ACTIVE':
        san_pham.trang_thai = 'INACTIVE'
        messages.warning(request, f'Đã chuyển sản phẩm "{san_pham.ten_sp}" sang trạng thái NGỪNG KINH DOANH (Tạm ẩn khỏi khách hàng).')
    else:
        san_pham.trang_thai = 'ACTIVE'
        messages.success(request, f'Đã kích hoạt mở bán lại cho sản phẩm "{san_pham.ten_sp}" thành công!')

    san_pham.save()
    return redirect('products:quan_ly')

def xoa_san_pham(request, ma_sp):
    """
    Xóa sản phẩm: Chỉ cho phép xóa khi chưa có biến thể nào gắn vào.
    """
    san_pham = get_object_or_404(SanPham, ma_sp=ma_sp)
    co_bien_the = BienTheSanPham.objects.filter(san_pham=san_pham).exists()

    if co_bien_the:
        messages.error(
            request,
            f'Không thể xóa sản phẩm "{san_pham.ten_sp}" vì đã có các biến thể bánh gắn vào! Hãy dùng nút "Ngừng bán" để bảo toàn dữ liệu.'
        )
    else:
        san_pham.delete()
        messages.success(request, f'Đã xóa sản phẩm "{san_pham.ten_sp}" thành công!')

    return redirect('products:quan_ly')


# ==============================================================================
# PHẦN 3: USE CASE 3 - QUẢN LÝ BIẾN THỂ SẢN PHẨM (M2-UC03)
# ==============================================================================

def danh_sach_bien_the(request, ma_sp):
    """
    1. Xem danh sách các gói bánh (biến thể) thuộc về 1 sản phẩm cha.
    """
    # Bước 1: Tìm đúng sản phẩm cha theo mã sản phẩm
    san_pham = get_object_or_404(SanPham, ma_sp=ma_sp)

    # Bước 2: Lấy tất cả các biến thể thuộc về sản phẩm này
    danh_sach_cac_goi = BienTheSanPham.objects.filter(san_pham=san_pham).order_by('-ngay_tao')

    # Bước 3: Đóng gói dữ liệu gửi sang file HTML
    du_lieu = {
        'san_pham': san_pham,
        'danh_sach_cac_goi': danh_sach_cac_goi,
    }
    return render(request, 'products/danh_sach_bien_the.html', du_lieu)


def them_bien_the(request, ma_sp):
    """
    2. Thêm gói bánh mới cho sản phẩm cha.
    Kiểm tra quy tắc M2-BR05 & Ngoại lệ E4: Không được trùng tổ hợp (Hương vị + Quy cách).
    """
    # Bước 1: Tìm sản phẩm cha
    san_pham = get_object_or_404(SanPham, ma_sp=ma_sp)

    if request.method == 'POST':
        # Bước 2: Khi người dùng bấm nút Lưu, nhận dữ liệu gửi lên
        form = BienTheForm(request.POST)

        if form.is_valid():
            huong_vi = form.cleaned_data.get('huong_vi')
            quy_cach = form.cleaned_data.get('quy_cach')

            # Bước 3: Kiểm tra xem tổ hợp này đã có trong sản phẩm cha chưa (M2-BR05)
            da_trung_to_hop = BienTheSanPham.objects.filter(
                san_pham=san_pham,
                huong_vi=huong_vi,
                quy_cach=quy_cach
            ).exists()

            if da_trung_to_hop:
                # Báo lỗi nếu đã có gói bánh vị này và khối lượng này
                messages.error(
                    request,
                    f'Sản phẩm này đã có biến thể "{huong_vi} - {quy_cach}" rồi! Vui lòng chọn vị hoặc quy cách khác.'
                )
            else:
                # Bước 4: Tạo đối tượng biến thể nhưng chưa ghi vào DB ngay
                bien_the_moi = form.save(commit=False)

                # Bước 5: Gán gói bánh này thuộc về sản phẩm cha
                bien_the_moi.san_pham = san_pham

                # Bước 6: Lưu chính thức vào Database
                bien_the_moi.save()
                messages.success(request, f'Đã thêm biến thể "{bien_the_moi.huong_vi} - {bien_the_moi.quy_cach}" thành công!')

                # Bước 7: Quay lại màn hình danh sách biến thể của sản phẩm
                return redirect('products:danh_sach_bien_the', ma_sp=san_pham.ma_sp)
        else:
            messages.error(request, 'Thông tin nhập chưa đúng hoặc mã vạch bị trùng, vui lòng kiểm tra lại!')
    else:
        # Khi mới vào trang thì mở form trống
        form = BienTheForm()

    du_lieu = {
        'form': form,
        'san_pham': san_pham,
        'tieu_de': f'Thêm biến thể mới cho: {san_pham.ten_sp}',
    }
    return render(request, 'products/form_bien_the.html', du_lieu)


def sua_bien_the(request, ma_bien_the):
    """
    3. Chỉnh sửa thông tin một gói bánh đã có.
    """
    # Bước 1: Tìm gói bánh cần sửa theo mã biến thể
    bien_the = get_object_or_404(BienTheSanPham, ma_bien_the=ma_bien_the)
    san_pham = bien_the.san_pham

    if request.method == 'POST':
        # Bước 2: Nhận dữ liệu cập nhật
        form = BienTheForm(request.POST, instance=bien_the)

        if form.is_valid():
            huong_vi = form.cleaned_data.get('huong_vi')
            quy_cach = form.cleaned_data.get('quy_cach')

            # Bước 3: Kiểm tra nếu sửa trùng với một biến thể KHÁC trong cùng sản phẩm
            da_trung_to_hop = BienTheSanPham.objects.filter(
                san_pham=san_pham,
                huong_vi=huong_vi,
                quy_cach=quy_cach
            ).exclude(ma_bien_the=ma_bien_the).exists()

            if da_trung_to_hop:
                messages.error(request, f'Tổ hợp vị "{huong_vi} - {quy_cach}" đã bị trùng với một gói bánh khác!')
            else:
                form.save()
                messages.success(request, f'Đã cập nhật biến thể "{bien_the.ma_bien_the}" thành công!')
                return redirect('products:danh_sach_bien_the', ma_sp=san_pham.ma_sp)
        else:
            messages.error(request, 'Thông tin chưa hợp lệ, vui lòng kiểm tra lại!')
    else:
        # Bước 4: Mở form có sẵn dữ liệu cũ của gói bánh
        form = BienTheForm(instance=bien_the)

    du_lieu = {
        'form': form,
        'san_pham': san_pham,
        'bien_the': bien_the,
        'tieu_de': f'Chỉnh sửa biến thể: {bien_the.ma_bien_the}',
    }
    return render(request, 'products/form_bien_the.html', du_lieu)


def doi_trang_thai_bien_the(request, ma_bien_the):
    """
    4. Bật / Tắt trạng thái kinh doanh của biến thể (M2-BR09, M2-BR13).
    """
    bien_the = get_object_or_404(BienTheSanPham, ma_bien_the=ma_bien_the)
    if bien_the.trang_thai == 'ACTIVE':
        bien_the.trang_thai = 'INACTIVE'
        messages.warning(request, f'Đã ngừng kinh doanh biến thể "{bien_the}".')
    else:
        bien_the.trang_thai = 'ACTIVE'
        messages.success(request, f'Đã mở kinh doanh lại biến thể "{bien_the}".')
    bien_the.save()
    return redirect('products:danh_sach_bien_the', ma_sp=bien_the.san_pham.ma_sp)


def xoa_bien_the(request, ma_bien_the):
    """
    5. Xóa gói bánh khỏi CSDL (Ngoại lệ E5 của M2-UC03).
    """
    bien_the = get_object_or_404(BienTheSanPham, ma_bien_the=ma_bien_the)
    ma_sp = bien_the.san_pham.ma_sp

    # Xóa biến thể
    bien_the.delete()
    messages.success(request, f'Đã xóa biến thể "{ma_bien_the}" thành công!')
    return redirect('products:danh_sach_bien_the', ma_sp=ma_sp)


from .forms import CapNhatMaVachForm


# ==============================================================================
# THUẬT TOÁN HỖ TRỢ: TÍNH SỐ KIỂM TRA CHO MÃ EAN-13 CHUẨN QUÝ THU
# ==============================================================================
def tao_ma_ean13_hop_le(ma_bien_the):
    """
    Hàm tự động sinh mã vạch 13 số bắt đầu bằng 893 (Mã quốc gia Việt Nam)
    + 6 số mã xưởng Quý Thu (850123) + 3 số thứ tự + 1 số kiểm tra chuẩn EAN-13.
    """
    # Lấy các chữ số từ mã biến thể hoặc dùng số mặc định
    so_thu_tu = "".join(filter(str.isdigit, ma_bien_the))
    if not so_thu_tu:
        so_thu_tu = "001"
    phan_12_so = f"8938501{int(so_thu_tu):05d}"[:12]

    # Tính số kiểm tra thứ 13 (Check digit)
    tong = 0
    for vi_tri, ky_tu in enumerate(phan_12_so):
        so = int(ky_tu)
        tong += so if (vi_tri % 2 == 0) else (so * 3)
    so_kiem_tra = (10 - (tong % 10)) % 10
    return phan_12_so + str(so_kiem_tra)


# ==============================================================================
# PHẦN 4: USE CASE 4 - QUẢN LÝ MÃ VẠCH (M2-UC04, WIREFRAME M2-WF09)
# ==============================================================================

def quan_ly_ma_vach(request, ma_sp):
    """
    Xem và cập nhật mã vạch EAN-13 cho từng biến thể của một sản phẩm.
    """
    # 1. Tìm sản phẩm cha theo mã
    san_pham = get_object_or_404(SanPham, ma_sp=ma_sp)

    # 2. Lấy tất cả các biến thể của sản phẩm này
    danh_sach_bien_the = BienTheSanPham.objects.filter(san_pham=san_pham).order_by('ma_bien_the')

    # 3. Khi nhân viên nhấn nút "Lưu mã vạch"
    if request.method == 'POST':
        thao_tac = request.POST.get('thao_tac')

        # Thao tác A: Nhân viên bấm "Tự động sinh mã EAN-13"
        if thao_tac == 'sinh_tu_dong':
            ma_bt = request.POST.get('ma_bien_the')
            bien_the = get_object_or_404(BienTheSanPham, ma_bien_the=ma_bt)

            # Sinh mã vạch chuẩn
            barcode_moi = tao_ma_ean13_hop_le(bien_the.ma_bien_the)

            # Kiểm tra xem mã sinh ra có trùng không
            if BienTheSanPham.objects.filter(barcode=barcode_moi).exclude(ma_bien_the=ma_bt).exists():
                messages.error(request, f"Mã sinh tự động {barcode_moi} đã bị trùng, vui lòng nhập thủ công!")
            else:
                bien_the.barcode = barcode_moi
                bien_the.save()
                messages.success(request,
                                 f"Đã sinh và gán mã vạch EAN-13 '{barcode_moi}' cho gói {bien_the.huong_vi} ({bien_the.quy_cach})!")
            return redirect('products:quan_ly_ma_vach', ma_sp=san_pham.ma_sp)

        # Thao tác B: Nhân viên tự gõ mã vạch vào và bấm "Cập nhật"
        else:
            form = CapNhatMaVachForm(request.POST)
            if form.is_valid():
                ma_bt = form.cleaned_data.get('ma_bien_the')
                barcode_moi = form.cleaned_data.get('barcode')

                # Tìm đúng biến thể và cập nhật mã vạch mới
                bien_the = get_object_or_404(BienTheSanPham, ma_bien_the=ma_bt)
                bien_the.barcode = barcode_moi
                bien_the.save()

                messages.success(
                    request,
                    f"Đã cập nhật mã vạch '{barcode_moi}' cho gói bánh {bien_the.huong_vi} ({bien_the.quy_cach}) thành công!"
                )
                return redirect('products:quan_ly_ma_vach', ma_sp=san_pham.ma_sp)
            else:
                # Nếu có lỗi (sai 13 số hoặc bị trùng mã) thì hiển thị câu thông báo lỗi
                for field, danh_sach_loi in form.errors.items():
                    for loi in danh_sach_loi:
                        messages.error(request, loi)

    # 4. Gửi dữ liệu sang giao diện M2-WF09
    du_lieu = {
        'san_pham': san_pham,
        'danh_sach_bien_the': danh_sach_bien_the,
    }
    return render(request, 'products/quan_ly_ma_vach.html', du_lieu)

from .forms import CapNhatGiaForm


# ==============================================================================
# PHẦN 5: USE CASE 5 - QUẢN LÝ GIÁ BÁN (M2-UC05, WIREFRAME M2-WF10)
# ==============================================================================

def quan_ly_gia(request, ma_sp):
    """
    Xem và cập nhật giá bán lẻ, giá bán sỉ và mức số lượng sỉ tối thiểu
    cho từng biến thể của một sản phẩm.
    """
    # Bước 1: Tìm sản phẩm cha theo mã
    san_pham = get_object_or_404(SanPham, ma_sp=ma_sp)

    # Bước 2: Lấy tất cả các biến thể của sản phẩm này
    danh_sach_bien_the = BienTheSanPham.objects.filter(san_pham=san_pham).order_by('ma_bien_the')

    # Bước 3: Khi nhân viên bấm nút "Cập nhật giá" (gửi POST)
    if request.method == 'POST':
        form = CapNhatGiaForm(request.POST)

        if form.is_valid():
            ma_bt = form.cleaned_data.get('ma_bien_the')
            gia_le_moi = form.cleaned_data.get('gia_ban_le')
            gia_si_moi = form.cleaned_data.get('gia_ban_si')
            sl_toi_thieu_moi = form.cleaned_data.get('so_luong_toi_thieu_si')

            # Tìm đúng biến thể cần cập nhật
            bien_the = get_object_or_404(BienTheSanPham, ma_bien_the=ma_bt)

            # Gán giá trị mới
            bien_the.gia_ban_le = gia_le_moi
            bien_the.gia_ban_si = gia_si_moi
            bien_the.so_luong_toi_thieu_si = sl_toi_thieu_moi
            bien_the.save()

            messages.success(
                request,
                f"Đã cập nhật bảng giá mới cho gói '{bien_the.huong_vi} - {bien_the.quy_cach}' thành công!"
            )
            return redirect('products:quan_ly_gia', ma_sp=san_pham.ma_sp)
        else:
            # Nếu vi phạm quy tắc M2-BR07 (nhập giá sỉ > giá lẻ) thì báo lỗi
            for field, danh_sach_loi in form.errors.items():
                for loi in danh_sach_loi:
                    messages.error(request, loi)

    # Bước 4: Đóng gói dữ liệu gửi sang giao diện HTML M2-WF10
    du_lieu = {
        'san_pham': san_pham,
        'danh_sach_bien_the': danh_sach_bien_the,
    }
    return render(request, 'products/quan_ly_gia.html', du_lieu)

from django.core.files.storage import FileSystemStorage


# ==============================================================================
# PHẦN 6: USE CASE 6 - QUẢN LÝ HÌNH ẢNH SẢN PHẨM (TẢI ẢNH TỪ MÁY TÍNH)
# ==============================================================================

def quan_ly_hinh_anh(request, ma_sp):
    """
    Xem bộ sưu tập ảnh, tải ảnh từ máy tính lên, đổi ảnh đại diện chính hoặc xóa ảnh.
    """
    # 1. Tìm sản phẩm cha
    san_pham = get_object_or_404(SanPham, ma_sp=ma_sp)

    # 2. Lấy danh sách ảnh hiện có của sản phẩm này
    danh_sach_anh = HinhAnhSanPham.objects.filter(san_pham=san_pham)

    # 3. Xử lý các thao tác khi bấm nút (POST)
    if request.method == 'POST':
        thao_tac = request.POST.get('thao_tac')

        # Thao tác A: Tải ảnh từ máy tính lên
        if thao_tac == 'them_anh':
            tep_anh = request.FILES.get('tep_anh')
            dat_lam_anh_chinh = (request.POST.get('anh_chinh') == 'on')

            if tep_anh:
                # 1. Kiểm tra dung lượng tối đa 5MB theo yêu cầu đề bài
                if tep_anh.size > 5 * 1024 * 1024:
                    messages.error(request, "Tệp ảnh quá lớn! Dung lượng tối đa cho phép là 5MB.")
                    return redirect('products:quan_ly_hinh_anh', ma_sp=san_pham.ma_sp)

                # 2. Kiểm tra định dạng đuôi file ảnh
                duoi_file = tep_anh.name.split('.')[-1].lower()
                if duoi_file not in ['jpg', 'jpeg', 'png', 'webp']:
                    messages.error(request, "Định dạng không hợp lệ! Hệ thống chỉ nhận ảnh JPG, PNG hoặc WEBP.")
                    return redirect('products:quan_ly_hinh_anh', ma_sp=san_pham.ma_sp)

                # 3. Lưu file vào thư mục media/products trên máy tính
                fs = FileSystemStorage()
                ten_file_da_luu = fs.save(f"products/{tep_anh.name}", tep_anh)
                duong_dan_anh = fs.url(ten_file_da_luu)

                # 4. Nếu chọn làm ảnh chính -> hủy ảnh chính của các ảnh cũ
                if dat_lam_anh_chinh:
                    HinhAnhSanPham.objects.filter(san_pham=san_pham).update(anh_chinh=False)

                # 5. Tự động sinh mã ảnh (HA001, HA002...)
                so_luong_anh = HinhAnhSanPham.objects.count() + 1
                ma_ha_moi = f"HA{so_luong_anh:03d}"

                # 6. Tạo bản ghi ảnh vào database
                HinhAnhSanPham.objects.create(
                    ma_hinh_anh=ma_ha_moi,
                    san_pham=san_pham,
                    duong_dan=duong_dan_anh,
                    anh_chinh=dat_lam_anh_chinh
                )
                messages.success(request, f"Đã tải lên ảnh '{tep_anh.name}' từ máy tính thành công!")
                return redirect('products:quan_ly_hinh_anh', ma_sp=san_pham.ma_sp)
            else:
                messages.error(request, "Vui lòng chọn một file ảnh từ máy tính của bạn!")

        # Thao tác B: Đặt một ảnh làm ảnh đại diện chính
        elif thao_tac == 'dat_lam_anh_chinh':
            ma_ha = request.POST.get('ma_hinh_anh')

            # Đặt tất cả ảnh về ảnh phụ
            HinhAnhSanPham.objects.filter(san_pham=san_pham).update(anh_chinh=False)

            # Đặt ảnh được chọn thành ảnh chính
            anh_duoc_chon = get_object_or_404(HinhAnhSanPham, ma_hinh_anh=ma_ha, san_pham=san_pham)
            anh_duoc_chon.anh_chinh = True
            anh_duoc_chon.save()

            messages.success(request, f"Đã đổi ảnh đại diện chính của sản phẩm!")
            return redirect('products:quan_ly_hinh_anh', ma_sp=san_pham.ma_sp)

        # Thao tác C: Xóa ảnh
        elif thao_tac == 'xoa_anh':
            ma_ha = request.POST.get('ma_hinh_anh')
            anh_can_xoa = get_object_or_404(HinhAnhSanPham, ma_hinh_anh=ma_ha, san_pham=san_pham)
            anh_can_xoa.delete()

            messages.success(request, "Đã xóa ảnh khỏi bộ sưu tập!")
            return redirect('products:quan_ly_hinh_anh', ma_sp=san_pham.ma_sp)

    du_lieu = {
        'san_pham': san_pham,
        'danh_sach_anh': danh_sach_anh,
    }
    return render(request, 'products/quan_ly_hinh_anh.html', du_lieu)

from .forms import DanhMucForm


# ==============================================================================
# PHẦN 7: USE CASE 9 - QUẢN LÝ DANH MỤC SẢN PHẨM (M2-UC09, WIREFRAME M2-WF13)
# ==============================================================================

def quan_ly_danh_muc(request):
    """
    Xem danh sách danh mục, số lượng sản phẩm của từng danh mục và thêm mới danh mục.
    """
    # 1. Lấy tất cả danh mục
    danh_sach_dm = DanhMucSanPham.objects.all().order_by('ma_dm')

    # 2. Xử lý khi người dùng gửi form thêm danh mục mới
    if request.method == 'POST':
        form = DanhMucForm(request.POST)
        if form.is_valid():
            danh_muc_moi = form.save()
            messages.success(request, f"Đã thêm mới danh mục '{danh_muc_moi.ten_dm}' thành công!")
            return redirect('products:quan_ly_danh_muc')
        else:
            for field, danh_sach_loi in form.errors.items():
                for loi in danh_sach_loi:
                    messages.error(request, loi)
    else:
        form = DanhMucForm()

    du_lieu = {
        'danh_sach_dm': danh_sach_dm,
        'form': form,
    }
    return render(request, 'products/quan_ly_danh_muc.html', du_lieu)


def sua_danh_muc(request, ma_dm):
    """
    Chỉnh sửa thông tin của một danh mục đã có.
    """
    danh_muc = get_object_or_404(DanhMucSanPham, ma_dm=ma_dm)

    if request.method == 'POST':
        form = DanhMucForm(request.POST, instance=danh_muc)
        if form.is_valid():
            form.save()
            messages.success(request, f"Đã cập nhật danh mục '{danh_muc.ten_dm}' thành công!")
            return redirect('products:quan_ly_danh_muc')
        else:
            messages.error(request, "Dữ liệu sửa không hợp lệ, vui lòng kiểm tra lại!")
    else:
        form = DanhMucForm(instance=danh_muc)

    du_lieu = {
        'form': form,
        'danh_muc': danh_muc,
    }
    return render(request, 'products/form_danh_muc.html', du_lieu)


def doi_trang_thai_danh_muc(request, ma_dm):
    """
    Bật / Tắt trạng thái hoạt động của danh mục.
    """
    danh_muc = get_object_or_404(DanhMucSanPham, ma_dm=ma_dm)

    if danh_muc.trang_thai == 'ACTIVE':
        danh_muc.trang_thai = 'INACTIVE'
        messages.warning(request, f"Đã ngừng áp dụng danh mục '{danh_muc.ten_dm}'.")
    else:
        danh_muc.trang_thai = 'ACTIVE'
        messages.success(request, f"Đã mở hoạt động lại danh mục '{danh_muc.ten_dm}'.")

    danh_muc.save()
    return redirect('products:quan_ly_danh_muc')