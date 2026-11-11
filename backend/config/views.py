import csv
import io
import re
import uuid

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.db import IntegrityError, transaction
from django.db.models import Count, Min, Prefetch, Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import logout
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import role_required
from customers.models import (
    DiaChiKH,
    GhiChuKhachHang,
    KhachHang,
    LichSuKhachHang,
    LoaiKhachHang,
    NhanVien,
    TaiKhoan,
)
from customers.services import (
    DichVuLichSuHoSo,
    DichVuTrangThaiTaiKhoan,
    LoiNghiepVuTaiKhoan,
    LoiQuyenTaiKhoan,
)
from orders.models import DonHang, TinhThanh, TrangThaiDonHang
from products.models import (
    BienTheSanPham,
    DanhMucSanPham,
    HinhAnhSanPham,
    SanPham,
)
from products.image_assets import CATEGORY_IMAGE_ASSETS, PRODUCT_IMAGE_ASSETS
from products.search import search_products_by_name

@role_required(
    TaiKhoan.VaiTro.EMPLOYEE,
    TaiKhoan.VaiTro.MANAGER
)
def order_list(request):
    return render(request, "orders/danh_sach.html", {
        "orders": [],
        "loai_khach_hang": LoaiKhachHang.objects.order_by("ma_loai_kh"),
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
            "shipping_provinces": TinhThanh.objects.filter(
                dang_hoat_dong=True
            ).order_by("ten_tinh"),
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
    orders = DonHang.objects.filter(
        khach_hang=request.user.khach_hang
    ).order_by("-ngay_dat")
    completed_orders = orders.filter(
        trang_thai__in=[
            TrangThaiDonHang.HOAN_THANH,
            TrangThaiDonHang.GIAO_THANH_CONG,
        ]
    )
    status_styles = {
        TrangThaiDonHang.HOAN_THANH: ("completed", "status-completed"),
        TrangThaiDonHang.GIAO_THANH_CONG: (
            "completed",
            "status-completed",
        ),
        TrangThaiDonHang.DANG_GIAO: ("shipping", "status-shipping"),
        TrangThaiDonHang.DA_HUY: ("cancelled", "status-cancelled"),
    }
    order_rows = []
    for order in orders:
        products = order.chi_tiet.select_related(
            "bien_the__san_pham"
        ).values_list("bien_the__san_pham__ten_sp", flat=True)
        order_rows.append({
            "ma_don_hang": order.ma_dh,
            "ngay_dat": order.ngay_dat.strftime("%d/%m/%Y"),
            "san_pham": ", ".join(products[:3]) or "Không có chi tiết sản phẩm",
            "tong_tien": order.tong_thanh_toan,
            "trang_thai": order.get_trang_thai_display(),
            "status_key": status_styles.get(
                order.trang_thai,
                ("pending", "status-pending"),
            )[0],
            "status_class": status_styles.get(
                order.trang_thai,
                ("pending", "status-pending"),
            )[1],
            "dia_chi": order.dia_chi_giao_hang,
        })

    return render(
        request,
        "storefront/accounts/purchase_history.html",
        {
            "orders": order_rows,
            "total_orders": orders.count(),
            "completed_orders": completed_orders.count(),
            "total_spent": sum(
                order.tong_thanh_toan for order in completed_orders
            ),
        }
    )

@role_required(
    TaiKhoan.VaiTro.EMPLOYEE,
    TaiKhoan.VaiTro.MANAGER
)
def employee_customer_list_page(request):
    all_customers = KhachHang.objects.select_related(
        "tai_khoan",
        "loai_khach_hang",
    )
    customers_queryset = (
        all_customers
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
    keyword = request.GET.get("q", "").strip()
    customer_type = request.GET.get("type", "").strip()
    customer_status = request.GET.get("status", "").strip()
    if keyword:
        customers_queryset = customers_queryset.filter(
            Q(ma_kh__icontains=keyword)
            | Q(ho_ten__icontains=keyword)
            | Q(email__icontains=keyword)
            | Q(tai_khoan__email__icontains=keyword)
            | Q(so_dien_thoai__icontains=keyword)
        )
    if customer_type in {"retail", "wholesale"}:
        type_text = "Khách sỉ" if customer_type == "wholesale" else "Khách lẻ"
        customers_queryset = customers_queryset.filter(
            loai_khach_hang__ten_loai_kh=type_text
        )
    if customer_status in {
        KhachHang.TrangThai.ACTIVE,
        KhachHang.TrangThai.INACTIVE,
    }:
        customers_queryset = customers_queryset.filter(
            trang_thai=customer_status
        )

    customers = []

    for kh in customers_queryset:

        # Email
        email = (
            kh.tai_khoan.email
            if kh.tai_khoan and kh.tai_khoan.email
            else kh.email
            if kh.email
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
            "tai_khoan_trang_thai": (
                kh.tai_khoan.trang_thai
                if kh.tai_khoan_id
                else None
            ),
        })

    return render(
        request,
        "customers/customer_list.html",
        {
            "customers": customers,
            "total_customers": all_customers.count(),
            "retail_customers": sum(
                c.loai_khach_hang.ten_loai_kh == "Khách lẻ"
                for c in all_customers.select_related("loai_khach_hang")
            ),
            "wholesale_customers": sum(
                c.loai_khach_hang.ten_loai_kh == "Khách sỉ"
                for c in all_customers.select_related("loai_khach_hang")
            ),
            "inactive_customers": sum(
                c.trang_thai == KhachHang.TrangThai.INACTIVE
                for c in all_customers
            ),
            "customers": customers,
            "search_query": keyword,
            "selected_type": customer_type,
            "selected_status": customer_status,
            "is_manager": request.user.vai_tro == TaiKhoan.VaiTro.MANAGER,
        }
    )

@role_required(
    TaiKhoan.VaiTro.EMPLOYEE,
    TaiKhoan.VaiTro.MANAGER
)
def employee_customer_add_page(request):
    if request.method == "POST":
        name = request.POST.get("ho_ten", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("so_dien_thoai", "").strip()
        type_name = request.POST.get("loai_khach_hang", "Khách lẻ").strip()
        errors = []

        if not name:
            errors.append("Vui lòng nhập họ tên khách hàng.")
        if email:
            try:
                EmailValidator()(email)
            except ValidationError:
                errors.append("Email không đúng định dạng.")
            if (
                TaiKhoan.objects.filter(email__iexact=email).exists()
                or KhachHang.objects.filter(email__iexact=email).exists()
            ):
                errors.append("Email đã được sử dụng.")
        if phone and not re.fullmatch(r"\+?[0-9\s().-]{8,15}", phone):
            errors.append("Số điện thoại không đúng định dạng.")
        if phone and (
            KhachHang.objects.filter(so_dien_thoai=phone).exists()
            or TaiKhoan.objects.filter(so_dien_thoai=phone).exists()
        ):
            errors.append("Số điện thoại đã được sử dụng.")
        customer_type = LoaiKhachHang.objects.filter(
            ten_loai_kh=type_name
        ).first()
        if customer_type is None:
            errors.append("Loại khách hàng không hợp lệ.")

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(
                request,
                "customers/customer_add.html",
                {"form_data": request.POST},
            )

        with transaction.atomic():
            customer = KhachHang.objects.create(
                ma_kh=_next_customer_code(),
                tai_khoan=None,
                loai_khach_hang=customer_type,
                ho_ten=name,
                email=email or None,
                so_dien_thoai=phone or None,
            )
            LichSuKhachHang.objects.create(
                ma_lich_su=DichVuLichSuHoSo.tao_ma_lich_su(),
                khach_hang=customer,
                nguoi_thuc_hien=request.user,
                loai_thay_doi=LichSuKhachHang.LoaiThayDoi.PROFILE_CREATE,
                noi_dung_moi="Tạo hồ sơ khách hàng.",
            )
        messages.success(request, "Đã tạo hồ sơ khách hàng.")
        return redirect("employee-customer-detail", ma_kh=customer.ma_kh)

    return render(
        request,
        "customers/customer_add.html",
        {"customer_types": LoaiKhachHang.objects.all()},
    )


def _next_customer_code():
    sequence = KhachHang.objects.count() + 1
    while True:
        code = f"KH{sequence:03d}"
        if not KhachHang.objects.filter(ma_kh=code).exists():
            return code
        sequence += 1


def _record_customer_update(customer, user, old_data):
    new_data = DichVuLichSuHoSo.lay_du_lieu_hien_tai(customer)
    DichVuLichSuHoSo.ghi_lich_su_cap_nhat(
        khach_hang=customer,
        nguoi_thuc_hien=user,
        du_lieu_cu=old_data,
        du_lieu_moi=new_data,
    )


@role_required(
    TaiKhoan.VaiTro.EMPLOYEE,
    TaiKhoan.VaiTro.MANAGER,
)
def employee_customer_detail_page(request, ma_kh):
    customer = get_object_or_404(
        KhachHang.objects.select_related("tai_khoan", "loai_khach_hang"),
        ma_kh=ma_kh,
    )
    is_manager = request.user.vai_tro == TaiKhoan.VaiTro.MANAGER

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "update":
            name = request.POST.get("ho_ten", "").strip()
            email = request.POST.get("email", "").strip().lower()
            phone = request.POST.get("so_dien_thoai", "").strip()
            type_name = request.POST.get("loai_khach_hang", "").strip()
            errors = []

            if not name:
                errors.append("Họ tên khách hàng không được để trống.")
            if email:
                try:
                    EmailValidator()(email)
                except ValidationError:
                    errors.append("Email không đúng định dạng.")
                account_emails = TaiKhoan.objects.filter(
                    email__iexact=email
                )
                if customer.tai_khoan_id:
                    account_emails = account_emails.exclude(
                        pk=customer.tai_khoan_id
                    )
                profile_emails = KhachHang.objects.filter(
                    email__iexact=email
                ).exclude(pk=customer.pk)
                if account_emails.exists() or profile_emails.exists():
                    errors.append("Email đã được sử dụng.")
            elif customer.tai_khoan_id:
                email = customer.tai_khoan.email

            if phone:
                if not re.fullmatch(r"\+?[0-9\s().-]{8,15}", phone):
                    errors.append("Số điện thoại không đúng định dạng.")
                account_phones = TaiKhoan.objects.filter(
                    so_dien_thoai=phone
                )
                if customer.tai_khoan_id:
                    account_phones = account_phones.exclude(
                        pk=customer.tai_khoan_id
                    )
                profile_phones = KhachHang.objects.filter(
                    so_dien_thoai=phone
                ).exclude(pk=customer.pk)
                if account_phones.exists() or profile_phones.exists():
                    errors.append("Số điện thoại đã được sử dụng.")

            customer_type = LoaiKhachHang.objects.filter(
                ten_loai_kh=type_name
            ).first()
            if customer_type is None:
                errors.append("Loại khách hàng không hợp lệ.")

            if errors:
                for error in errors:
                    messages.error(request, error)
                return redirect(
                    "employee-customer-detail",
                    ma_kh=customer.ma_kh,
                )

            old_data = DichVuLichSuHoSo.lay_du_lieu_hien_tai(customer)
            old_type = customer.loai_khach_hang
            with transaction.atomic():
                customer.ho_ten = name
                customer.email = email or None
                customer.so_dien_thoai = phone or None
                customer.loai_khach_hang = customer_type
                customer.save()
                if customer.tai_khoan_id:
                    customer.tai_khoan.email = email
                    customer.tai_khoan.so_dien_thoai = phone or None
                    customer.tai_khoan.save(
                        update_fields=["email", "so_dien_thoai"]
                    )
                _record_customer_update(customer, request.user, old_data)
                if old_type.pk != customer_type.pk:
                    LichSuKhachHang.objects.create(
                        ma_lich_su=DichVuLichSuHoSo.tao_ma_lich_su(),
                        khach_hang=customer,
                        nguoi_thuc_hien=request.user,
                        loai_thay_doi=(
                            LichSuKhachHang.LoaiThayDoi.CUSTOMER_TYPE
                        ),
                        noi_dung_cu=old_type.ten_loai_kh,
                        noi_dung_moi=customer_type.ten_loai_kh,
                    )
            messages.success(request, "Đã cập nhật hồ sơ khách hàng.")

        elif action == "status":
            new_status = request.POST.get("trang_thai", "")
            reason = request.POST.get("ly_do", "").strip()
            if new_status not in {
                KhachHang.TrangThai.ACTIVE,
                KhachHang.TrangThai.INACTIVE,
            }:
                messages.error(request, "Trạng thái khách hàng không hợp lệ.")
            elif (
                new_status == KhachHang.TrangThai.INACTIVE
                and customer.trang_thai != new_status
                and not reason
            ):
                messages.error(
                    request,
                    "Vui lòng nhập lý do ngừng hoạt động.",
                )
            elif new_status != customer.trang_thai:
                old_status = customer.trang_thai
                customer.trang_thai = new_status
                customer.save(update_fields=["trang_thai", "ngay_cap_nhat"])
                LichSuKhachHang.objects.create(
                    ma_lich_su=DichVuLichSuHoSo.tao_ma_lich_su(),
                    khach_hang=customer,
                    nguoi_thuc_hien=request.user,
                    loai_thay_doi=LichSuKhachHang.LoaiThayDoi.STATUS,
                    noi_dung_cu=old_status,
                    noi_dung_moi="; ".join(filter(None, [new_status, reason])),
                )
                messages.success(request, "Đã cập nhật trạng thái khách hàng.")

        elif action == "account_status":
            if not is_manager:
                return HttpResponseForbidden(
                    "Chỉ quản lý mới được khóa hoặc mở khóa tài khoản."
                )
            try:
                DichVuTrangThaiTaiKhoan.thay_doi_trang_thai(
                    khach_hang=customer,
                    nguoi_thuc_hien=request.user,
                    hanh_dong=request.POST.get("hanh_dong", ""),
                )
                messages.success(request, "Đã cập nhật trạng thái tài khoản.")
            except (LoiNghiepVuTaiKhoan, LoiQuyenTaiKhoan) as error:
                messages.error(request, str(error))

        elif action == "note":
            note = request.POST.get("noi_dung", "").strip()
            if not note:
                messages.error(request, "Nội dung ghi chú không được để trống.")
            elif len(note) > 2000:
                messages.error(request, "Ghi chú không được vượt quá 2.000 ký tự.")
            else:
                GhiChuKhachHang.objects.create(
                    khach_hang=customer,
                    nguoi_tao=request.user,
                    noi_dung=note,
                )
                messages.success(request, "Đã thêm ghi chú nội bộ.")
        else:
            messages.error(request, "Thao tác không hợp lệ.")

        return redirect(
            "employee-customer-detail",
            ma_kh=customer.ma_kh,
        )

    orders = DonHang.objects.filter(khach_hang=customer).order_by("-ngay_dat")
    context = {
        "customer": customer,
        "customer_email": (
            customer.tai_khoan.email
            if customer.tai_khoan_id
            else customer.email
        ),
        "customer_phone": (
            customer.tai_khoan.so_dien_thoai
            if customer.tai_khoan_id
            else customer.so_dien_thoai
        ),
        "addresses": customer.dia_chi.all().order_by("-mac_dinh", "-ngay_tao"),
        "customer_types": LoaiKhachHang.objects.all(),
        "is_manager": is_manager,
        "orders": orders,
        "history": customer.lich_su_thay_doi.select_related(
            "nguoi_thuc_hien"
        ),
        "notes": customer.ghi_chu_noi_bo.select_related("nguoi_tao"),
    }
    return render(request, "customers/customer_detail.html", context)


def _filtered_customers(request):
    customers = KhachHang.objects.select_related(
        "tai_khoan",
        "loai_khach_hang",
    ).order_by("ma_kh")
    keyword = request.GET.get("q", "").strip()
    customer_type = request.GET.get("type", "").strip()
    customer_status = request.GET.get("status", "").strip()
    if keyword:
        customers = customers.filter(
            Q(ma_kh__icontains=keyword)
            | Q(ho_ten__icontains=keyword)
            | Q(email__icontains=keyword)
            | Q(tai_khoan__email__icontains=keyword)
            | Q(so_dien_thoai__icontains=keyword)
        )
    if customer_type in {"retail", "wholesale"}:
        name = "Khách sỉ" if customer_type == "wholesale" else "Khách lẻ"
        customers = customers.filter(loai_khach_hang__ten_loai_kh=name)
    if customer_status in {
        KhachHang.TrangThai.ACTIVE,
        KhachHang.TrangThai.INACTIVE,
    }:
        customers = customers.filter(trang_thai=customer_status)
    return customers


@role_required(
    TaiKhoan.VaiTro.EMPLOYEE,
    TaiKhoan.VaiTro.MANAGER,
)
def employee_customer_export_page(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        'attachment; filename="danh-sach-khach-hang.csv"'
    )
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow([
        "ma_kh",
        "ho_ten",
        "email",
        "so_dien_thoai",
        "loai_khach_hang",
        "trang_thai",
        "ngay_tao",
    ])
    for customer in _filtered_customers(request):
        values = [
            customer.ma_kh,
            customer.ho_ten,
            customer.tai_khoan.email if customer.tai_khoan_id else customer.email,
            (
                customer.tai_khoan.so_dien_thoai
                if customer.tai_khoan_id
                else customer.so_dien_thoai
            ),
            customer.loai_khach_hang.ten_loai_kh,
            customer.get_trang_thai_display(),
            customer.ngay_tao.strftime("%Y-%m-%d"),
        ]
        writer.writerow([
            "'" + value if isinstance(value, str) and value[:1] in "=+-@" else value
            for value in values
        ])
    return response


def _validate_customer_import_csv(text):
    reader = csv.DictReader(io.StringIO(text))
    headers = [
        (header or "").strip().lower()
        for header in (reader.fieldnames or [])
    ]
    if "ho_ten" not in headers:
        return [], ["Thiếu cột bắt buộc ho_ten trong tệp CSV."]
    if len(headers) != len(set(headers)):
        return [], ["Tên cột trong tệp CSV không được trùng lặp."]

    reader.fieldnames = headers
    accepted_rows = []
    import_errors = []
    seen_emails = set()
    seen_phones = set()
    status_aliases = {
        "ACTIVE": KhachHang.TrangThai.ACTIVE,
        "HOẠT ĐỘNG": KhachHang.TrangThai.ACTIVE,
        "INACTIVE": KhachHang.TrangThai.INACTIVE,
        "NGỪNG HOẠT ĐỘNG": KhachHang.TrangThai.INACTIVE,
    }

    for row_number, raw_row in enumerate(reader, start=2):
        if not any(value for value in raw_row.values() if isinstance(value, str)):
            continue
        row_errors = []
        if None in raw_row:
            row_errors.append("Số cột dữ liệu không khớp tiêu đề.")
        row = {
            (key or "").strip().lower(): (value or "").strip()
            for key, value in raw_row.items()
            if key is not None and isinstance(value, str)
        }
        name = row.get("ho_ten", "")
        email = row.get("email", "").lower()
        phone = row.get("so_dien_thoai", "")
        raw_type = row.get("loai_khach_hang", "Khách lẻ")
        raw_status = row.get("trang_thai", "ACTIVE").upper()

        if not name or len(name) > 100:
            row_errors.append("Họ tên bắt buộc, tối đa 100 ký tự.")
        if email:
            try:
                EmailValidator()(email)
            except ValidationError:
                row_errors.append("Email không hợp lệ.")
            if (
                TaiKhoan.objects.filter(email__iexact=email).exists()
                or KhachHang.objects.filter(email__iexact=email).exists()
                or email in seen_emails
            ):
                row_errors.append("Email bị trùng.")
            seen_emails.add(email)
        if phone:
            if (
                len(phone) > 15
                or not re.fullmatch(r"\+?[0-9\s().-]{8,15}", phone)
            ):
                row_errors.append("Số điện thoại không hợp lệ.")
            if (
                TaiKhoan.objects.filter(so_dien_thoai=phone).exists()
                or KhachHang.objects.filter(so_dien_thoai=phone).exists()
                or phone in seen_phones
            ):
                row_errors.append("Số điện thoại bị trùng.")
            seen_phones.add(phone)

        normalized_type = raw_type.casefold()
        if normalized_type in {"retail", "khách lẻ"}:
            type_name = "Khách lẻ"
        elif normalized_type in {"wholesale", "khách sỉ"}:
            type_name = "Khách sỉ"
        else:
            type_name = ""
            row_errors.append("Loại khách hàng phải là Khách lẻ hoặc Khách sỉ.")
        status_value = status_aliases.get(raw_status)
        if status_value is None:
            row_errors.append("Trạng thái phải là ACTIVE hoặc INACTIVE.")

        if row_errors:
            import_errors.append(
                f"Dòng {row_number}: {' '.join(row_errors)}"
            )
        else:
            accepted_rows.append(
                {
                    "line": row_number,
                    "ho_ten": name,
                    "email": email,
                    "so_dien_thoai": phone,
                    "loai_khach_hang": type_name,
                    "trang_thai": status_value,
                }
            )

    if not accepted_rows and not import_errors:
        import_errors.append("Tệp CSV không có dữ liệu khách hàng.")
    return accepted_rows, import_errors


def _customer_import_conflicts(rows):
    conflicts = []
    for row in rows:
        if row["email"] and (
            TaiKhoan.objects.filter(email__iexact=row["email"]).exists()
            or KhachHang.objects.filter(email__iexact=row["email"]).exists()
        ):
            conflicts.append(f"Dòng {row['line']}: Email đã được sử dụng.")
        if row["so_dien_thoai"] and (
            TaiKhoan.objects.filter(
                so_dien_thoai=row["so_dien_thoai"]
            ).exists()
            or KhachHang.objects.filter(
                so_dien_thoai=row["so_dien_thoai"]
            ).exists()
        ):
            conflicts.append(
                f"Dòng {row['line']}: Số điện thoại đã được sử dụng."
            )
    return conflicts


@role_required(
    TaiKhoan.VaiTro.EMPLOYEE,
    TaiKhoan.VaiTro.MANAGER,
)
def employee_customer_import_page(request):
    import_errors = []
    imported_count = 0
    preview_rows = []
    preview_ready = False
    if request.method == "POST":
        if request.POST.get("action") == "confirm":
            pending = request.session.pop("customer_import_stage", None)
            if (
                not isinstance(pending, dict)
                or pending.get("user_id") != request.user.pk
                or pending.get("id") != request.POST.get("stage_id")
                or not isinstance(pending.get("rows"), list)
                or not pending["rows"]
            ):
                import_errors.append(
                    "Phiên kiểm tra đã hết hạn. Vui lòng tải tệp lên và kiểm tra lại."
                )
            else:
                preview_rows = pending["rows"]
                import_errors.extend(_customer_import_conflicts(preview_rows))
                if not import_errors:
                    try:
                        with transaction.atomic():
                            for row in preview_rows:
                                customer_type = LoaiKhachHang.objects.get(
                                    ten_loai_kh=row["loai_khach_hang"]
                                )
                                customer = KhachHang.objects.create(
                                    ma_kh=_next_customer_code(),
                                    tai_khoan=None,
                                    loai_khach_hang=customer_type,
                                    ho_ten=row["ho_ten"],
                                    email=row["email"] or None,
                                    so_dien_thoai=row["so_dien_thoai"] or None,
                                    trang_thai=row["trang_thai"],
                                )
                                LichSuKhachHang.objects.create(
                                    ma_lich_su=DichVuLichSuHoSo.tao_ma_lich_su(),
                                    khach_hang=customer,
                                    nguoi_thuc_hien=request.user,
                                    loai_thay_doi=(
                                        LichSuKhachHang.LoaiThayDoi.IMPORT
                                    ),
                                    noi_dung_moi=(
                                        "Nhập từ CSV; trạng thái: "
                                        f"{row['trang_thai']}"
                                    ),
                                )
                    except IntegrityError:
                        import_errors.append(
                            "Dữ liệu đã thay đổi sau khi kiểm tra. "
                            "Chưa có hồ sơ nào được nhập; vui lòng kiểm tra lại tệp."
                        )
                    else:
                        imported_count = len(preview_rows)
        else:
            request.session.pop("customer_import_stage", None)
            upload = request.FILES.get("file")
            if upload is None:
                import_errors.append("Vui lòng chọn tệp CSV để kiểm tra.")
            elif upload.size > 2_000_000:
                import_errors.append("Tệp CSV không được vượt quá 2 MB.")
            else:
                try:
                    text = upload.read().decode("utf-8-sig")
                    preview_rows, import_errors = _validate_customer_import_csv(text)
                except UnicodeDecodeError:
                    import_errors.append(
                        "Không đọc được tệp. Hãy lưu CSV theo mã hóa UTF-8."
                    )
                except csv.Error as error:
                    import_errors.append(f"Tệp CSV không hợp lệ: {error}")
                if preview_rows and not import_errors:
                    stage_id = uuid.uuid4().hex
                    request.session["customer_import_stage"] = {
                        "id": stage_id,
                        "user_id": request.user.pk,
                        "rows": preview_rows,
                    }
                    preview_ready = True
        if imported_count:
            messages.success(
                request,
                f"Đã nhập thành công {imported_count} hồ sơ khách hàng.",
            )
    return render(
        request,
        "customers/customer_import.html",
        {
            "import_errors": import_errors,
            "imported_count": imported_count,
            "preview_rows": preview_rows if preview_ready or import_errors else [],
            "preview_ready": preview_ready,
            "preview_stage_id": (
                request.session.get("customer_import_stage", {}).get("id", "")
                if preview_ready
                else ""
            ),
        },
    )


@role_required(TaiKhoan.VaiTro.MANAGER)
def manager_role_permissions_page(request):
    if request.method == "POST":
        account_id = request.POST.get("tai_khoan_id", "")
        new_role = request.POST.get("vai_tro", "")
        account = get_object_or_404(
            TaiKhoan.objects.filter(
                vai_tro__in=[
                    TaiKhoan.VaiTro.EMPLOYEE,
                    TaiKhoan.VaiTro.MANAGER,
                ]
            ),
            pk=account_id,
        )
        if account.pk == request.user.pk:
            messages.error(request, "Không thể đổi vai trò của chính mình.")
        elif new_role not in {
            TaiKhoan.VaiTro.EMPLOYEE,
            TaiKhoan.VaiTro.MANAGER,
        }:
            messages.error(request, "Vai trò nhân viên không hợp lệ.")
        elif (
            account.vai_tro == TaiKhoan.VaiTro.MANAGER
            and new_role == TaiKhoan.VaiTro.EMPLOYEE
            and TaiKhoan.objects.filter(
                vai_tro=TaiKhoan.VaiTro.MANAGER,
                is_active=True,
                trang_thai=TaiKhoan.TrangThai.ACTIVE,
            ).count() <= 1
        ):
            messages.error(request, "Hệ thống cần ít nhất một quản lý hoạt động.")
        else:
            account.vai_tro = new_role
            account.is_staff = new_role == TaiKhoan.VaiTro.MANAGER
            account.save(update_fields=["vai_tro", "is_staff"])
            messages.success(request, "Đã cập nhật vai trò nhân viên.")
        return redirect("manager-role-permissions")

    staff = NhanVien.objects.select_related("tai_khoan").filter(
        tai_khoan__vai_tro__in=[
            TaiKhoan.VaiTro.EMPLOYEE,
            TaiKhoan.VaiTro.MANAGER,
        ]
    ).order_by("tai_khoan__vai_tro", "ho_ten")
    return render(
        request,
        "customers/role_permissions.html",
        {
            "staff": staff,
            "is_manager": True,
        },
    )
def storefront_home_page(request):
    search_query = request.GET.get("q", "").strip()
    category_products = (
        SanPham.objects.filter(
            trang_thai="ACTIVE",
            bienthesanpham__trang_thai="ACTIVE",
        )
        .order_by("ten_sp")
        .prefetch_related(
            Prefetch(
                "hinhanhsanpham_set",
                queryset=HinhAnhSanPham.objects.order_by(
                    "-anh_chinh",
                    "ma_hinh_anh",
                ),
                to_attr="home_images",
            )
        )
        .distinct()
    )
    categories = (
        DanhMucSanPham.objects.filter(trang_thai="ACTIVE")
        .annotate(
            active_product_count=Count(
                "sanpham",
                filter=Q(
                    sanpham__trang_thai="ACTIVE",
                    sanpham__bienthesanpham__trang_thai="ACTIVE",
                ),
                distinct=True,
            )
        )
        .filter(active_product_count__gt=0)
        .order_by("ten_dm")
        .prefetch_related(
            Prefetch(
                "sanpham_set",
                queryset=category_products,
                to_attr="home_products",
            )
        )
    )
    for category in categories:
        category.home_category_image = CATEGORY_IMAGE_ASSETS.get(category.ma_dm)

    products = (
        SanPham.objects.filter(
            trang_thai="ACTIVE",
            bienthesanpham__trang_thai="ACTIVE",
        )
        .select_related("danh_muc")
        .annotate(
            home_price=Min(
                "bienthesanpham__gia_ban_le",
                filter=Q(bienthesanpham__trang_thai="ACTIVE"),
            ),
            active_variant_count=Count(
                "bienthesanpham",
                filter=Q(bienthesanpham__trang_thai="ACTIVE"),
                distinct=True,
            ),
        )
        .prefetch_related(
            Prefetch(
                "hinhanhsanpham_set",
                queryset=HinhAnhSanPham.objects.order_by(
                    "-anh_chinh",
                    "ma_hinh_anh",
                ),
                to_attr="home_images",
            )
        )
        .distinct()
        .order_by("-ngay_tao", "ten_sp")
    )

    if search_query:
        products = search_products_by_name(products, search_query)

    danh_sach_san_pham = list(products[:8])
    for product in danh_sach_san_pham:
        product.home_product_image = PRODUCT_IMAGE_ASSETS.get(product.ma_sp)

    return render(
        request,
        "storefront/home.html",
        {
            "categories": categories,
            "products": danh_sach_san_pham,
            "search_query": search_query,
        },
    )


@role_required(TaiKhoan.VaiTro.EMPLOYEE)
def employee_dashboard_page(request):
    customers = KhachHang.objects.all()
    return render(
        request,
        "dashboard/employee.html",
        {
            "total_customers": customers.count(),
            "active_customers": customers.filter(
                trang_thai=KhachHang.TrangThai.ACTIVE
            ).count(),
            "new_customers_today": customers.filter(
                ngay_tao__date=timezone.localdate()
            ).count(),
            "wholesale_customers": customers.filter(
                loai_khach_hang__ten_loai_kh="Khách sỉ"
            ).count(),
            "recent_changes": LichSuKhachHang.objects.select_related(
                "khach_hang",
                "nguoi_thuc_hien",
            )[:8],
        },
    )


@role_required(TaiKhoan.VaiTro.MANAGER)
def manager_dashboard_page(request):
    customers = KhachHang.objects.all()
    return render(
        request,
        "dashboard/manager.html",
        {
            "total_customers": customers.count(),
            "active_customers": customers.filter(
                trang_thai=KhachHang.TrangThai.ACTIVE
            ).count(),
            "inactive_customers": customers.filter(
                trang_thai=KhachHang.TrangThai.INACTIVE
            ).count(),
            "wholesale_customers": customers.filter(
                loai_khach_hang__ten_loai_kh="Khách sỉ"
            ).count(),
            "locked_accounts": TaiKhoan.objects.filter(
                vai_tro=TaiKhoan.VaiTro.CUSTOMER,
                trang_thai=TaiKhoan.TrangThai.LOCKED,
            ).count(),
            "active_staff": NhanVien.objects.filter(
                trang_thai=NhanVien.TrangThai.ACTIVE,
                tai_khoan__is_active=True,
            ).count(),
            "recent_changes": LichSuKhachHang.objects.select_related(
                "khach_hang",
                "nguoi_thuc_hien",
            )[:10],
        },
    )

@require_POST
def logout_page(request):
    logout(request)
    return redirect("login-page")