import csv
import json
import re
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from customers.models import LoaiKhachHang, NhanVien
from orders.models import PhuongThucThanhToan
from products.models import DanhMucSanPham, SanPham
from .permissions import manager_or_report_staff_required
from .models import LoaiBaoCao, NhatKyXuatBaoCao
from . import services


def _safe_truncate_json(data: dict, max_len: int) -> str:
    """Serialize dict thành JSON theo đặc tả M5-UC08:
    1. Nếu JSON đầy đủ <= max_len: trả nguyên.
    2. Rút ngắn value chuỗi dài hơn 25 ký tự thành 22 ký tự + '...' rồi ghi JSON nén.
    3. Nếu vẫn vượt: chỉ giữ các value khác rỗng và cắt cứng ở max_len ký tự.
    Bước 3 có thể tạo JSON không hợp lệ nhưng đúng đặc tả (cắt cứng)."""
    import copy
    d = copy.copy(data)
    candidate = json.dumps(d, ensure_ascii=False)
    if len(candidate) <= max_len:
        return candidate
    # Bước 2: rút ngắn value dài hơn 25 ký tự → 22 + "..."
    for k in list(d.keys()):
        if isinstance(d[k], str) and len(d[k]) > 25:
            d[k] = d[k][:22] + "..."
    candidate = json.dumps(d, separators=(",", ":"), ensure_ascii=False)
    if len(candidate) <= max_len:
        return candidate
    # Bước 3: chỉ giữ value khác rỗng, cắt cứng 500 ký tự (theo đặc tả)
    candidate = json.dumps(
        {k: v for k, v in d.items() if v},
        separators=(",", ":"),
        ensure_ascii=False,
    )[:max_len]
    return candidate


REPORT_PRESETS = {
    "today",
    "7days",
    "this_month",
    "last_month",
    "this_quarter",
    "this_year",
    "custom",
}


REPORT_TABS = {"revenue", "products", "recent", "area"}

TAB_TITLES = {
    "revenue": "Chi tiết doanh thu",
    "products": "Sản phẩm bán chạy",
    "recent": "Giao dịch bán gần đây",
    "area": "Doanh thu theo khu vực",
}

ORDER_SORT_FIELDS = {"order_code", "completion_time", "customer_name", "customer_type", "total"}
PAGE_SIZES = {10, 20, 25, 50}

REVENUE_BASIS_LABELS = {
    "tien_hang": "Doanh thu tiền hàng (không gồm phí vận chuyển)",
}

# Ô bắt đầu bằng = + - @ (hoặc tab/CR) có thể bị Excel hiểu là công thức.
# Số/phần trăm thuần (vd "-5.0%") vẫn giữ nguyên.
_PLAIN_NUMBER_RE = re.compile(r"^[+-]?\d+(?:[.,]\d+)?%?$")


def _csv_safe(value):
    """Chống CSV/Excel formula injection: thêm dấu ' trước ô văn bản nguy hiểm."""
    if (
        isinstance(value, str)
        and value
        and value[0] in ("=", "+", "-", "@", "\t", "\r")
        and not _PLAIN_NUMBER_RE.fullmatch(value)
    ):
        return "'" + value
    return value


def _write_csv_row(writer, row):
    writer.writerow([_csv_safe(cell) for cell in row])


def _read_order_sort(request):
    order_sort = request.GET.get("order_sort", "completion_time")
    if order_sort not in ORDER_SORT_FIELDS:
        order_sort = "completion_time"
    order_sort_dir = request.GET.get("order_sort_dir", "desc")
    if order_sort_dir not in {"asc", "desc"}:
        order_sort_dir = "desc"
    return order_sort, order_sort_dir


def _read_report_date_range(request, default_preset="this_month"):
    preset = request.GET.get("preset") or default_preset
    if preset not in REPORT_PRESETS:
        return None, "Kỳ báo cáo không hợp lệ. Hãy chọn lại khoảng thời gian."
    if preset != "custom":
        return services.parse_date_range(preset), None

    start_date = request.GET.get("start_date", "").strip()
    end_date = request.GET.get("end_date", "").strip()
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        return None, "Vui lòng chọn đầy đủ ngày bắt đầu và ngày kết thúc."
    if start > end:
        return None, "Ngày bắt đầu không được sau ngày kết thúc."
    today = timezone.localdate()
    if end > today:
        return None, "Ngày kết thúc không được vượt quá hôm nay."
    if (end - start).days > 366:
        return None, "Khoảng thời gian báo cáo không được vượt quá 366 ngày."
    return services.parse_date_range("custom", start_date, end_date), None


