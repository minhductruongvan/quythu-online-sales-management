# File: backend/products/views.py
import os
import re
from urllib.parse import parse_qsl, quote, unquote, urlencode

from django.conf import settings
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from config.decorators import role_required
from customers.models import KhachHang, TaiKhoan

from .forms import (
    BienTheForm,
    CapNhatGiaForm,
    CapNhatMaVachForm,
    DanhMucForm,
    SanPhamForm,
)
from .image_assets import PRODUCT_IMAGE_ASSETS
from .models import (
    BienTheSanPham,
    DanhMucSanPham,
    HinhAnhSanPham,
    LichSuGiaBienThe,
    SanPham,
)
from .search import search_products_by_name, search_products_for_staff

MA_LOAI_KHACH_SI = "LKH002"
DUOI_ANH_HOP_LE = (".jpg", ".jpeg", ".png", ".webp")
DUNG_LUONG_ANH_TOI_DA = 5 * 1024 * 1024
ANH_DU_PHONG_MAC_DINH = "https://placehold.co/400x300?text=Banh+Dua+Quy+Thu"
TEN_TEP_CAM_WINDOWS = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _la_tep_anh_hop_le(tep_anh, duoi_file):
    """Kiểm tra chữ ký nhị phân (magic bytes) để chặn tệp giả mạo đuôi ảnh."""
    vi_tri_cu = tep_anh.tell() if hasattr(tep_anh, "tell") else 0
    try:
        tep_anh.seek(0)
        dau_tep = tep_anh.read(16)
    except Exception:
        return False
    finally:
        try:
            tep_anh.seek(vi_tri_cu)
        except Exception:
            pass

    if duoi_file in (".jpg", ".jpeg"):
        return dau_tep.startswith(b"\xff\xd8\xff")
    if duoi_file == ".png":
        return dau_tep.startswith(b"\x89PNG\r\n\x1a\n")
    if duoi_file == ".webp":
        return len(dau_tep) >= 12 and dau_tep[:4] == b"RIFF" and dau_tep[8:12] == b"WEBP"
    return False


def la_khach_si_da_xac_minh(user):
    """
    Kiểm tra tài khoản hiện tại có phải Khách sỉ đang hoạt động hay không.
    Dùng thống nhất giữa trang chủ, danh mục sản phẩm, chi tiết sản phẩm và M3.
    """
    if not user or not user.is_authenticated:
        return False
    if not user.is_active or user.trang_thai != TaiKhoan.TrangThai.ACTIVE:
        return False
    if user.vai_tro != TaiKhoan.VaiTro.CUSTOMER:
        return False
    if not hasattr(user, "khach_hang"):
        return False

    khach_hang = user.khach_hang
    if khach_hang.trang_thai != KhachHang.TrangThai.ACTIVE:
        return False

    return (
        khach_hang.loai_khach_hang_id == MA_LOAI_KHACH_SI
        or khach_hang.loai_khach_hang.ten_loai_kh == "Khách sỉ"
    )


def _ghi_lich_su_gia_bien_the(bien_the, nguoi_thuc_hien, gia_cu):
    gia_moi = (
        bien_the.gia_ban_le,
        bien_the.gia_ban_si,
        bien_the.so_luong_toi_thieu_si,
    )
    if gia_cu == gia_moi:
        return False

    LichSuGiaBienThe.objects.create(
        san_pham=bien_the.san_pham,
        bien_the=bien_the,
        ma_bien_the=bien_the.ma_bien_the,
        ten_bien_the=f"{bien_the.huong_vi} - {bien_the.quy_cach}",
        nguoi_thuc_hien=nguoi_thuc_hien,
        gia_ban_le_cu=gia_cu[0],
        gia_ban_le_moi=gia_moi[0],
        gia_ban_si_cu=gia_cu[1],
        gia_ban_si_moi=gia_moi[1],
        so_luong_toi_thieu_si_cu=gia_cu[2],
        so_luong_toi_thieu_si_moi=gia_moi[2],
    )
    return True


def _save_file_upload(uploaded_file, save_path):
    """Lưu tệp tải lên theo từng đoạn chunks() (Chương 6 - Quản lý tập tin)."""
    with open(save_path, "wb+") as output_file:
        for chunk in uploaded_file.chunks():
            output_file.write(chunk)


def _tao_ten_tep_anh_an_toan(ten_goc, thu_muc_dich):
    """Chuẩn hóa tên tệp, chặn tên dành riêng Windows, giới hạn độ dài an toàn và tự đổi tên nếu trùng."""
    ten_co_ban = os.path.basename(ten_goc or "anh.jpg")
    phan_ten, duoi_tep = os.path.splitext(ten_co_ban)
    phan_ten_sach = re.sub(r"[^A-Za-z0-9._-]+", "_", phan_ten).strip("._-")[:80] or "san_pham"
    if phan_ten_sach.split(".", 1)[0].upper() in TEN_TEP_CAM_WINDOWS:
        phan_ten_sach = f"san_pham_{phan_ten_sach}"
    duoi_sach = duoi_tep.lower()

    ten_tep = f"{phan_ten_sach}{duoi_sach}"
    chi_so = 1
    while os.path.exists(os.path.join(thu_muc_dich, ten_tep)):
        ten_tep = f"{phan_ten_sach}_{chi_so}{duoi_sach}"
        chi_so += 1
    return ten_tep


def _luu_tep_anh_len_dia(tep_anh):
    """Lưu tệp ảnh vào MEDIA_ROOT/products/ và trả về (duong_dan_url, duong_dan_dia)."""
    thu_muc_anh = os.path.join(settings.MEDIA_ROOT, "products")
    os.makedirs(thu_muc_anh, exist_ok=True)

    ten_tep = _tao_ten_tep_anh_an_toan(tep_anh.name, thu_muc_anh)
    duong_dan_dia = os.path.join(thu_muc_anh, ten_tep)
    _save_file_upload(tep_anh, duong_dan_dia)

    media_url = settings.MEDIA_URL
    if not media_url.endswith("/"):
        media_url += "/"
    duong_dan_url = f"{media_url}products/{quote(ten_tep)}"
    return duong_dan_url, duong_dan_dia


def _xoa_tep_anh_neu_khong_con_dung(duong_dan_url):
    """Xóa tệp ảnh vật lý trong MEDIA_ROOT nếu không còn bản ghi HinhAnhSanPham nào tham chiếu."""
    if not duong_dan_url:
        return
    media_url = settings.MEDIA_URL
    if not media_url.endswith("/"):
        media_url += "/"
    if not duong_dan_url.startswith(media_url):
        return
    if HinhAnhSanPham.objects.filter(duong_dan=duong_dan_url).exists():
        return

    duong_dan_tuong_doi = unquote(duong_dan_url[len(media_url):]).lstrip("/\\")
    if not duong_dan_tuong_doi:
        return

    goc_media = os.path.abspath(settings.MEDIA_ROOT)
    duong_dan_dia = os.path.abspath(os.path.join(goc_media, duong_dan_tuong_doi))
    if not duong_dan_dia.startswith(goc_media + os.sep):
        return
    if os.path.isfile(duong_dan_dia):
        try:
            os.remove(duong_dan_dia)
        except OSError:
            pass


