import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from customers.models import LoaiKhachHang
from orders.models import PhuongThucThanhToan
from products.models import DanhMucSanPham, SanPham
from .permissions import manager_or_report_staff_required
from . import services


REPORT_PRESETS = {
    "today",
    "7days",
    "this_month",
    "last_month",
    "this_quarter",
    "this_year",
    "custom",
}


def _read_report_date_range(request):
    preset = request.GET.get("preset", "this_month")
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
    date_range, date_error = _read_report_date_range(request)
    if date_error:
        return _filter_error_response(request, date_error)
    preset = date_range["preset"]
    filters, error = _read_report_filters(request)
    if error:
        return _filter_error_response(request, error)

    # Lấy dữ liệu
    kpis = services.get_dashboard_kpis(date_range, customer_type, **filters)
    timeline = services.get_revenue_timeline(date_range, customer_type, group_by="day", **filters)
    customer_ratio = services.get_customer_type_ratio(date_range, **filters)
    status_list = services.get_order_status_distribution(date_range, customer_type, **filters)
    top_products = services.get_top_selling_products(
        date_range, top_n=7, sort_by="revenue", customer_type=customer_type, **filters
    )
    customer_types = LoaiKhachHang.objects.all()

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
        "top_products": top_products,
    }
    return render(request, "reports/dashboard.html", context)


@require_GET
@manager_or_report_staff_required
def detail_report_view(request):
    """
    M5-UC02, M5-UC04, M5-UC05, M5-UC06: Giao diện Báo cáo chi tiết
    """
    active_tab = request.GET.get("tab", "revenue")
    if active_tab not in {"revenue", "products", "recent", "area"}:
        active_tab = "revenue"
    customer_type = request.GET.get("customer_type", "ALL")
    pttt_id = request.GET.get("pttt", "ALL")
    sort_by = request.GET.get("sort_by", "sl")
    order_sort = request.GET.get("order_sort", "completion_time")
    order_sort_dir = request.GET.get("order_sort_dir", "desc")
    if order_sort not in {"order_code", "completion_time", "customer_name", "customer_type", "total"}:
        order_sort = "completion_time"
    if order_sort_dir not in {"asc", "desc"}:
        order_sort_dir = "desc"
    group_level = request.GET.get("level", "variant")
    group_by = request.GET.get("group_by", "day")
    if group_by not in {"day", "week", "month"}:
        group_by = "day"
    search_kw = request.GET.get("q", "")
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
        if page_size not in {10, 25, 50}:
            raise ValueError
    except ValueError:
        return _filter_error_response(request, "Số dòng mỗi trang không hợp lệ.")

    # 1. Tab Doanh thu: Timeline kết hợp (cột DT + đường đơn hàng) & Bảng chi tiết đơn HT
    rev_timeline = services.get_revenue_timeline(
        date_range,
        customer_type,
        group_by=group_by,
        pttt_id=pttt_id,
        search_kw=search_kw,
        **filters,
    )
    customer_ratio = services.get_customer_type_ratio(
        date_range, pttt_id=pttt_id, **filters
    )
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

    # 2. Tab Top sản phẩm
    top_products = services.get_top_selling_products(
        date_range=date_range,
        top_n=20,
        sort_by=sort_by,
        group_level=group_level,
        customer_type=customer_type,
        **filters,
        pttt_id=pttt_id,
    )

    # 3. Tab Bán gần đây
    recent_products = services.get_recent_products(
        limit=15,
        category_id=filters["category_id"],
        product_id=filters["product_id"],
        date_range=date_range,
        customer_type=customer_type,
        pttt_id=pttt_id,
        amount_min=filters["amount_min"],
        amount_max=filters["amount_max"],
    )

    # 4. Tab Khu vực
    area_report = services.get_revenue_by_area(
        date_range, customer_type, pttt_id=pttt_id, **filters
    )

    # Metadata cho bộ lọc
    categories = DanhMucSanPham.objects.filter(trang_thai="ACTIVE")
    customer_types = LoaiKhachHang.objects.all()
    payment_methods = PhuongThucThanhToan.objects.filter(dang_kich_hoat=True)

    context = {
        "page_title": "Báo cáo chi tiết",
        "active_tab": active_tab,
        "date_range": date_range,
        "selected_preset": preset,
        "selected_customer_type": customer_type,
        "selected_pttt": pttt_id,
        "selected_category": filters["category_id"],
        "selected_product": filters["product_id"],
        "amount_min_input": request.GET.get("amount_min", ""),
        "amount_max_input": request.GET.get("amount_max", ""),
        "selected_sort": sort_by,
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
    date_range, date_error = _read_report_date_range(request)
    if date_error:
        return _filter_error_response(request, date_error, api=True)
    filters, error = _read_report_filters(request)
    if error:
        return _filter_error_response(request, error, api=True)

    kpis = services.get_dashboard_kpis(date_range, customer_type, **filters)
    timeline = services.get_revenue_timeline(date_range, customer_type, group_by="day", **filters)
    customer_ratio = services.get_customer_type_ratio(date_range, **filters)
    status_list = services.get_order_status_distribution(date_range, customer_type, **filters)
    top_products = services.get_top_selling_products(
        date_range, top_n=7, sort_by="revenue", customer_type=customer_type, **filters
    )

    return JsonResponse({
        "status": "success",
        "kpis": kpis,
        "timeline": timeline,
        "customer_ratio": customer_ratio,
        "status_list": status_list,
        "top_products": top_products,
    })


@require_GET
@manager_or_report_staff_required
def api_detail_data(request):
    """
    API JSON phục vụ cập nhật bảng và tab bằng AJAX
    """
    tab = request.GET.get("tab", "revenue")
    customer_type = request.GET.get("customer_type", "ALL")
    pttt_id = request.GET.get("pttt", "ALL")
    sort_by = request.GET.get("sort_by", "sl")
    group_level = request.GET.get("level", "variant")
    search_kw = request.GET.get("q", "")
    group_by = request.GET.get("group_by", "day")
    if group_by not in {"day", "week", "month"}:
        group_by = "day"
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
            group_by=group_by,
            pttt_id=pttt_id,
            search_kw=search_kw,
            **filters,
        )
        try:
            page_size = int(request.GET.get("page_size", 10))
            if page_size not in {10, 25, 50}:
                raise ValueError
        except ValueError:
            return _filter_error_response(
                request, "Số dòng mỗi trang không hợp lệ.", api=True
            )
        data["orders"] = services.get_order_details(
            date_range, customer_type, pttt_id, search_kw, page,
            page_size=page_size,
            sort_by=request.GET.get("order_sort", "completion_time"),
            sort_dir=request.GET.get("order_sort_dir", "desc"),
            **filters
        )
    elif tab == "products":
        data["products"] = services.get_top_selling_products(
            date_range, top_n=50, sort_by=sort_by, group_level=group_level,
            customer_type=customer_type, pttt_id=pttt_id, **filters
        )
    elif tab == "recent":
        data["recent"] = services.get_recent_products(
            limit=50,
            category_id=filters["category_id"],
            product_id=filters["product_id"],
            date_range=date_range,
            customer_type=customer_type,
            pttt_id=pttt_id,
            amount_min=filters["amount_min"],
            amount_max=filters["amount_max"],
        )
    elif tab == "area":
        data["area"] = services.get_revenue_by_area(
            date_range, customer_type, pttt_id=pttt_id, **filters
        )

    return JsonResponse({"status": "success", "tab": tab, "data": data})