def _read_report_filters(request):
    product_id = request.GET.get("product", "").strip()
    category_id = request.GET.get("category", "").strip()
    if product_id and not SanPham.objects.filter(ma_sp=product_id).exists():
        return None, "Không tìm thấy sản phẩm trong bộ lọc báo cáo."
    if category_id and not DanhMucSanPham.objects.filter(ma_dm=category_id).exists():
        return None, "Không tìm thấy danh mục trong bộ lọc báo cáo."

    amounts = {}
    for field in ("amount_min", "amount_max"):
        raw_value = request.GET.get(field, "").strip()
        if not raw_value:
            amounts[field] = None
            continue
        try:
            value = Decimal(raw_value)
        except InvalidOperation:
            return None, "Giá trị tiền phải là một số hợp lệ."
        if not value.is_finite() or value < 0:
            return None, "Giá trị tiền phải lớn hơn hoặc bằng 0."
        amounts[field] = value

    if (
        amounts["amount_min"] is not None
        and amounts["amount_max"] is not None
        and amounts["amount_min"] > amounts["amount_max"]
    ):
        return None, "Mức tiền tối thiểu không được lớn hơn mức tối đa."

    return {
        "product_id": product_id or None,
        "category_id": category_id or None,
        "amount_min": amounts["amount_min"],
        "amount_max": amounts["amount_max"],
    }, None


def _filter_error_response(request, message, *, api=False):
    if api:
        return JsonResponse({"status": "error", "message": message}, status=400)
    return render(
        request,
        "reports/filter_error.html",
        {
            "page_title": "Không thể áp dụng bộ lọc",
            "error_message": message,
        },
        status=400,
    )


@require_GET
@manager_or_report_staff_required
def dashboard_view(request):
    """
    M5-UC01: Giao diện Dashboard tổng quan
    """
    customer_type = request.GET.get("customer_type", "ALL")
    date_range, date_error = _read_report_date_range(request, default_preset="this_month")
    if date_error:
        return _filter_error_response(request, date_error)
    preset = date_range["preset"]
    filters, error = _read_report_filters(request)
    if error:
        return _filter_error_response(request, error)

    # Lấy dữ liệu
    kpis = services.get_dashboard_kpis(date_range, customer_type, **filters)
    # Biểu đồ tự chọn độ chi tiết theo kỳ: mọi kỳ -> ngày; chỉ "Năm nay" -> tháng
    timeline = services.get_revenue_timeline(date_range, customer_type=customer_type, **filters)
    customer_ratio = services.get_customer_type_ratio(date_range, **filters)
    status_list = services.get_order_status_distribution(date_range, customer_type, **filters)
    status_summary = services.get_order_status_summary(date_range, customer_type, **filters)
    top_products = services.get_top_selling_products(
        date_range, top_n=5, sort_by="sl", customer_type=customer_type, **filters
    )
    customer_types = LoaiKhachHang.objects.all()
    basis = services.revenue_basis(filters["product_id"], filters["category_id"])

    context = {
        "page_title": "Dashboard tổng quan",
        "date_range": date_range,
        "selected_preset": preset,
        "selected_customer_type": customer_type,
        "customer_types": customer_types,
        "products": SanPham.objects.filter(trang_thai="ACTIVE").order_by("ten_sp"),
        "selected_product": filters["product_id"],
        "amount_min_input": request.GET.get("amount_min", ""),
        "amount_max_input": request.GET.get("amount_max", ""),
        "has_product_filter": bool(filters["product_id"]),
        "has_customer_revenue": any(customer_ratio["values"]),
        "kpis": kpis,
        "timeline": timeline,
        "customer_ratio": customer_ratio,
        "status_list": status_list,
        "status_summary": status_summary,
        "top_products": top_products,
        "revenue_basis": basis,
        "revenue_basis_label": REVENUE_BASIS_LABELS[basis],
    }
    return render(request, "reports/dashboard.html", context)