def _redirect_quan_ly_voi_bo_loc(request):
    """Giữ lại tham số lọc hợp lệ (q, status, category) khi quay về trang quản lý sản phẩm."""
    raw_query = (request.POST.get("return_query") or "").strip()
    cac_tham_so_hop_le = [
        (k, v)
        for k, v in parse_qsl(raw_query, keep_blank_values=False)
        if k in ("q", "status", "category") and v.strip()
    ]
    url = reverse("products:quan_ly")
    if cac_tham_so_hop_le:
        return redirect(f"{url}?{urlencode(cac_tham_so_hop_le)}")
    return redirect("products:quan_ly")


def _sinh_ma_hinh_anh_moi():
    """Sinh mã hình ảnh mới dạng HA001, HA002... dựa trên mã lớn nhất hiện có."""
    so_lon_nhat = 0
    for anh in HinhAnhSanPham.objects.filter(ma_hinh_anh__startswith="HA"):
        phan_so = anh.ma_hinh_anh[2:]
        if phan_so.isdigit():
            so_hien_tai = int(phan_so)
            if so_hien_tai > so_lon_nhat:
                so_lon_nhat = so_hien_tai
    return f"HA{so_lon_nhat + 1:03d}"


def _gan_thong_tin_hien_thi_san_pham(
    danh_sach_sp,
    la_khach_si=False,
    huong_vi_da_chon=None,
    quy_cach_da_chon=None,
):
    """
    Gắn ảnh đại diện ưu tiên, giá thấp nhất (khớp bộ lọc biến thể nếu có) và trạng thái biến thể
    lên từng sản phẩm bằng các truy vấn ORM cơ bản (tránh N+1 query trong vòng lặp template).
    """
    ds_sp = list(danh_sach_sp)
    if not ds_sp:
        return ds_sp

    danh_sach_ma_sp = [sp.ma_sp for sp in ds_sp]

    # 1. Ảnh đại diện: ưu tiên ảnh anh_chinh=True, sau đó theo mã hình ảnh
    anh_theo_sp = {}
    for anh in HinhAnhSanPham.objects.filter(
        san_pham_id__in=danh_sach_ma_sp
    ).order_by("-anh_chinh", "ma_hinh_anh"):
        if anh.san_pham_id not in anh_theo_sp:
            anh_theo_sp[anh.san_pham_id] = anh.duong_dan

    # 2. Giá thấp nhất từ các biến thể ACTIVE (nếu đang lọc hương vị/quy cách thì tính theo các biến thể khớp)
    bien_the_qs = BienTheSanPham.objects.filter(
        san_pham_id__in=danh_sach_ma_sp,
        trang_thai="ACTIVE",
    )
    if huong_vi_da_chon:
        bien_the_qs = bien_the_qs.filter(huong_vi__in=huong_vi_da_chon)
    if quy_cach_da_chon:
        bien_the_qs = bien_the_qs.filter(quy_cach__in=quy_cach_da_chon)

    gia_theo_sp = {}
    cac_muc_gia_theo_sp = {}
    for bien_the in bien_the_qs:
        if la_khach_si and bien_the.gia_ban_si is not None:
            gia_ap_dung = bien_the.gia_ban_si
        else:
            gia_ap_dung = bien_the.gia_ban_le

        cac_muc_gia_theo_sp.setdefault(bien_the.san_pham_id, set()).add(gia_ap_dung)
        gia_hien_tai = gia_theo_sp.get(bien_the.san_pham_id)
        if gia_hien_tai is None or gia_ap_dung < gia_hien_tai:
            gia_theo_sp[bien_the.san_pham_id] = gia_ap_dung

    # 3. Đánh dấu sản phẩm đã có ít nhất 1 biến thể (dù ACTIVE hay INACTIVE) cho giao diện quản lý
    sp_co_bien_the = set(
        BienTheSanPham.objects.filter(san_pham_id__in=danh_sach_ma_sp)
        .values_list("san_pham_id", flat=True)
        .distinct()
    )

    for sp in ds_sp:
        anh_url = anh_theo_sp.get(sp.ma_sp)
        anh_mau = PRODUCT_IMAGE_ASSETS.get(sp.ma_sp)
        sp.catalog_image_url = anh_url
        sp.catalog_image_asset = anh_mau
        sp.catalog_fallback_image = ANH_DU_PHONG_MAC_DINH
        sp.admin_image_url = anh_url
        sp.admin_image_asset = anh_mau
        sp.gia_hien_thi = gia_theo_sp.get(sp.ma_sp)
        sp.nhieu_muc_gia = len(cac_muc_gia_theo_sp.get(sp.ma_sp, ())) > 1
        sp.co_bien_the = sp.ma_sp in sp_co_bien_the

    return ds_sp


# ==============================================================================
# USE CASE 1 & USE CASE 8: XEM DANH SÁCH, TÌM KIẾM & LỌC SẢN PHẨM PHÍA KHÁCH HÀNG
# ==============================================================================

