import csv
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from customers.models import LoaiKhachHang
from orders.models import PhuongThucThanhToan
from products.models import DanhMucSanPham
from .permissions import manager_or_report_staff_required
from . import services


@require_GET
@manager_or_report_staff_required
def dashboard_view(request):
    """
    M5-UC01: Giao diện Dashboard tổng quan
    """
    preset = request.GET.get("preset", "this_month")
    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")
    customer_type = request.GET.get("customer_type", "ALL")

    date_range = services.parse_date_range(preset, start_date_str, end_date_str)

    # Lấy dữ liệu
    kpis = services.get_dashboard_kpis(date_range, customer_type)
    timeline = services.get_revenue_timeline(date_range, customer_type, group_by="day")
    customer_ratio = services.get_customer_type_ratio(date_range)
    status_list = services.get_order_status_distribution(date_range, customer_type)
    top_products = services.get_top_selling_products(date_range, top_n=5, sort_by="sl", customer_type=customer_type)
    recent_products = services.get_recent_products(limit=5)

    customer_types = LoaiKhachHang.objects.all()

    context = {
        "page_title": "Dashboard tổng quan",
        "date_range": date_range,
        "selected_preset": preset,
        "selected_customer_type": customer_type,
        "customer_types": customer_types,
        "kpis": kpis,
        "timeline": timeline,
        "customer_ratio": customer_ratio,
        "status_list": status_list,
        "top_products": top_products,
        "recent_products": recent_products,
    }
    return render(request, "reports/dashboard.html", context)


@require_GET
@manager_or_report_staff_required
def detail_report_view(request):
    """
    M5-UC02, M5-UC04, M5-UC05, M5-UC06: Giao diện Báo cáo chi tiết
    """
    active_tab = request.GET.get("tab", "revenue")
    preset = request.GET.get("preset", "this_month")
    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")
    customer_type = request.GET.get("customer_type", "ALL")
    pttt_id = request.GET.get("pttt", "ALL")
    category_id = request.GET.get("category")
    sort_by = request.GET.get("sort_by", "sl")
    group_level = request.GET.get("level", "variant")
    search_kw = request.GET.get("q", "")
    page = int(request.GET.get("page", 1))

    date_range = services.parse_date_range(preset, start_date_str, end_date_str)

    # 1. Tab Doanh thu: Timeline kết hợp (cột DT + đường đơn hàng) & Bảng chi tiết đơn HT
    rev_timeline = services.get_revenue_timeline(date_range, customer_type, group_by="day")
    order_details = services.get_order_details(
        date_range=date_range,
        customer_type=customer_type,
        pttt_id=pttt_id,
        search_kw=search_kw,
        page=page,
        page_size=10,
    )

    # 2. Tab Top sản phẩm
    top_products = services.get_top_selling_products(
        date_range=date_range,
        top_n=20,
        sort_by=sort_by,
        group_level=group_level,
        category_id=category_id,
        customer_type=customer_type,
    )

    # 3. Tab Bán gần đây
    recent_products = services.get_recent_products(limit=15, category_id=category_id)

    # 4. Tab Khu vực
    area_report = services.get_revenue_by_area(date_range, customer_type)

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
        "selected_category": category_id,
        "selected_sort": sort_by,
        "selected_level": group_level,
        "search_kw": search_kw,
        "current_page": page,
        "categories": categories,
        "customer_types": customer_types,
        "payment_methods": payment_methods,
        # Tab data
        "rev_timeline": rev_timeline,
        "order_details": order_details,
        "top_products": top_products,
        "recent_products": recent_products,
        "area_report": area_report,
    }
    return render(request, "reports/bao-cao-chi-tiet.html", context)