@require_GET
@manager_or_report_staff_required
def detail_report_view(request):
    """
    M5-UC02, M5-UC04, M5-UC05, M5-UC06: Giao diện Báo cáo chi tiết
    """
    active_tab = request.GET.get("tab", "revenue")
    if active_tab not in REPORT_TABS:
        active_tab = "revenue"
    customer_type = request.GET.get("customer_type", "ALL")
    pttt_id = request.GET.get("pttt", "ALL")
    sort_by = request.GET.get("sort_by", "sl")
    order_sort, order_sort_dir = _read_order_sort(request)
    group_level = request.GET.get("level", "variant")
    if group_level not in {"variant", "product"}:
        group_level = "variant"
    search_kw = request.GET.get("q", "").strip()
    date_range, date_error = _read_report_date_range(request)
    if date_error:
        return _filter_error_response(request, date_error)
    preset = date_range["preset"]
    filters, error = _read_report_filters(request)
    if error:
        return _filter_error_response(request, error)
    try:
        page = int(request.GET.get("page", 1))
        if page < 1:
            raise ValueError
    except ValueError:
        return _filter_error_response(request, "Số trang phải là số nguyên lớn hơn 0.")
    try:
        page_size = int(request.GET.get("page_size", 10))
        if page_size not in PAGE_SIZES:
            page_size = 10
    except ValueError:
        page_size = 10

    try:
        top_n = int(request.GET.get("top_n", 5))
        if top_n not in {5, 10, 20}:
            top_n = 5
    except ValueError:
        top_n = 5

    try:
        recent_limit = int(request.GET.get("recent_limit", 10))
        if recent_limit not in {10, 20, 50}:
            recent_limit = 10
    except ValueError:
        recent_limit = 10

    # 1. Tab Doanh thu: Timeline kết hợp (cột DT + đường đơn hàng) & Bảng chi tiết đơn HT
    # Độ chi tiết biểu đồ tự động theo kỳ (mọi kỳ -> ngày; chỉ "Năm nay" -> tháng)
    rev_timeline = services.get_revenue_timeline(
        date_range,
        customer_type,
        pttt_id=pttt_id,
        search_kw=search_kw,
        **filters,
    )
    group_by = rev_timeline["group_by"]
    customer_ratio = services.get_customer_type_ratio(
        date_range, pttt_id=pttt_id, search_kw=search_kw, **filters
    )

    # Chỉ tính dữ liệu cho tab đang được người dùng xem để tối ưu hiệu năng
    order_details = None
    top_products = None
    recent_products = None
    area_report = None

    if active_tab == "products":
        top_products = services.get_top_selling_products(
            date_range=date_range,
            top_n=top_n,
            sort_by=sort_by,
            group_level=group_level,
            customer_type=customer_type,
            pttt_id=pttt_id,
            search_kw=search_kw,
            **filters,
        )
    elif active_tab == "recent":
        recent_products = services.get_recent_products(
            limit=recent_limit,
            category_id=filters["category_id"],
            product_id=filters["product_id"],
            date_range=date_range,
            customer_type=customer_type,
            pttt_id=pttt_id,
            amount_min=filters["amount_min"],
            amount_max=filters["amount_max"],
            search_kw=search_kw,
        )
    elif active_tab == "area":
        area_report = services.get_revenue_by_area(
            date_range, customer_type, pttt_id=pttt_id, search_kw=search_kw, **filters
        )
    else:
        active_tab = "revenue"
        order_details = services.get_order_details(
            date_range=date_range,
            customer_type=customer_type,
            pttt_id=pttt_id,
            search_kw=search_kw,
            page=page,
            page_size=page_size,
            product_id=filters["product_id"],
            amount_min=filters["amount_min"],
            amount_max=filters["amount_max"],
            category_id=filters["category_id"],
            sort_by=order_sort,
            sort_dir=order_sort_dir,
        )

    # Metadata cho bộ lọc
    categories = DanhMucSanPham.objects.filter(trang_thai="ACTIVE")
    customer_types = LoaiKhachHang.objects.all()
    payment_methods = PhuongThucThanhToan.objects.filter(dang_kich_hoat=True)
    basis = services.revenue_basis(filters["product_id"], filters["category_id"])

    context = {
        "page_title": "Báo cáo chi tiết",
        "active_tab": active_tab,
        "tab_titles": TAB_TITLES,
        "active_tab_title": TAB_TITLES[active_tab],
        "revenue_basis": basis,
        "revenue_basis_label": REVENUE_BASIS_LABELS[basis],
        "date_range": date_range,
        "selected_preset": preset,
        "selected_customer_type": customer_type,
        "selected_pttt": pttt_id,
        "selected_category": filters["category_id"],
        "selected_product": filters["product_id"],
        "amount_min_input": request.GET.get("amount_min", ""),
        "amount_max_input": request.GET.get("amount_max", ""),
        "selected_sort": sort_by,
        "selected_top_n": top_n,
        "selected_recent_limit": recent_limit,
        "selected_order_sort": order_sort,
        "selected_order_sort_dir": order_sort_dir,
        "selected_page_size": page_size,
        "selected_group_by": group_by,
        "selected_level": group_level,
        "search_kw": search_kw,
        "current_page": page,
        "categories": categories,
        "products": SanPham.objects.filter(trang_thai="ACTIVE").order_by("ten_sp"),
        "customer_types": customer_types,
        "payment_methods": payment_methods,
        # Tab data
        "rev_timeline": rev_timeline,
        "customer_ratio": customer_ratio,
        "has_customer_revenue": any(customer_ratio["values"]),
        "order_details": order_details,
        "top_products": top_products,
        "recent_products": recent_products,
        "area_report": area_report,
    }
    return render(request, "reports/bao-cao-chi-tiet.html", context)