def danh_sach_san_pham(request):
    """
    Hiển thị danh sách sản phẩm cho Khách hàng:
    - Tìm kiếm theo từ khóa có trong tên sản phẩm (hỗ trợ tiếng Việt không phân biệt hoa/thường).
    - Lọc theo danh mục, lọc theo hương vị, lọc theo quy cách đóng gói.
    - Khách hàng chỉ xem sản phẩm đang có trạng thái Đang kinh doanh (ACTIVE) thuộc danh mục ACTIVE.
    - Khách sỉ đã xác minh thấy giá bán sỉ thấp nhất ngay trên danh sách sản phẩm.
    """
    tu_khoa = request.GET.get('q', '').strip()
    ma_dm_da_chon = [value.strip() for value in request.GET.getlist('category') if value.strip()]
    huong_vi_da_chon = [value.strip() for value in request.GET.getlist('flavor') if value.strip()]
    quy_cach_da_chon = [value.strip() for value in request.GET.getlist('pack') if value.strip()]

    # Chỉ lấy sản phẩm đang bán (ACTIVE) thuộc danh mục đang hoạt động (ACTIVE)
    danh_sach_sp = SanPham.objects.select_related('danh_muc').filter(
        trang_thai='ACTIVE',
        danh_muc__trang_thai='ACTIVE',
    )

    if tu_khoa:
        danh_sach_sp = search_products_by_name(danh_sach_sp, tu_khoa)

    if ma_dm_da_chon:
        danh_sach_sp = danh_sach_sp.filter(danh_muc__ma_dm__in=ma_dm_da_chon)

    # Lọc hương vị và quy cách trên cùng một biến thể đang ACTIVE
    if huong_vi_da_chon or quy_cach_da_chon:
        bien_the_khop = BienTheSanPham.objects.filter(trang_thai='ACTIVE')
        if huong_vi_da_chon:
            bien_the_khop = bien_the_khop.filter(huong_vi__in=huong_vi_da_chon)
        if quy_cach_da_chon:
            bien_the_khop = bien_the_khop.filter(quy_cach__in=quy_cach_da_chon)
        ma_sp_co_bien_the = list(
            bien_the_khop.values_list('san_pham_id', flat=True).distinct()
        )
        danh_sach_sp = danh_sach_sp.filter(ma_sp__in=ma_sp_co_bien_the)

    la_khach_si = la_khach_si_da_xac_minh(request.user)
    danh_sach_sp = _gan_thong_tin_hien_thi_san_pham(
        danh_sach_sp.order_by('-ngay_tao', 'ma_sp'),
        la_khach_si=la_khach_si,
        huong_vi_da_chon=huong_vi_da_chon,
        quy_cach_da_chon=quy_cach_da_chon,
    )

    # Danh sách các lựa chọn bộ lọc chỉ lấy từ các biến thể đang bán (ACTIVE) thuộc
    # sản phẩm và danh mục đang hoạt động (ưu tiên thứ tự chuẩn), tránh rò rỉ dữ liệu đã ẩn/ngừng bán.
    danh_sach_dm = DanhMucSanPham.objects.filter(trang_thai='ACTIVE').order_by('ten_dm')
    bien_the_dang_ban = BienTheSanPham.objects.filter(
        trang_thai='ACTIVE',
        san_pham__trang_thai='ACTIVE',
        san_pham__danh_muc__trang_thai='ACTIVE',
    ).values_list('huong_vi', 'quy_cach')

    thu_tu_vi_chuan = ['Truyền thống', 'Mè đen', 'Gừng', 'Lá dứa']
    thu_tu_qc_chuan = ['120g', '125g', '150g', '225g']
    vi_dang_ban = set()
    qc_dang_ban = set()
    for huong_vi, quy_cach in bien_the_dang_ban:
        if huong_vi:
            vi_dang_ban.add(huong_vi)
        if quy_cach:
            qc_dang_ban.add(quy_cach)

    danh_sach_huong_vi = [v for v in thu_tu_vi_chuan if v in vi_dang_ban]
    for v in sorted(vi_dang_ban):
        if v not in danh_sach_huong_vi:
            danh_sach_huong_vi.append(v)

    danh_sach_quy_cach = [q for q in thu_tu_qc_chuan if q in qc_dang_ban]
    for q in sorted(qc_dang_ban):
        if q not in danh_sach_quy_cach:
            danh_sach_quy_cach.append(q)

    dang_loc = bool(
        tu_khoa or ma_dm_da_chon or huong_vi_da_chon or quy_cach_da_chon
    )

    du_lieu = {
        'danh_sach_sp': danh_sach_sp,
        'danh_sach_dm': danh_sach_dm,
        'danh_sach_huong_vi': danh_sach_huong_vi,
        'danh_sach_quy_cach': danh_sach_quy_cach,
        'tu_khoa': tu_khoa,
        'ma_dm_da_chon': ma_dm_da_chon,
        'huong_vi_da_chon': [v for v in huong_vi_da_chon if v in vi_dang_ban],
        'quy_cach_da_chon': [q for q in quy_cach_da_chon if q in qc_dang_ban],
        'dang_loc': dang_loc,
        'la_khach_si': la_khach_si,
    }
    return render(request, 'products/danh_sach.html', du_lieu)


def chi_tiet_san_pham(request, ma_sp):
    """
    Xem chi tiết 1 sản phẩm: hiển thị các gói bánh (biến thể), hình ảnh và giá.
    """
    san_pham = get_object_or_404(
        SanPham.objects.select_related('danh_muc'),
        ma_sp=ma_sp,
        trang_thai='ACTIVE',
        danh_muc__trang_thai='ACTIVE',
    )

    danh_sach_bien_the = BienTheSanPham.objects.filter(
        san_pham=san_pham,
        trang_thai='ACTIVE',
    ).order_by('ma_bien_the')
    danh_sach_anh = HinhAnhSanPham.objects.filter(
        san_pham=san_pham
    ).order_by('-anh_chinh', 'ma_hinh_anh')

    la_khach_si = la_khach_si_da_xac_minh(request.user)

    du_lieu = {
        'san_pham': san_pham,
        'danh_sach_bien_the': danh_sach_bien_the,
        'danh_sach_anh': danh_sach_anh,
        'anh_dai_dien_du_phong': PRODUCT_IMAGE_ASSETS.get(san_pham.ma_sp),
        'la_khach_si': la_khach_si,
    }
    return render(request, 'products/chi_tiet.html', du_lieu)


# ==============================================================================
# PHẦN 2: DÀNH CHO NHÂN VIÊN / QUẢN LÝ (USE CASE 2 - M2-UC02)
# ==============================================================================

@role_required(TaiKhoan.VaiTro.EMPLOYEE, TaiKhoan.VaiTro.MANAGER)
def quan_ly_san_pham(request):
    """
    Trang quản lý sản phẩm dành cho Nhân viên / Quản lý:
    - Tìm kiếm nhanh theo tên sản phẩm, mã SP, mã vạch (hỗ trợ tiếng Việt có dấu).
    - Lọc theo trạng thái Đang bán / Ngừng bán và danh mục.
    """
    tu_khoa = request.GET.get('q', '').strip()
    trang_thai_loc = request.GET.get('status', '').strip()
    ma_dm_loc = request.GET.get('category', '').strip()

    danh_sach_sp = SanPham.objects.select_related('danh_muc')

    if trang_thai_loc == 'ACTIVE':
        danh_sach_sp = danh_sach_sp.filter(
            trang_thai='ACTIVE',
            danh_muc__trang_thai='ACTIVE',
        )
    elif trang_thai_loc == 'HIDDEN':
        danh_sach_sp = danh_sach_sp.filter(
            trang_thai='ACTIVE',
        ).exclude(danh_muc__trang_thai='ACTIVE')
    elif trang_thai_loc == 'INACTIVE':
        danh_sach_sp = danh_sach_sp.filter(trang_thai='INACTIVE')
    else:
        trang_thai_loc = ''

    if ma_dm_loc:
        danh_sach_sp = danh_sach_sp.filter(danh_muc__ma_dm=ma_dm_loc)

    if tu_khoa:
        danh_sach_sp = search_products_for_staff(danh_sach_sp, tu_khoa)

    danh_sach_sp = _gan_thong_tin_hien_thi_san_pham(
        danh_sach_sp.order_by('-ngay_tao', 'ma_sp'),
        la_khach_si=False,
    )

    du_lieu = {
        'danh_sach_sp': danh_sach_sp,
        'trang_thai_loc': trang_thai_loc,
        'ma_dm_loc': ma_dm_loc,
        'danh_sach_dm': DanhMucSanPham.objects.all().order_by('ten_dm'),
        'tu_khoa': tu_khoa,
        'dang_loc': bool(tu_khoa or trang_thai_loc or ma_dm_loc),
        'return_query': request.GET.urlencode(),
    }
    return render(request, 'products/quan_ly.html', du_lieu)


@role_required(TaiKhoan.VaiTro.EMPLOYEE, TaiKhoan.VaiTro.MANAGER)
def chi_tiet_quan_ly_san_pham(request, ma_sp):
    san_pham = get_object_or_404(SanPham.objects.select_related('danh_muc'), ma_sp=ma_sp)
    danh_sach_anh = HinhAnhSanPham.objects.filter(
        san_pham=san_pham
    ).order_by('-anh_chinh', 'ma_hinh_anh')
    danh_sach_bien_the = BienTheSanPham.objects.select_related('don_vi_tinh').filter(
        san_pham=san_pham
    ).order_by('ma_bien_the')
    return render(request, "products/chi_tiet_quan_ly.html", {
        "san_pham": san_pham,
        "danh_sach_anh": danh_sach_anh,
        "anh_dai_dien_du_phong": PRODUCT_IMAGE_ASSETS.get(san_pham.ma_sp),
        "danh_sach_bien_the": danh_sach_bien_the,
    })