@require_GET
@manager_or_report_staff_required
def export_report_csv(request):
    """
    M5-UC08: Xuất báo cáo CSV với UTF-8 BOM chuẩn để mở trong Microsoft Excel không bị lỗi font
    """
    tab = request.GET.get("tab", "revenue")
    customer_type = request.GET.get("customer_type", "ALL")
    pttt_id = request.GET.get("pttt", "ALL")
    sort_by = request.GET.get("sort_by", "sl")
    group_level = request.GET.get("level", "variant")
    date_range, date_error = _read_report_date_range(request)
    if date_error:
        return _filter_error_response(request, date_error)
    filters, error = _read_report_filters(request)
    if error:
        return _filter_error_response(request, error)

    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = f'attachment; filename="Bao_cao_Quy_Thu_{tab}.csv"'

    writer = csv.writer(response)

    if tab == "revenue":
        writer.writerow(["Mã đơn", "Thời điểm hoàn thành", "Khách hàng", "Loại khách", "PTTT", "Tiền hàng", "Phí VC", "Tổng TT", "Hoàn tiền", "Doanh thu thuần"])
        orders_data = services.get_order_details(
            date_range, customer_type, pttt_id, page=1, page_size=1000, **filters
        )
        for it in orders_data["items"]:
            writer.writerow([
                it["order_code"],
                it["completion_time"],
                it["customer_name"],
                it["customer_type"],
                it["payment_method"],
                it["subtotal"],
                it["shipping_fee"],
                it["total_payment"],
                it["refund"],
                it["net_revenue"],
            ])
    elif tab == "products":
        writer.writerow(["Hạng", "Mã", "Tên sản phẩm", "Danh mục", "Quy cách", "Đơn giá", "Số lượng bán", "Doanh thu", "Tỉ trọng %", "Thời điểm đơn gần nhất"])
        products = services.get_top_selling_products(
            date_range, top_n=100, sort_by=sort_by, group_level=group_level,
            customer_type=customer_type, pttt_id=pttt_id, **filters
        )
        for p in products:
            writer.writerow([
                p["rank"],
                p["code"],
                p["name"],
                p["category"],
                p["spec"],
                p["price"],
                p["qty"],
                p["revenue_formatted"],
                f"{p['percentage']}%",
                p["latest_order_time"],
            ])
    elif tab == "area":
        writer.writerow(["Tỉnh/Thành", "Số đơn hoàn thành", "Doanh thu thuần", "TB/đơn", "% Tổng", "So kỳ trước"])
        areas = services.get_revenue_by_area(
            date_range, customer_type, pttt_id=pttt_id, **filters
        )
        for a in areas:
            writer.writerow([
                a["province"],
                a["order_count"],
                a["revenue_formatted"],
                a["avg_per_order"],
                a["pct_total"],
                f"{a['pct_change']}%" if a["pct_change"] is not None else "—",
            ])
    else:
        writer.writerow(["Mã đơn", "Sản phẩm", "Quy cách", "Số lượng", "Thành tiền", "Loại khách", "Thời điểm đặt"])
        recents = services.get_recent_products(
            limit=100,
            category_id=filters["category_id"],
            product_id=filters["product_id"],
            date_range=date_range,
            customer_type=customer_type,
            pttt_id=pttt_id,
            amount_min=filters["amount_min"],
            amount_max=filters["amount_max"],
        )
        for r in recents:
            writer.writerow([
                r["order_code"],
                r["product_name"],
                r["spec"],
                r["qty"],
                r["amount_formatted"],
                r["customer_type"],
                r["full_time"],
            ])

    return response