@require_GET
@manager_or_report_staff_required
def api_dashboard_data(request):
    """
    API JSON phục vụ cập nhật Dashboard bằng AJAX
    """
    customer_type = request.GET.get("customer_type", "ALL")
    date_range, date_error = _read_report_date_range(request, default_preset="this_month")
    if date_error:
        return _filter_error_response(request, date_error, api=True)
    filters, error = _read_report_filters(request)
    if error:
        return _filter_error_response(request, error, api=True)

    kpis = services.get_dashboard_kpis(date_range, customer_type, **filters)
    timeline = services.get_revenue_timeline(date_range, customer_type, **filters)
    customer_ratio = services.get_customer_type_ratio(date_range, **filters)
    status_list = services.get_order_status_distribution(date_range, customer_type, **filters)
    status_summary = services.get_order_status_summary(date_range, customer_type, **filters)
    # Giống hệt trang dashboard: top 5 theo số lượng
    top_products = services.get_top_selling_products(
        date_range, top_n=5, sort_by="sl", customer_type=customer_type, **filters
    )

    return JsonResponse({
        "status": "success",
        "kpis": kpis,
        "timeline": timeline,
        "customer_ratio": customer_ratio,
        "status_list": status_list,
        "status_summary": status_summary,
        "top_products": top_products,
    })


@require_GET
@manager_or_report_staff_required
def api_detail_data(request):
    """
    API JSON phục vụ cập nhật bảng và tab bằng AJAX
    """
    tab = request.GET.get("tab", "revenue")
    if tab not in REPORT_TABS:
        return JsonResponse({"status": "error", "message": "Tab báo cáo không hợp lệ."}, status=400)
    customer_type = request.GET.get("customer_type", "ALL")
    pttt_id = request.GET.get("pttt", "ALL")
    sort_by = request.GET.get("sort_by", "sl")
    order_sort, order_sort_dir = _read_order_sort(request)
    group_level = request.GET.get("level", "variant")
    if group_level not in {"variant", "product"}:
        group_level = "variant"
    search_kw = request.GET.get("q", "").strip()
    date_range, date_error = _read_report_date_range(request)
    if date_error:
        return _filter_error_response(request, date_error, api=True)
    filters, error = _read_report_filters(request)
    if error:
        return _filter_error_response(request, error, api=True)
    try:
        page = int(request.GET.get("page", 1))
        if page < 1:
            raise ValueError
    except ValueError:
        return _filter_error_response(
            request, "Số trang phải là số nguyên lớn hơn 0.", api=True
        )

    data = {}
    if tab == "revenue":
        data["timeline"] = services.get_revenue_timeline(
            date_range,
            customer_type,
            pttt_id=pttt_id,
            search_kw=search_kw,
            **filters,
        )
        try:
            page_size = int(request.GET.get("page_size", 10))
            if page_size not in PAGE_SIZES:
                raise ValueError
        except ValueError:
            return _filter_error_response(
                request, "Số dòng mỗi trang không hợp lệ.", api=True
            )
        data["orders"] = services.get_order_details(
            date_range, customer_type, pttt_id, search_kw, page,
            page_size=page_size,
            sort_by=order_sort,
            sort_dir=order_sort_dir,
            **filters
        )
    elif tab == "products":
        try:
            top_n = int(request.GET.get("top_n", 50))
            if top_n not in {5, 10, 20, 50}:
                top_n = 50
        except ValueError:
            top_n = 50
        data["products"] = services.get_top_selling_products(
            date_range, top_n=top_n, sort_by=sort_by, group_level=group_level,
            customer_type=customer_type, pttt_id=pttt_id, search_kw=search_kw, **filters
        )
    elif tab == "recent":
        try:
            recent_limit = int(request.GET.get("recent_limit", 50))
            if recent_limit not in {10, 20, 50}:
                recent_limit = 50
        except ValueError:
            recent_limit = 50
        data["recent"] = services.get_recent_products(
            limit=recent_limit,
            category_id=filters["category_id"],
            product_id=filters["product_id"],
            date_range=date_range,
            customer_type=customer_type,
            pttt_id=pttt_id,
            amount_min=filters["amount_min"],
            amount_max=filters["amount_max"],
            search_kw=search_kw,
        )
    elif tab == "area":
        data["area"] = services.get_revenue_by_area(
            date_range, customer_type, pttt_id=pttt_id, search_kw=search_kw, **filters
        )

    return JsonResponse({"status": "success", "tab": tab, "data": data})