@role_required(TaiKhoan.VaiTro.EMPLOYEE, TaiKhoan.VaiTro.MANAGER)
def them_san_pham(request):
    """
    Thêm sản phẩm mới vào hệ thống.
    """
    if request.method == 'POST':
        form = SanPhamForm(request.POST)
        if form.is_valid():
            try:
                form.save()
            except IntegrityError:
                messages.error(request, 'Mã sản phẩm đã tồn tại, vui lòng chọn mã khác!')
            else:
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


@role_required(TaiKhoan.VaiTro.EMPLOYEE, TaiKhoan.VaiTro.MANAGER)
def sua_san_pham(request, ma_sp):
    """
    Chỉnh sửa thông tin sản phẩm.
    """
    san_pham = get_object_or_404(SanPham.objects.select_related('danh_muc'), ma_sp=ma_sp)
    ten_sp_goc = san_pham.ten_sp

    if request.method == 'POST':
        form = SanPhamForm(request.POST, instance=san_pham)
        if form.is_valid():
            san_pham_da_luu = form.save()
            if san_pham_da_luu.trang_thai == 'ACTIVE' and san_pham_da_luu.danh_muc.trang_thai != 'ACTIVE':
                messages.warning(
                    request,
                    f'Đã cập nhật sản phẩm "{san_pham_da_luu.ten_sp}", nhưng danh mục "{san_pham_da_luu.danh_muc.ten_dm}" đang ngừng áp dụng nên sản phẩm vẫn tạm ẩn khỏi cửa hàng.'
                )
            else:
                messages.success(request, f'Cập nhật sản phẩm "{san_pham_da_luu.ten_sp}" thành công!')
            return redirect('products:quan_ly')
        else:
            messages.error(request, 'Có lỗi xảy ra khi sửa, vui lòng thử lại!')
    else:
        form = SanPhamForm(instance=san_pham)

    du_lieu = {
        'form': form,
        'tieu_de': f'Chỉnh sửa sản phẩm: {ten_sp_goc}',
        'san_pham': san_pham,
        'danh_sach_bien_the': BienTheSanPham.objects.select_related('don_vi_tinh').filter(
            san_pham=san_pham
        ).order_by('ma_bien_the'),
    }
    return render(request, 'products/form_san_pham.html', du_lieu)


@role_required(TaiKhoan.VaiTro.EMPLOYEE, TaiKhoan.VaiTro.MANAGER)
@require_POST
def doi_trang_thai_san_pham(request, ma_sp):
    """
    Chuyển đổi trạng thái kinh doanh giữa 'ACTIVE' (Đang bán) và 'INACTIVE' (Ngừng bán).
    Không xóa dữ liệu để bảo toàn lịch sử đơn hàng và doanh thu.
    """
    san_pham = get_object_or_404(SanPham.objects.select_related('danh_muc'), ma_sp=ma_sp)

    if san_pham.trang_thai == 'ACTIVE':
        san_pham.trang_thai = 'INACTIVE'
        messages.warning(
            request,
            f'Đã chuyển sản phẩm "{san_pham.ten_sp}" sang trạng thái NGỪNG KINH DOANH (Tạm ẩn khỏi khách hàng).'
        )
    else:
        san_pham.trang_thai = 'ACTIVE'
        if san_pham.danh_muc.trang_thai != 'ACTIVE':
            messages.warning(
                request,
                f'Đã bật trạng thái kinh doanh cho sản phẩm "{san_pham.ten_sp}", nhưng danh mục "{san_pham.danh_muc.ten_dm}" đang ngừng áp dụng nên sản phẩm vẫn tạm ẩn khỏi cửa hàng.'
            )
        else:
            messages.success(request, f'Đã kích hoạt mở bán lại cho sản phẩm "{san_pham.ten_sp}" thành công!')

    san_pham.save(update_fields=['trang_thai'])
    return _redirect_quan_ly_voi_bo_loc(request)


@role_required(TaiKhoan.VaiTro.EMPLOYEE, TaiKhoan.VaiTro.MANAGER)
@require_POST
def xoa_san_pham(request, ma_sp):
    """
    Xóa sản phẩm cùng các biến thể chưa phát sinh đơn hàng/hậu mãi.
    Nếu có biến thể đã liên kết đơn hàng hoặc dữ liệu hậu mãi, transaction sẽ rollback
    toàn bộ để bảo toàn lịch sử (M2-BR13) và hướng dẫn dùng "Ngừng kinh doanh".
    Đồng thời dọn tệp ảnh vật lý của sản phẩm khỏi MEDIA_ROOT sau khi xóa thành công.
    """
    san_pham = get_object_or_404(SanPham, ma_sp=ma_sp)
    ten_sp = san_pham.ten_sp
    cac_duong_dan_anh = []
    so_bien_the = 0

    try:
        with transaction.atomic():
            cac_duong_dan_anh = list(
                HinhAnhSanPham.objects.filter(san_pham=san_pham).values_list("duong_dan", flat=True)
            )
            bien_the_qs = BienTheSanPham.objects.filter(san_pham=san_pham)
            so_bien_the = bien_the_qs.count()
            if so_bien_the:
                bien_the_qs.delete()
            san_pham.delete()
    except ProtectedError:
        messages.error(
            request,
            f'Không thể xóa sản phẩm "{ten_sp}" vì có biến thể đã phát sinh đơn hàng hoặc dữ liệu hậu mãi! '
            f'Hãy dùng nút "Ngừng kinh doanh" để bảo toàn dữ liệu.'
        )
    else:
        for duong_dan in cac_duong_dan_anh:
            _xoa_tep_anh_neu_khong_con_dung(duong_dan)
        if so_bien_the:
            messages.success(
                request,
                f'Đã xóa sản phẩm "{ten_sp}" cùng {so_bien_the} biến thể thành công!'
            )
        else:
            messages.success(request, f'Đã xóa sản phẩm "{ten_sp}" thành công!')

    return _redirect_quan_ly_voi_bo_loc(request)


# ==============================================================================
# PHẦN 3: USE CASE 3 - QUẢN LÝ BIẾN THỂ SẢN PHẨM (M2-UC03)
# ==============================================================================

@role_required(TaiKhoan.VaiTro.EMPLOYEE, TaiKhoan.VaiTro.MANAGER)
def danh_sach_bien_the(request, ma_sp):
    """
    1. Xem danh sách các gói bánh (biến thể) thuộc về 1 sản phẩm cha.
    """
    san_pham = get_object_or_404(SanPham.objects.select_related('danh_muc'), ma_sp=ma_sp)
    danh_sach_cac_goi = BienTheSanPham.objects.select_related('don_vi_tinh').filter(
        san_pham=san_pham
    ).order_by('ma_bien_the')

    du_lieu = {
        'san_pham': san_pham,
        'danh_sach_cac_goi': danh_sach_cac_goi,
    }
    return render(request, 'products/danh_sach_bien_the.html', du_lieu)