@require_GET
def api_dashboard_data(request):
    """
    API JSON phục vụ cập nhật Dashboard bằng AJAX
    """
    preset = request.GET.get("preset", "this_month")
    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")
    customer_type = request.GET.get("customer_type", "ALL")

    date_range = services.parse_date_range(preset, start_date_str, end_date_str)
    kpis = services.get_dashboard_kpis(date_range, customer_type)
    timeline = services.get_revenue_timeline(date_range, customer_type, group_by="day")
    customer_ratio = services.get_customer_type_ratio(date_range)
    status_list = services.get_order_status_distribution(date_range, customer_type)
    top_products = services.get_top_selling_products(date_range, top_n=5, sort_by="sl", customer_type=customer_type)

    return JsonResponse({
        "status": "success",
        "kpis": kpis,
        "timeline": timeline,
        "customer_ratio": customer_ratio,
        "status_list": status_list,
        "top_products": top_products,
    })


@require_GET
def api_detail_data(request):
    """
    API JSON phục vụ cập nhật bảng và tab bằng AJAX
    """
    tab = request.GET.get("tab", "revenue")
    preset = request.GET.get("preset", "this_month")
    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")
    customer_type = request.GET.get("customer_type", "ALL")
    pttt_id = request.GET.get("pttt", "ALL")
    category_id = request.GET.get("category")
    sort_by = request.GET.get("sort_by", "sl")
    group_level = request.GET.get("level", "variant")
    search_kw = request.GET.get("q", "")
    page = int(request.GET.get("page", 1))

    date_range = services.parse_date_range(preset, start_date_str, end_date_str)

    data = {}
    if tab == "revenue":
        data["timeline"] = services.get_revenue_timeline(date_range, customer_type, group_by="day")
        data["orders"] = services.get_order_details(
            date_range, customer_type, pttt_id, search_kw, page, page_size=10
        )
    elif tab == "products":
        data["products"] = services.get_top_selling_products(
            date_range, top_n=50, sort_by=sort_by, group_level=group_level, category_id=category_id, customer_type=customer_type
        )
    elif tab == "recent":
        data["recent"] = services.get_recent_products(limit=50, category_id=category_id)
    elif tab == "area":
        data["area"] = services.get_revenue_by_area(date_range, customer_type)

    return JsonResponse({"status": "success", "tab": tab, "data": data})


@require_GET
def export_report_csv(request):
    """
    M5-UC08: Xuất báo cáo CSV với UTF-8 BOM chuẩn để mở trong Microsoft Excel không bị lỗi font
    """
    tab = request.GET.get("tab", "revenue")
    preset = request.GET.get("preset", "this_month")
    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")
    customer_type = request.GET.get("customer_type", "ALL")
    pttt_id = request.GET.get("pttt", "ALL")
    category_id = request.GET.get("category")
    sort_by = request.GET.get("sort_by", "sl")
    group_level = request.GET.get("level", "variant")

    date_range = services.parse_date_range(preset, start_date_str, end_date_str)

    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = f'attachment; filename="Bao_cao_Quy_Thu_{tab}.csv"'

    writer = csv.writer(response)

    if tab == "revenue":
        writer.writerow(["Mã đơn", "Thời điểm hoàn thành", "Khách hàng", "Loại khách", "PTTT", "Tiền hàng", "Phí VC", "Tổng TT", "Hoàn tiền", "Doanh thu thuần"])
        orders_data = services.get_order_details(date_range, customer_type, pttt_id, page=1, page_size=1000)
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
        products = services.get_top_selling_products(date_range, top_n=100, sort_by=sort_by, group_level=group_level, category_id=category_id, customer_type=customer_type)
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
        areas = services.get_revenue_by_area(date_range, customer_type)
        for a in areas:
            writer.writerow([
                a["province"],
                a["order_count"],
                a["revenue_formatted"],
                a["avg_per_order"],
                a["pct_total"],
                f"{a['pct_change']}%",
            ])
    else:
        writer.writerow(["Mã đơn", "Sản phẩm", "Quy cách", "Số lượng", "Thành tiền", "Loại khách", "Thời điểm đặt"])
        recents = services.get_recent_products(limit=100, category_id=category_id)
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