@require_GET
@manager_or_report_staff_required
def export_report_csv(request):
    """
    M5-UC08: Xuất báo cáo CSV với UTF-8 BOM chuẩn để mở trong Microsoft Excel không bị lỗi font.
    Áp dụng đúng các bộ lọc đang chọn (kể cả ô tìm kiếm q và kiểu sắp xếp) như trên màn hình.
    """
    tab = request.GET.get("tab", "revenue")
    if tab not in REPORT_TABS:
        return HttpResponse("Tab báo cáo không hợp lệ.", status=400)
    customer_type = request.GET.get("customer_type", "ALL")
    pttt_id = request.GET.get("pttt", "ALL")
    sort_by = request.GET.get("sort_by", "sl")
    order_sort, order_sort_dir = _read_order_sort(request)
    search_kw = request.GET.get("q", "").strip()
    group_level = request.GET.get("level", "variant")
    if group_level not in {"variant", "product"}:
        group_level = "variant"
    date_range, date_error = _read_report_date_range(request)
    if date_error:
        return _filter_error_response(request, date_error)
    filters, error = _read_report_filters(request)
    if error:
        return _filter_error_response(request, error)

    # Phải có hồ sơ nhân viên để ghi nhật ký -> kiểm tra trước khi dựng file
    nhan_vien = NhanVien.objects.filter(tai_khoan=request.user).first()
    if nhan_vien is None:
        return HttpResponse(
            "Tài khoản chưa có hồ sơ nhân viên để ghi nhật ký xuất báo cáo.",
            status=403,
        )

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="Bao_cao_Quy_Thu_{tab}.csv"'
    response.write("\ufeff")

    writer = csv.writer(response)

    if tab == "revenue":
        _write_csv_row(writer, ["Mã đơn", "Thời điểm hoàn thành", "Khách hàng", "Loại khách", "PTTT", "Số lượng", "Tiền hàng", "Phí VC", "Tổng tiền"])
        orders_data = services.get_order_details(
            date_range,
            customer_type,
            pttt_id,
            search_kw,
            page=1,
            page_size=None,
            sort_by=order_sort,
            sort_dir=order_sort_dir,
            **filters,
        )
        for it in orders_data["items"]:
            _write_csv_row(writer, [
                it["order_code"],
                it["completion_time"],
                it["customer_name"],
                it["customer_type"],
                it["payment_method"],
                it["quantity"],
                it.get("subtotal_raw", 0),
                it.get("shipping_fee_raw", 0),
                it.get("total_payment_raw", 0),
            ])
    elif tab == "products":
        _write_csv_row(writer, ["Hạng", "Mã", "Tên sản phẩm", "Danh mục", "Quy cách", "Giá bán TB", "Số đơn", "Số lượng", "Doanh thu (tiền hàng)", "Tỉ trọng %", "Thời điểm đơn gần nhất"])
        products = services.get_top_selling_products(
            date_range, top_n=None, sort_by=sort_by, group_level=group_level,
            customer_type=customer_type, pttt_id=pttt_id, search_kw=search_kw, **filters
        )
        for p in products:
            _write_csv_row(writer, [
                p["rank"],
                p["code"],
                p["name"],
                p["category"],
                p["spec"],
                p.get("price_raw", 0),
                p.get("order_count", 0),
                p["qty"],
                p.get("revenue_raw", p.get("revenue", 0)),
                p["percentage"],
                p["latest_order_time"],
            ])
    elif tab == "area":
        revenue_header = "Doanh thu (tiền hàng)"
        _write_csv_row(writer, ["Tỉnh/Thành", "Số đơn hoàn thành", "Số khách", revenue_header, "TB/đơn", "% Tổng", "So kỳ trước"])
        areas = services.get_revenue_by_area(
            date_range, customer_type, pttt_id=pttt_id, search_kw=search_kw, **filters
        )
        for a in areas:
            _write_csv_row(writer, [
                a["province"],
                a["order_count"],
                a.get("customer_count", 0),
                a.get("revenue_raw", a.get("revenue", 0)),
                a.get("avg_per_order_raw", 0),
                a["pct_total"],
                f"{a['pct_change']}%" if a["pct_change"] is not None else "—",
            ])
    elif tab == "recent":
        _write_csv_row(writer, ["Mã đơn", "Sản phẩm", "Quy cách", "Số lượng", "Đơn giá", "Thành tiền", "Loại khách", "Trạng thái đơn", "Thời điểm đặt"])
        recents = services.get_recent_products(
            limit=None,
            category_id=filters["category_id"],
            product_id=filters["product_id"],
            date_range=date_range,
            customer_type=customer_type,
            pttt_id=pttt_id,
            amount_min=filters["amount_min"],
            amount_max=filters["amount_max"],
            search_kw=search_kw,
        )
        for r in recents:
            _write_csv_row(writer, [
                r["order_code"],
                r["product_name"],
                r["spec"],
                r["qty"],
                r.get("unit_price_raw", r.get("unit_price", 0)),
                r.get("amount_raw", r.get("amount", 0)),
                r["customer_type"],
                r["order_status"],
                r["full_time"],
            ])

    loai_bao_cao = {
        "revenue": LoaiBaoCao.CHI_TIET_DOANH_THU,
        "products": LoaiBaoCao.SAN_PHAM_BAN_CHAY,
        "recent": LoaiBaoCao.SAN_PHAM_BAN_GAN_DAY,
        "area": LoaiBaoCao.KHU_VUC,
    }[tab]
    filters_applied = {
        key: value[:100] if key == "q" else value
        for key, value in request.GET.items()
        if key in {
            "preset",
            "start_date",
            "end_date",
            "customer_type",
            "pttt",
            "category",
            "product",
            "amount_min",
            "amount_max",
            "q",
            "sort_by",
            "level",
            "order_sort",
            "order_sort_dir",
        }
    }
    # M5-UC08: mã NKX dạng 7 chữ số theo đặc tả; dùng sequence từ DB + retry để tránh race condition
    sequence = NhatKyXuatBaoCao.objects.count() + 1
    ma_nhat_ky_xuat = f"NKX{sequence:07d}"
    while NhatKyXuatBaoCao.objects.filter(ma_nhat_ky_xuat=ma_nhat_ky_xuat).exists():
        sequence += 1
        ma_nhat_ky_xuat = f"NKX{sequence:07d}"

    bo_loc_clean = dict(filters_applied)
    bo_loc_json = _safe_truncate_json(bo_loc_clean, max_len=500)

    NhatKyXuatBaoCao.objects.create(
        ma_nhat_ky_xuat=ma_nhat_ky_xuat,
        nhan_vien=nhan_vien,
        loai_bao_cao=loai_bao_cao,
        ky_bao_cao=(
            f"{date_range['start_date']:%Y-%m-%d} - "
            f"{date_range['end_date']:%Y-%m-%d}"
        ),
        bo_loc_ap_dung=bo_loc_json or None,
        dinh_dang_file=NhatKyXuatBaoCao.DinhDang.CSV,
    )
    return response