@role_required(TaiKhoan.VaiTro.EMPLOYEE, TaiKhoan.VaiTro.MANAGER)
def them_bien_the(request, ma_sp):
    """
    2. Thêm gói bánh mới cho sản phẩm cha.
    Kiểm tra quy tắc M2-BR05 & Ngoại lệ E4: Không được trùng tổ hợp (Hương vị + Quy cách).
    """
    san_pham = get_object_or_404(SanPham, ma_sp=ma_sp)

    if request.method == 'POST':
        form = BienTheForm(request.POST, san_pham=san_pham)

        if form.is_valid():
            bien_the_moi = form.save(commit=False)
            bien_the_moi.san_pham = san_pham
            try:
                bien_the_moi.save()
            except IntegrityError:
                messages.error(
                    request,
                    'Không thể lưu biến thể do trùng mã biến thể, mã vạch hoặc tổ hợp hương vị - quy cách!'
                )
            else:
                messages.success(
                    request,
                    f'Đã thêm biến thể "{bien_the_moi.huong_vi} - {bien_the_moi.quy_cach}" thành công!'
                )
                return redirect('products:danh_sach_bien_the', ma_sp=san_pham.ma_sp)
        else:
            messages.error(request, 'Thông tin nhập chưa hợp lệ, vui lòng kiểm tra lại các trường báo lỗi bên dưới!')
    else:
        form = BienTheForm(san_pham=san_pham)

    du_lieu = {
        'form': form,
        'san_pham': san_pham,
        'tieu_de': f'Thêm biến thể mới cho: {san_pham.ten_sp}',
    }
    return render(request, 'products/form_bien_the.html', du_lieu)


@role_required(TaiKhoan.VaiTro.EMPLOYEE, TaiKhoan.VaiTro.MANAGER)
def sua_bien_the(request, ma_bien_the):
    """
    3. Chỉnh sửa thông tin một gói bánh đã có và tự động lưu lịch sử giá nếu giá thay đổi.
    """
    bien_the = get_object_or_404(
        BienTheSanPham.objects.select_related('san_pham'),
        ma_bien_the=ma_bien_the,
    )
    san_pham = bien_the.san_pham

    if request.method == 'POST':
        form = None
        try:
            with transaction.atomic():
                bien_the_khoa = get_object_or_404(
                    BienTheSanPham.objects.select_for_update().select_related('san_pham'),
                    ma_bien_the=ma_bien_the,
                )
                san_pham = bien_the_khoa.san_pham
                gia_cu = (
                    bien_the_khoa.gia_ban_le,
                    bien_the_khoa.gia_ban_si,
                    bien_the_khoa.so_luong_toi_thieu_si,
                )
                form = BienTheForm(request.POST, instance=bien_the_khoa, san_pham=san_pham)

                if form.is_valid():
                    bien_the = form.save()
                    gia_thay_doi = _ghi_lich_su_gia_bien_the(
                        bien_the, request.user, gia_cu
                    )
                    if gia_thay_doi:
                        messages.success(
                            request,
                            f'Đã cập nhật biến thể "{bien_the.ma_bien_the}" và lưu lịch sử giá.',
                        )
                    else:
                        messages.success(
                            request,
                            f'Đã cập nhật biến thể "{bien_the.ma_bien_the}" thành công!',
                        )
                    return redirect('products:danh_sach_bien_the', ma_sp=san_pham.ma_sp)
                else:
                    bien_the = bien_the_khoa
                    messages.error(request, 'Thông tin chưa hợp lệ, vui lòng kiểm tra lại các trường báo lỗi bên dưới!')
        except IntegrityError:
            if form is None:
                form = BienTheForm(request.POST, instance=bien_the, san_pham=san_pham)
            messages.error(
                request,
                'Không thể cập nhật biến thể do trùng mã vạch hoặc tổ hợp hương vị - quy cách!'
            )
    else:
        form = BienTheForm(instance=bien_the, san_pham=san_pham)

    du_lieu = {
        'form': form,
        'san_pham': san_pham,
        'bien_the': bien_the,
        'tieu_de': f'Chỉnh sửa biến thể: {bien_the.ma_bien_the}',
    }
    return render(request, 'products/form_bien_the.html', du_lieu)


@role_required(TaiKhoan.VaiTro.EMPLOYEE, TaiKhoan.VaiTro.MANAGER)
@require_POST
def doi_trang_thai_bien_the(request, ma_bien_the):
    """
    4. Bật / Tắt trạng thái kinh doanh của biến thể (M2-BR09, M2-BR13).
    """
    bien_the = get_object_or_404(
        BienTheSanPham.objects.select_related('san_pham__danh_muc'),
        ma_bien_the=ma_bien_the,
    )
    if bien_the.trang_thai == 'ACTIVE':
        bien_the.trang_thai = 'INACTIVE'
        messages.warning(request, f'Đã ngừng kinh doanh biến thể "{bien_the}".')
    else:
        bien_the.trang_thai = 'ACTIVE'
        if bien_the.san_pham.danh_muc.trang_thai != 'ACTIVE':
            messages.warning(
                request,
                f'Đã mở trạng thái biến thể "{bien_the}", nhưng danh mục "{bien_the.san_pham.danh_muc.ten_dm}" đang ngừng áp dụng nên biến thể vẫn tạm ẩn khỏi cửa hàng.'
            )
        elif bien_the.san_pham.trang_thai != 'ACTIVE':
            messages.warning(
                request,
                f'Đã mở trạng thái biến thể "{bien_the}", nhưng sản phẩm "{bien_the.san_pham.ten_sp}" đang ngừng kinh doanh nên biến thể vẫn tạm ẩn khỏi cửa hàng.'
            )
        else:
            messages.success(request, f'Đã mở kinh doanh lại biến thể "{bien_the}".')
    bien_the.save(update_fields=['trang_thai'])
    return redirect('products:danh_sach_bien_the', ma_sp=bien_the.san_pham.ma_sp)


@role_required(TaiKhoan.VaiTro.EMPLOYEE, TaiKhoan.VaiTro.MANAGER)
@require_POST
def xoa_bien_the(request, ma_bien_the):
    """
    5. Xóa gói bánh khỏi CSDL (Ngoại lệ E5 của M2-UC03).
    Nếu gói bánh đã từng có trong đơn hàng hoặc hậu mãi thì không cho xóa để tránh mất dữ liệu lịch sử.
    """
    bien_the = get_object_or_404(BienTheSanPham, ma_bien_the=ma_bien_the)
    ma_sp = bien_the.san_pham.ma_sp

    try:
        bien_the.delete()
        messages.success(request, f'Đã xóa biến thể "{ma_bien_the}" thành công!')
    except ProtectedError:
        messages.error(
            request,
            f'Không thể xóa biến thể "{ma_bien_the}" vì đã phát sinh đơn hàng hoặc lịch sử liên quan! '
            f'Hãy dùng nút "Ngừng kinh doanh" để bảo toàn dữ liệu.'
        )

    return redirect('products:danh_sach_bien_the', ma_sp=ma_sp)


# ==============================================================================
# THUẬT TOÁN HỖ TRỢ: TÍNH SỐ KIỂM TRA CHO MÃ EAN-13 CHUẨN QUÝ THU
# ==============================================================================
def tao_ma_ean13_hop_le(ma_bien_the, barcode_hien_tai=None):
    """
    Tự động sinh mã vạch 13 số bắt đầu bằng 893 (Mã quốc gia Việt Nam) + 1 số kiểm tra chuẩn EAN-13.
    Luôn chọn một mã mới chưa tồn tại trên bất kỳ biến thể nào; nếu biến thể đang mang mã chuẩn
    8938501XXXXX* thì tịnh tiến tiếp theo dãy thay vì đảo qua lại giữa 2 mã.
    """
    if barcode_hien_tai and re.match(r"^8938501[0-9]{6}$", barcode_hien_tai):
        so_thu_tu = (int(barcode_hien_tai[7:12]) + 1) % 100000
    else:
        chuoi_so = "".join(filter(str.isdigit, ma_bien_the))
        so_thu_tu = int(chuoi_so) % 100000 if chuoi_so else 1

    ma_da_dung = set(
        BienTheSanPham.objects.filter(barcode__startswith="8938501").values_list(
            "barcode", flat=True
        )
    )

    for _ in range(100000):
        phan_12_so = f"8938501{so_thu_tu:05d}"

        # Tính số kiểm tra thứ 13 (Check digit) theo công thức chuẩn EAN-13
        tong = 0
        for vi_tri, ky_tu in enumerate(phan_12_so):
            so = int(ky_tu)
            tong += so if (vi_tri % 2 == 0) else (so * 3)
        so_kiem_tra = (10 - (tong % 10)) % 10
        ma_vach = phan_12_so + str(so_kiem_tra)

        # Kiểm tra mã chưa được sử dụng bởi bất kỳ biến thể nào
        if ma_vach not in ma_da_dung:
            return ma_vach

        so_thu_tu = (so_thu_tu + 1) % 100000

    return None


# ==============================================================================
# PHẦN 4: USE CASE 4 - QUẢN LÝ MÃ VẠCH (M2-UC04, WIREFRAME M2-WF08)
# ==============================================================================

@role_required(TaiKhoan.VaiTro.EMPLOYEE, TaiKhoan.VaiTro.MANAGER)
def quan_ly_ma_vach(request, ma_sp):
    """
    Xem và cập nhật mã vạch EAN-13 cho từng biến thể của một sản phẩm.
    """
    san_pham = get_object_or_404(SanPham, ma_sp=ma_sp)
    danh_sach_bien_the = BienTheSanPham.objects.filter(san_pham=san_pham).order_by('ma_bien_the')

    loi_ma_bt = None
    barcode_da_nhap = ''

    if request.method == 'POST':
        thao_tac = request.POST.get('thao_tac')

        # Thao tác A: Nhân viên bấm "Tự động sinh mã EAN-13"
        if thao_tac == 'sinh_tu_dong':
            ma_bt = request.POST.get('ma_bien_the')
            bien_the = get_object_or_404(BienTheSanPham, ma_bien_the=ma_bt, san_pham=san_pham)

            barcode_moi = tao_ma_ean13_hop_le(
                bien_the.ma_bien_the,
                barcode_hien_tai=bien_the.barcode,
            )

            if not barcode_moi:
                messages.error(request, "Không thể tự động sinh mã vạch mới, vui lòng nhập thủ công!")
            else:
                try:
                    bien_the.barcode = barcode_moi
                    bien_the.save(update_fields=['barcode'])
                except IntegrityError:
                    messages.error(request, "Mã vạch vừa sinh bị trùng do thao tác đồng thời, vui lòng thử lại!")
                else:
                    messages.success(
                        request,
                        f"Đã sinh và gán mã vạch EAN-13 mới '{barcode_moi}' cho gói {bien_the.huong_vi} ({bien_the.quy_cach})!"
                    )
            return redirect('products:quan_ly_ma_vach', ma_sp=san_pham.ma_sp)

        # Thao tác B: Nhân viên tự gõ mã vạch vào và bấm "Lưu mã vạch"
        else:
            form = CapNhatMaVachForm(request.POST)
            if form.is_valid():
                ma_bt = form.cleaned_data.get('ma_bien_the')
                barcode_moi = form.cleaned_data.get('barcode')

                bien_the = get_object_or_404(BienTheSanPham, ma_bien_the=ma_bt, san_pham=san_pham)
                try:
                    bien_the.barcode = barcode_moi
                    bien_the.save(update_fields=['barcode'])
                except IntegrityError:
                    messages.error(
                        request,
                        f"[{bien_the.ma_bien_the}] Mã vạch '{barcode_moi}' đã được sử dụng cho một biến thể khác!"
                    )
                    loi_ma_bt = ma_bt
                    barcode_da_nhap = barcode_moi
                else:
                    messages.success(
                        request,
                        f"Đã cập nhật mã vạch '{barcode_moi}' cho gói bánh {bien_the.huong_vi} ({bien_the.quy_cach}) thành công!"
                    )
                    return redirect('products:quan_ly_ma_vach', ma_sp=san_pham.ma_sp)
            else:
                loi_ma_bt = request.POST.get('ma_bien_the', '').strip()
                barcode_da_nhap = request.POST.get('barcode', '').strip()
                tien_to = f"[{loi_ma_bt}] " if loi_ma_bt else ""
                for field, danh_sach_loi in form.errors.items():
                    nhan = form.fields[field].label if field in form.fields else ""
                    for loi in danh_sach_loi:
                        if nhan:
                            messages.error(request, f"{tien_to}{nhan}: {loi}")
                        else:
                            messages.error(request, f"{tien_to}{loi}")

    du_lieu = {
        'san_pham': san_pham,
        'danh_sach_bien_the': danh_sach_bien_the,
        'loi_ma_bt': loi_ma_bt,
        'barcode_da_nhap': barcode_da_nhap,
    }
    return render(request, 'products/quan_ly_ma_vach.html', du_lieu)


# ==============================================================================
# PHẦN 5: USE CASE 5 - QUẢN LÝ GIÁ BÁN (M2-UC05, WIREFRAME M2-WF09)
# ==============================================================================

@role_required(TaiKhoan.VaiTro.EMPLOYEE, TaiKhoan.VaiTro.MANAGER)
def quan_ly_gia(request, ma_sp):
    """
    Xem và cập nhật giá bán lẻ, giá bán sỉ và mức số lượng sỉ tham khảo
    cho từng biến thể của một sản phẩm.
    """
    san_pham = get_object_or_404(SanPham, ma_sp=ma_sp)
    danh_sach_bien_the = BienTheSanPham.objects.filter(san_pham=san_pham).order_by('ma_bien_the')

    loi_ma_bt = None
    gia_da_nhap = {}

    if request.method == 'POST':
        form = CapNhatGiaForm(request.POST)

        if form.is_valid():
            ma_bt = form.cleaned_data.get('ma_bien_the')
            gia_le_moi = form.cleaned_data.get('gia_ban_le')
            gia_si_moi = form.cleaned_data.get('gia_ban_si')
            sl_toi_thieu_moi = form.cleaned_data.get('so_luong_toi_thieu_si')

            with transaction.atomic():
                bien_the = get_object_or_404(
                    BienTheSanPham.objects.select_for_update(),
                    ma_bien_the=ma_bt,
                    san_pham=san_pham,
                )
                gia_cu = (
                    bien_the.gia_ban_le,
                    bien_the.gia_ban_si,
                    bien_the.so_luong_toi_thieu_si,
                )
                gia_moi = (gia_le_moi, gia_si_moi, sl_toi_thieu_moi)
                gia_thay_doi = gia_cu != gia_moi

                if gia_thay_doi:
                    bien_the.gia_ban_le = gia_le_moi
                    bien_the.gia_ban_si = gia_si_moi
                    bien_the.so_luong_toi_thieu_si = sl_toi_thieu_moi
                    bien_the.save(
                        update_fields=(
                            "gia_ban_le",
                            "gia_ban_si",
                            "so_luong_toi_thieu_si",
                        )
                    )
                    _ghi_lich_su_gia_bien_the(bien_the, request.user, gia_cu)

            if gia_thay_doi:
                messages.success(
                    request,
                    f"Đã cập nhật bảng giá và lưu lịch sử cho gói "
                    f"'{bien_the.huong_vi} - {bien_the.quy_cach}' thành công!",
                )
            else:
                messages.info(request, "Bảng giá không thay đổi; không tạo bản ghi lịch sử.")
            return redirect('products:quan_ly_gia', ma_sp=san_pham.ma_sp)
        else:
            loi_ma_bt = request.POST.get('ma_bien_the', '').strip()
            gia_da_nhap = {
                'gia_ban_le': request.POST.get('gia_ban_le', ''),
                'gia_ban_si': request.POST.get('gia_ban_si', ''),
                'so_luong_toi_thieu_si': request.POST.get('so_luong_toi_thieu_si', ''),
            }
            tien_to = f"[{loi_ma_bt}] " if loi_ma_bt else ""
            for field, danh_sach_loi in form.errors.items():
                nhan = form.fields[field].label if field in form.fields else ""
                for loi in danh_sach_loi:
                    if nhan:
                        messages.error(request, f"{tien_to}{nhan}: {loi}")
                    else:
                        messages.error(request, f"{tien_to}{loi}")

    du_lieu = {
        'san_pham': san_pham,
        'danh_sach_bien_the': danh_sach_bien_the,
        'lich_su_gia': LichSuGiaBienThe.objects.select_related('nguoi_thuc_hien').filter(
            san_pham=san_pham
        ),
        'loi_ma_bt': loi_ma_bt,
        'gia_da_nhap': gia_da_nhap,
    }
    return render(request, 'products/quan_ly_gia.html', du_lieu)


# ==============================================================================
# PHẦN 6: USE CASE 6 - QUẢN LÝ HÌNH ẢNH SẢN PHẨM (TẢI ẢNH TỪ MÁY TÍNH)
# ==============================================================================

@role_required(TaiKhoan.VaiTro.EMPLOYEE, TaiKhoan.VaiTro.MANAGER)
def quan_ly_hinh_anh(request, ma_sp):
    """
    Xem bộ sưu tập ảnh, tải ảnh từ máy tính lên (dùng chunks() theo Chương 6),
    đổi ảnh đại diện chính hoặc xóa ảnh.
    """
    san_pham = get_object_or_404(SanPham, ma_sp=ma_sp)
    danh_sach_anh = HinhAnhSanPham.objects.filter(
        san_pham=san_pham
    ).order_by('-anh_chinh', 'ma_hinh_anh')

    if request.method == 'POST':
        thao_tac = request.POST.get('thao_tac')

        # Thao tác A: Tải ảnh từ máy tính lên
        if thao_tac == 'them_anh':
            tep_anh = request.FILES.get('tep_anh')
            dat_lam_anh_chinh = (request.POST.get('anh_chinh') == 'on')

            if not tep_anh:
                messages.error(request, "Vui lòng chọn một file ảnh từ máy tính của bạn!")
                return redirect('products:quan_ly_hinh_anh', ma_sp=san_pham.ma_sp)

            # 1. Kiểm tra dung lượng (khác 0 và tối đa 5MB)
            if tep_anh.size == 0:
                messages.error(request, "Tệp ảnh rỗng, vui lòng chọn một tệp ảnh hợp lệ!")
                return redirect('products:quan_ly_hinh_anh', ma_sp=san_pham.ma_sp)

            if tep_anh.size > DUNG_LUONG_ANH_TOI_DA:
                messages.error(request, "Tệp ảnh quá lớn! Dung lượng tối đa cho phép là 5MB.")
                return redirect('products:quan_ly_hinh_anh', ma_sp=san_pham.ma_sp)

            # 2. Kiểm tra đuôi file và chữ ký nhị phân (magic bytes) của tệp ảnh
            _, duoi_file = os.path.splitext(tep_anh.name)
            duoi_chuan = duoi_file.lower()
            if duoi_chuan not in DUOI_ANH_HOP_LE:
                messages.error(request, "Định dạng không hợp lệ! Hệ thống chỉ nhận ảnh JPG, PNG hoặc WEBP.")
                return redirect('products:quan_ly_hinh_anh', ma_sp=san_pham.ma_sp)

            if not _la_tep_anh_hop_le(tep_anh, duoi_chuan):
                messages.error(request, "Tệp tải lên không phải ảnh JPG, PNG hoặc WEBP hợp lệ!")
                return redirect('products:quan_ly_hinh_anh', ma_sp=san_pham.ma_sp)

            # 3. Lưu tệp lên thư mục MEDIA_ROOT/products/ bằng chunks() (Chương 6)
            try:
                duong_dan_anh, duong_dan_dia = _luu_tep_anh_len_dia(tep_anh)
            except OSError:
                messages.error(request, "Không thể lưu tệp ảnh lên máy chủ, vui lòng thử lại!")
                return redirect('products:quan_ly_hinh_anh', ma_sp=san_pham.ma_sp)

            # 4. Lưu bản ghi vào CSDL trong transaction để đảm bảo nếu lỗi không làm mất ảnh chính cũ
            try:
                with transaction.atomic():
                    # Nếu sản phẩm chưa có ảnh đại diện chính nào thì tự động đặt ảnh mới làm ảnh chính
                    if not HinhAnhSanPham.objects.filter(san_pham=san_pham, anh_chinh=True).exists():
                        dat_lam_anh_chinh = True

                    if dat_lam_anh_chinh:
                        HinhAnhSanPham.objects.filter(san_pham=san_pham).update(anh_chinh=False)

                    ma_ha_moi = _sinh_ma_hinh_anh_moi()
                    HinhAnhSanPham.objects.create(
                        ma_hinh_anh=ma_ha_moi,
                        san_pham=san_pham,
                        duong_dan=duong_dan_anh,
                        anh_chinh=dat_lam_anh_chinh,
                    )
            except Exception:
                if os.path.isfile(duong_dan_dia):
                    try:
                        os.remove(duong_dan_dia)
                    except OSError:
                        pass
                messages.error(request, "Không thể lưu thông tin ảnh vào cơ sở dữ liệu, vui lòng thử lại!")
                return redirect('products:quan_ly_hinh_anh', ma_sp=san_pham.ma_sp)

            messages.success(request, f"Đã tải lên ảnh '{tep_anh.name}' từ máy tính thành công!")
            return redirect('products:quan_ly_hinh_anh', ma_sp=san_pham.ma_sp)

        # Thao tác B: Đặt một ảnh làm ảnh đại diện chính
        elif thao_tac == 'dat_lam_anh_chinh':
            ma_ha = request.POST.get('ma_hinh_anh')
            anh_duoc_chon = get_object_or_404(HinhAnhSanPham, ma_hinh_anh=ma_ha, san_pham=san_pham)
            with transaction.atomic():
                HinhAnhSanPham.objects.filter(san_pham=san_pham).update(anh_chinh=False)
                anh_duoc_chon.anh_chinh = True
                anh_duoc_chon.save(update_fields=['anh_chinh'])

            messages.success(request, "Đã đổi ảnh đại diện chính của sản phẩm!")
            return redirect('products:quan_ly_hinh_anh', ma_sp=san_pham.ma_sp)

        # Thao tác C: Xóa ảnh
        elif thao_tac == 'xoa_anh':
            ma_ha = request.POST.get('ma_hinh_anh')
            anh_can_xoa = get_object_or_404(HinhAnhSanPham, ma_hinh_anh=ma_ha, san_pham=san_pham)
            duong_dan_cu = anh_can_xoa.duong_dan
            la_anh_chinh = anh_can_xoa.anh_chinh

            with transaction.atomic():
                anh_can_xoa.delete()

                # Nếu vừa xóa ảnh chính thì tự chọn ảnh còn lại đầu tiên làm ảnh chính mới
                if la_anh_chinh:
                    anh_thay_the = HinhAnhSanPham.objects.filter(
                        san_pham=san_pham
                    ).order_by('ma_hinh_anh').first()
                    if anh_thay_the:
                        anh_thay_the.anh_chinh = True
                        anh_thay_the.save(update_fields=['anh_chinh'])

            # Xóa tệp ảnh vật lý nếu không còn bản ghi nào khác dùng chung
            _xoa_tep_anh_neu_khong_con_dung(duong_dan_cu)

            messages.success(request, "Đã xóa ảnh khỏi bộ sưu tập!")
            return redirect('products:quan_ly_hinh_anh', ma_sp=san_pham.ma_sp)

        else:
            messages.warning(request, "Thao tác hình ảnh không hợp lệ.")
            return redirect('products:quan_ly_hinh_anh', ma_sp=san_pham.ma_sp)

    du_lieu = {
        'san_pham': san_pham,
        'danh_sach_anh': danh_sach_anh,
    }
    return render(request, 'products/quan_ly_hinh_anh.html', du_lieu)


# ==============================================================================
# PHẦN 7: USE CASE 9 - QUẢN LÝ DANH MỤC SẢN PHẨM (M2-UC09, WIREFRAME M2-WF11)
# ==============================================================================

@role_required(TaiKhoan.VaiTro.EMPLOYEE, TaiKhoan.VaiTro.MANAGER)
def quan_ly_danh_muc(request):
    """
    Xem danh sách danh mục, số lượng sản phẩm của từng danh mục và thêm mới danh mục.
    """
    if request.method == 'POST':
        form = DanhMucForm(request.POST)
        if form.is_valid():
            try:
                danh_muc_moi = form.save()
            except IntegrityError:
                messages.error(request, "Mã hoặc tên danh mục đã tồn tại, vui lòng kiểm tra lại!")
            else:
                messages.success(request, f"Đã thêm mới danh mục '{danh_muc_moi.ten_dm}' thành công!")
                return redirect('products:quan_ly_danh_muc')
        else:
            messages.error(request, "Dữ liệu danh mục chưa hợp lệ, vui lòng kiểm tra lại biểu mẫu bên dưới.")
    else:
        form = DanhMucForm()

    # Đếm số sản phẩm theo từng danh mục bằng truy vấn nhẹ (chỉ lấy danh_muc_id)
    dem_san_pham = {}
    for danh_muc_id in SanPham.objects.values_list('danh_muc_id', flat=True):
        dem_san_pham[danh_muc_id] = dem_san_pham.get(danh_muc_id, 0) + 1

    danh_sach_dm = list(DanhMucSanPham.objects.all().order_by('ma_dm'))
    for dm in danh_sach_dm:
        dm.so_san_pham = dem_san_pham.get(dm.ma_dm, 0)

    du_lieu = {
        'danh_sach_dm': danh_sach_dm,
        'form': form,
    }
    return render(request, 'products/quan_ly_danh_muc.html', du_lieu)


@role_required(TaiKhoan.VaiTro.EMPLOYEE, TaiKhoan.VaiTro.MANAGER)
def sua_danh_muc(request, ma_dm):
    """
    Chỉnh sửa thông tin của một danh mục đã có.
    """
    danh_muc = get_object_or_404(DanhMucSanPham, ma_dm=ma_dm)
    ten_dm_goc = danh_muc.ten_dm
    trang_thai_cu = danh_muc.trang_thai

    if request.method == 'POST':
        form = DanhMucForm(request.POST, instance=danh_muc)
        if form.is_valid():
            try:
                danh_muc_da_luu = form.save()
            except IntegrityError:
                messages.error(request, "Tên danh mục đã tồn tại trong hệ thống, vui lòng chọn tên khác!")
            else:
                if (
                    trang_thai_cu == 'ACTIVE'
                    and danh_muc_da_luu.trang_thai != 'ACTIVE'
                    and SanPham.objects.filter(danh_muc=danh_muc_da_luu, trang_thai='ACTIVE').exists()
                ):
                    messages.warning(
                        request,
                        f"Đã cập nhật và ngừng áp dụng danh mục '{danh_muc_da_luu.ten_dm}'. Các sản phẩm thuộc danh mục này sẽ tạm ẩn khỏi cửa hàng và không thể đặt mua.",
                    )
                else:
                    messages.success(request, f"Đã cập nhật danh mục '{danh_muc_da_luu.ten_dm}' thành công!")
                return redirect('products:quan_ly_danh_muc')
        else:
            messages.error(request, "Dữ liệu sửa không hợp lệ, vui lòng kiểm tra lại!")
    else:
        form = DanhMucForm(instance=danh_muc)

    du_lieu = {
        'form': form,
        'danh_muc': danh_muc,
        'ten_dm_hien_thi': ten_dm_goc,
    }
    return render(request, 'products/form_danh_muc.html', du_lieu)


@role_required(TaiKhoan.VaiTro.EMPLOYEE, TaiKhoan.VaiTro.MANAGER)
@require_POST
def doi_trang_thai_danh_muc(request, ma_dm):
    """
    Bật / Tắt trạng thái hoạt động của danh mục.
    """
    danh_muc = get_object_or_404(DanhMucSanPham, ma_dm=ma_dm)

    if danh_muc.trang_thai == 'ACTIVE':
        danh_muc.trang_thai = 'INACTIVE'
        messages.warning(
            request,
            f"Đã ngừng áp dụng danh mục '{danh_muc.ten_dm}'. Các sản phẩm thuộc danh mục này sẽ tạm ẩn khỏi cửa hàng và không thể đặt mua."
        )
    else:
        danh_muc.trang_thai = 'ACTIVE'
        messages.success(request, f"Đã mở hoạt động lại danh mục '{danh_muc.ten_dm}'.")

    danh_muc.save(update_fields=['trang_thai'])
    return redirect('products:quan_ly_danh_muc')
