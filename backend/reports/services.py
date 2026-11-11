from datetime import datetime, time, timedelta
from decimal import Decimal
from django.db import models
from django.db.models import Count, Exists, OuterRef, Sum, F, Q, Value, DecimalField
from django.db.models.functions import Coalesce, TruncDate, TruncWeek, TruncMonth
from django.utils import timezone

from customers.models import KhachHang, TaiKhoan
from orders.models import (
    DonHang,
    ChiTietDonHang,
    TrangThaiDonHang,
    TinhThanh,
    PhuongThucThanhToan,
    GioHang,
)
from products.models import SanPham, BienTheSanPham, DanhMucSanPham


def _filter_orders(
    qs,
    product_id=None,
    amount_min=None,
    amount_max=None,
    category_id=None,
    pttt_id=None,
    search_kw=None,
):
    if product_id or category_id:
        matching_lines = ChiTietDonHang.objects.filter(don_hang_id=OuterRef("pk"))
        if product_id:
            matching_lines = matching_lines.filter(bien_the__san_pham_id=product_id)
        if category_id:
            matching_lines = matching_lines.filter(
                bien_the__san_pham__danh_muc_id=category_id
            )
        qs = qs.filter(Exists(matching_lines))
    if amount_min is not None:
        qs = qs.filter(tong_thanh_toan__gte=amount_min)
    if amount_max is not None:
        qs = qs.filter(tong_thanh_toan__lte=amount_max)
    if pttt_id and pttt_id != "ALL":
        qs = qs.filter(phuong_thuc_thanh_toan_id=pttt_id)
    if search_kw:
        keyword = search_kw.strip()
        qs = qs.filter(
            Q(ma_dh__icontains=keyword)
            | Q(khach_hang__ho_ten__icontains=keyword)
            | Q(ho_ten_nguoi_nhan__icontains=keyword)
            | Q(sdt_nguoi_nhan__icontains=keyword)
        )
    return qs


def parse_date_range(preset=None, start_date_str=None, end_date_str=None):
    """
    Quy tắc M5-BR09:
    - start_date <= end_date
    - Khoảng cách tối đa 366 ngày
    - Không vượt quá ngày hiện tại
    - Mặc định: 'this_month' (Tháng này)
    - Trả về: (start_dt, end_dt, prev_start_dt, prev_end_dt, preset_used)
    """
    now = timezone.now()
    today = timezone.localdate(now)

    if preset == "today":
        start_d = today
        end_d = today
    elif preset == "7days":
        start_d = today - timedelta(days=6)
        end_d = today
    elif preset == "last_month":
        # Ngày đầu tháng trước đến ngày cuối tháng trước
        first_day_this_month = today.replace(day=1)
        last_day_last_month = first_day_this_month - timedelta(days=1)
        first_day_last_month = last_day_last_month.replace(day=1)
        start_d = first_day_last_month
        end_d = last_day_last_month
    elif preset == "this_quarter":
        quarter = (today.month - 1) // 3 + 1
        start_month = 3 * (quarter - 1) + 1
        start_d = today.replace(month=start_month, day=1)
        end_d = today
    elif preset == "this_year":
        start_d = today.replace(month=1, day=1)
        end_d = today
    elif preset == "custom" and start_date_str and end_date_str:
        try:
            start_d = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_d = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            start_d = today.replace(day=1)
            end_d = today
            preset = "this_month"
    else:
        # Default: this_month
        start_d = today.replace(day=1)
        end_d = today
        preset = "this_month"

    # Validation
    if end_d > today:
        end_d = today
    if start_d > end_d:
        start_d = end_d
    if (end_d - start_d).days > 366:
        start_d = end_d - timedelta(days=366)

    # Chuyển sang datetime timezone-aware
    start_dt = timezone.make_aware(datetime.combine(start_d, time.min))
    end_dt = timezone.make_aware(datetime.combine(end_d, time.max))

    # Tính kỳ liền trước có cùng độ dài (M5-BR04, M5-BR01...)
    duration = end_d - start_d + timedelta(days=1)
    prev_end_d = start_d - timedelta(days=1)
    prev_start_d = prev_end_d - duration + timedelta(days=1)

    prev_start_dt = timezone.make_aware(datetime.combine(prev_start_d, time.min))
    prev_end_dt = timezone.make_aware(datetime.combine(prev_end_d, time.max))

    return {
        "start_date": start_d,
        "end_date": end_d,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "prev_start_dt": prev_start_dt,
        "prev_end_dt": prev_end_dt,
        "preset": preset,
    }


def calc_percentage_change(current_val, prev_val):
    """Tính % tăng trưởng so với kỳ trước"""
    if not prev_val:
        return None
    curr = float(current_val or 0)
    prev = float(prev_val or 0)
    return round(((curr - prev) / prev) * 100, 1)


def get_dashboard_kpis(date_range, customer_type=None, product_id=None, amount_min=None, amount_max=None, category_id=None):
    """
    Quy tắc M5-BR01, M5-BR02, M5-BR04, M5-BR05:
    1. Doanh thu thuần: Đơn HOAN_THANH theo thoi_diem_hoan_thanh
    2. Đơn hàng: Đơn đặt theo ngay_dat, không tính DA_HUY
    3. Khách hàng mới: KhachHang.ngay_tao trong kỳ
    4. Tỉ lệ chuyển đổi: Số khách đặt đơn / Số khách tương tác (có giỏ hàng cập nhật hoặc đặt đơn)
    5. Giá trị TB/đơn: Doanh thu thuần / Số đơn hoàn thành
    6. Đơn đang xử lý: 5 trạng thái (DA_XAC_NHAN, DANG_CHUAN_BI, CHO_BO_SUNG, SAN_SANG_GIAO, DANG_GIAO)
    """
    start_dt = date_range["start_dt"]
    end_dt = date_range["end_dt"]
    prev_start_dt = date_range["prev_start_dt"]
    prev_end_dt = date_range["prev_end_dt"]

    # Filter base
    qs_orders = _filter_orders(
        DonHang.objects.all(), product_id, amount_min, amount_max, category_id
    )
    if customer_type and customer_type != "ALL":
        qs_orders = qs_orders.filter(loai_khach_hang_ap_dung_id=customer_type)

    # 1. Doanh thu thuần (M5-BR01)
    rev_curr_orders = qs_orders.filter(
        trang_thai=TrangThaiDonHang.HOAN_THANH,
        thoi_diem_hoan_thanh__range=(start_dt, end_dt),
    )
    rev_prev_orders = qs_orders.filter(
        trang_thai=TrangThaiDonHang.HOAN_THANH,
        thoi_diem_hoan_thanh__range=(prev_start_dt, prev_end_dt),
    )
    if product_id or category_id:
        current_lines = ChiTietDonHang.objects.filter(
            don_hang__in=rev_curr_orders,
        )
        previous_lines = ChiTietDonHang.objects.filter(
            don_hang__in=rev_prev_orders,
        )
        if product_id:
            current_lines = current_lines.filter(bien_the__san_pham_id=product_id)
            previous_lines = previous_lines.filter(bien_the__san_pham_id=product_id)
        if category_id:
            current_lines = current_lines.filter(
                bien_the__san_pham__danh_muc_id=category_id
            )
            previous_lines = previous_lines.filter(
                bien_the__san_pham__danh_muc_id=category_id
            )
        rev_curr = current_lines.aggregate(
            total=Coalesce(Sum("thanh_tien"), Value(Decimal(0)))
        )["total"]
        rev_prev = previous_lines.aggregate(
            total=Coalesce(Sum("thanh_tien"), Value(Decimal(0)))
        )["total"]
    else:
        rev_curr = rev_curr_orders.aggregate(
            total=Coalesce(Sum("tong_thanh_toan"), Value(Decimal(0)))
        )["total"]
        rev_prev = rev_prev_orders.aggregate(
            total=Coalesce(Sum("tong_thanh_toan"), Value(Decimal(0)))
        )["total"]

    # 2. Số đơn hàng đặt (M5-BR02)
    orders_curr = qs_orders.filter(
        ngay_dat__range=(start_dt, end_dt),
    ).exclude(trang_thai=TrangThaiDonHang.DA_HUY).count()

    orders_prev = qs_orders.filter(
        ngay_dat__range=(prev_start_dt, prev_end_dt),
    ).exclude(trang_thai=TrangThaiDonHang.DA_HUY).count()

    # 3. Khách hàng mới (M5-BR04)
    new_customers_curr_qs = KhachHang.objects.filter(ngay_tao__range=(start_dt, end_dt))
    new_customers_prev_qs = KhachHang.objects.filter(ngay_tao__range=(prev_start_dt, prev_end_dt))
    if customer_type and customer_type != "ALL":
        new_customers_curr_qs = new_customers_curr_qs.filter(loai_khach_hang_id=customer_type)
        new_customers_prev_qs = new_customers_prev_qs.filter(loai_khach_hang_id=customer_type)
    new_customers_curr = new_customers_curr_qs.count()
    new_customers_prev = new_customers_prev_qs.count()

    # 4. Tỉ lệ chuyển đổi (M5-BR05)
    # Khách có đặt đơn trong kỳ
    customers_ordered = qs_orders.filter(
        ngay_dat__range=(start_dt, end_dt)
    ).values("khach_hang_id").distinct().count()

    # Khách tương tác trong kỳ: có giỏ hàng cập nhật hoặc có đặt đơn
    carts_active_qs = GioHang.objects.filter(
        ngay_cap_nhat__range=(start_dt, end_dt)
    )
    if customer_type and customer_type != "ALL":
        carts_active_qs = carts_active_qs.filter(khach_hang__loai_khach_hang_id=customer_type)
    carts_active = carts_active_qs.values("khach_hang_id").distinct().count()
    
    total_active_customers = max(customers_ordered, carts_active, 1) if (customers_ordered or carts_active) else 0
    conv_rate_curr = round((customers_ordered / total_active_customers * 100), 1) if total_active_customers > 0 else None

    # Kỳ trước
    cust_ord_prev = qs_orders.filter(
        ngay_dat__range=(prev_start_dt, prev_end_dt)
    ).values("khach_hang_id").distinct().count()
    carts_prev_qs = GioHang.objects.filter(
        ngay_cap_nhat__range=(prev_start_dt, prev_end_dt)
    )
    if customer_type and customer_type != "ALL":
        carts_prev_qs = carts_prev_qs.filter(khach_hang__loai_khach_hang_id=customer_type)
    carts_prev = carts_prev_qs.values("khach_hang_id").distinct().count()
    tot_prev = max(cust_ord_prev, carts_prev, 1) if (cust_ord_prev or carts_prev) else 0
    conv_rate_prev = round((cust_ord_prev / tot_prev * 100), 1) if tot_prev > 0 else None

    # 5. Giá trị trung bình / đơn
    completed_orders_cnt = qs_orders.filter(
        trang_thai=TrangThaiDonHang.HOAN_THANH,
        thoi_diem_hoan_thanh__range=(start_dt, end_dt),
    ).count()
    completed_orders_prev_cnt = qs_orders.filter(
        trang_thai=TrangThaiDonHang.HOAN_THANH,
        thoi_diem_hoan_thanh__range=(prev_start_dt, prev_end_dt),
    ).count()

    avg_order_curr = int(rev_curr / completed_orders_cnt) if completed_orders_cnt > 0 else 0
    avg_order_prev = int(rev_prev / completed_orders_prev_cnt) if completed_orders_prev_cnt > 0 else 0

    # 6. Đơn đang xử lý (5 trạng thái vận hành)
    PROCESSING_STATUSES = [
        TrangThaiDonHang.DA_XAC_NHAN,
        TrangThaiDonHang.DANG_CHUAN_BI,
        TrangThaiDonHang.CHO_BO_SUNG,
        TrangThaiDonHang.SAN_SANG_GIAO,
        TrangThaiDonHang.DANG_GIAO,
    ]
    processing_curr = qs_orders.filter(trang_thai__in=PROCESSING_STATUSES).count()
    # So sánh với thời điểm trước (ước lượng kỳ trước dựa trên đơn chưa hoàn thành ở kỳ trước)
    processing_prev = qs_orders.filter(
        ngay_dat__range=(prev_start_dt, prev_end_dt),
        trang_thai__in=PROCESSING_STATUSES,
    ).count()

    return {
        "revenue": {
            "value": int(rev_curr),
            "formatted": f"{int(rev_curr):,}đ".replace(",", "."),
            "pct_change": calc_percentage_change(rev_curr, rev_prev),
        },
        "orders": {
            "value": orders_curr,
            "formatted": f"{orders_curr:,}".replace(",", "."),
            "pct_change": calc_percentage_change(orders_curr, orders_prev),
        },
        "new_customers": {
            "value": new_customers_curr,
            "formatted": f"{new_customers_curr:,}".replace(",", "."),
            "pct_change": calc_percentage_change(new_customers_curr, new_customers_prev),
        },
        "conversion_rate": {
            "value": conv_rate_curr,
            "formatted": f"{conv_rate_curr:.1f}%".replace(".", ",") if conv_rate_curr is not None else "—",
            "pct_change": round(conv_rate_curr - conv_rate_prev, 1)
            if conv_rate_curr is not None and conv_rate_prev is not None else None,
        },
        "avg_order_value": {
            "value": avg_order_curr,
            "formatted": f"{avg_order_curr:,}đ".replace(",", ".") if completed_orders_cnt else "—",
            "pct_change": calc_percentage_change(avg_order_curr, avg_order_prev),
        },
        "processing_orders": {
            "value": processing_curr,
            "formatted": f"{processing_curr:,}".replace(",", "."),
            "pct_change": calc_percentage_change(processing_curr, processing_prev),
        },
    }


def get_revenue_timeline(
    date_range,
    customer_type=None,
    group_by="day",
    product_id=None,
    amount_min=None,
    amount_max=None,
    category_id=None,
    pttt_id=None,
    search_kw=None,
):
    """
    Biểu đồ doanh thu theo thời gian và số đơn đặt.
    Hỗ trợ group_by: 'day', 'week', 'month'
    """
    start_dt = date_range["start_dt"]
    end_dt = date_range["end_dt"]

    qs_completed = DonHang.objects.filter(
        trang_thai=TrangThaiDonHang.HOAN_THANH,
        thoi_diem_hoan_thanh__range=(start_dt, end_dt),
    )
    qs_placed = DonHang.objects.filter(
        ngay_dat__range=(start_dt, end_dt),
    ).exclude(trang_thai=TrangThaiDonHang.DA_HUY)

    if customer_type and customer_type != "ALL":
        qs_completed = qs_completed.filter(loai_khach_hang_ap_dung_id=customer_type)
        qs_placed = qs_placed.filter(loai_khach_hang_ap_dung_id=customer_type)
    qs_completed = _filter_orders(
        qs_completed, product_id, amount_min, amount_max, category_id, pttt_id, search_kw
    )
    qs_placed = _filter_orders(
        qs_placed, product_id, amount_min, amount_max, category_id, pttt_id, search_kw
    )

    if group_by == "month":
        trunc_fn = TruncMonth
        date_format = "%m/%Y"
    elif group_by == "week":
        trunc_fn = TruncWeek
        date_format = "T%W/%Y"
    else:
        trunc_fn = TruncDate
        date_format = "%d/%m"

    # Aggregations
    if product_id or category_id:
        revenue_source = ChiTietDonHang.objects.filter(
            don_hang__in=qs_completed,
        )
        if product_id:
            revenue_source = revenue_source.filter(bien_the__san_pham_id=product_id)
        if category_id:
            revenue_source = revenue_source.filter(
                bien_the__san_pham__danh_muc_id=category_id
            )
        rev_by_date = (
            revenue_source.annotate(period=trunc_fn("don_hang__thoi_diem_hoan_thanh"))
            .values("period")
            .annotate(total_rev=Coalesce(Sum("thanh_tien"), Value(Decimal(0))))
            .order_by("period")
        )
    else:
        rev_by_date = (
            qs_completed.annotate(period=trunc_fn("thoi_diem_hoan_thanh"))
        .values("period")
        .annotate(total_rev=Coalesce(Sum("tong_thanh_toan"), Value(Decimal(0))))
        .order_by("period")
        )

    orders_by_date = (
        qs_placed.annotate(period=trunc_fn("ngay_dat"))
        .values("period")
        .annotate(order_count=Count("ma_dh"))
        .order_by("period")
    )

    rev_map = {}
    for r in rev_by_date:
        if r["period"]:
            p = r["period"].date() if hasattr(r["period"], "date") else r["period"]
            rev_map[p] = float(r["total_rev"])

    ord_map = {}
    for o in orders_by_date:
        if o["period"]:
            p = o["period"].date() if hasattr(o["period"], "date") else o["period"]
            ord_map[p] = o["order_count"]

    # Generate sequence of dates
    curr_d = date_range["start_date"]
    end_d = date_range["end_date"]
    labels = []
    rev_data = []
    ord_data = []

    # If day grouping
    if group_by == "day":
        while curr_d <= end_d:
            labels.append(curr_d.strftime(date_format))
            rev_million = round(rev_map.get(curr_d, 0.0) / 1_000_000, 2)
            rev_data.append(rev_million)
            ord_data.append(ord_map.get(curr_d, 0))
            curr_d += timedelta(days=1)
    else:
        # Month or week: sort unique periods
        all_periods = sorted(set(list(rev_map.keys()) + list(ord_map.keys())))
        if not all_periods:
            labels = [date_range["start_date"].strftime(date_format)]
            rev_data = [0.0]
            ord_data = [0]
        else:
            for p in all_periods:
                labels.append(p.strftime(date_format))
                rev_million = round(rev_map.get(p, 0.0) / 1_000_000, 2)
                rev_data.append(rev_million)
                ord_data.append(ord_map.get(p, 0))

    return {
        "labels": labels,
        "revenue_millions": rev_data,
        "orders_count": ord_data,
    }


def get_customer_type_ratio(
    date_range,
    customer_type=None,
    product_id=None,
    amount_min=None,
    amount_max=None,
    category_id=None,
    pttt_id=None,
):
    """
    Tỉ trọng doanh thu sỉ / lẻ từ các đơn Hoàn thành
    M5-BR08: Khách lẻ vs Khách sỉ
    """
    start_dt = date_range["start_dt"]
    end_dt = date_range["end_dt"]

    completed_orders = _filter_orders(DonHang.objects.filter(
            trang_thai=TrangThaiDonHang.HOAN_THANH,
            thoi_diem_hoan_thanh__range=(start_dt, end_dt),
        ), product_id, amount_min, amount_max, category_id)
    if pttt_id and pttt_id != "ALL":
        completed_orders = completed_orders.filter(phuong_thuc_thanh_toan_id=pttt_id)
    if customer_type and customer_type != "ALL":
        completed_orders = completed_orders.filter(
            loai_khach_hang_ap_dung_id=customer_type
        )
    if product_id or category_id:
        customer_type_field = "don_hang__loai_khach_hang_ap_dung__ten_loai_kh"
        qs = ChiTietDonHang.objects.filter(
            don_hang__in=completed_orders,
        )
        if product_id:
            qs = qs.filter(bien_the__san_pham_id=product_id)
        if category_id:
            qs = qs.filter(bien_the__san_pham__danh_muc_id=category_id)
        qs = qs.values(customer_type_field).annotate(
            total=Sum("thanh_tien")
        )
    else:
        customer_type_field = "loai_khach_hang_ap_dung__ten_loai_kh"
        qs = (
            completed_orders
            .values(customer_type_field)
            .annotate(total=Sum("tong_thanh_toan"))
        )

    data = {"Khách sỉ": 0, "Khách lẻ": 0}
    for row in qs:
        name = row[customer_type_field] or "Khách lẻ"
        val = int(row["total"] or 0)
        if "sỉ" in name.lower() or "si" in name.lower():
            data["Khách sỉ"] += val
        else:
            data["Khách lẻ"] += val

    total = data["Khách sỉ"] + data["Khách lẻ"]
    pct_si = round((data["Khách sỉ"] / total * 100), 1) if total > 0 else 0.0
    pct_le = round(100.0 - pct_si, 1) if total > 0 else 0.0

    return {
        "labels": ["Khách sỉ", "Khách lẻ"],
        "values": [data["Khách sỉ"], data["Khách lẻ"]],
        "percentages": [pct_si, pct_le],
    }


def get_order_status_distribution(date_range, customer_type=None, product_id=None, amount_min=None, amount_max=None, category_id=None):
    """
    Thống kê đơn hàng theo 9 trạng thái (M5-UC01, M5-UC03)
    """
    start_dt = date_range["start_dt"]
    end_dt = date_range["end_dt"]

    qs = DonHang.objects.filter(ngay_dat__range=(start_dt, end_dt))
    if customer_type and customer_type != "ALL":
        qs = qs.filter(loai_khach_hang_ap_dung_id=customer_type)
    qs = _filter_orders(qs, product_id, amount_min, amount_max, category_id)

    counts = dict(qs.values("trang_thai").annotate(c=Count("ma_dh")).values_list("trang_thai", "c"))

    ORDER_STATUS_METADATA = [
        {"key": TrangThaiDonHang.CHO_XAC_NHAN, "label": "Chờ xác nhận", "color": "#D99132"},
        {"key": TrangThaiDonHang.DA_XAC_NHAN, "label": "Đã xác nhận", "color": "#5287B3"},
        {"key": TrangThaiDonHang.DANG_CHUAN_BI, "label": "Đang chuẩn bị hàng", "color": "#5287B3"},
        {"key": TrangThaiDonHang.CHO_BO_SUNG, "label": "Chờ bổ sung hàng", "color": "#5287B3"},
        {"key": TrangThaiDonHang.SAN_SANG_GIAO, "label": "Sẵn sàng giao", "color": "#5287B3"},
        {"key": TrangThaiDonHang.DANG_GIAO, "label": "Đang giao", "color": "#5287B3"},
        {"key": TrangThaiDonHang.GIAO_THANH_CONG, "label": "Giao thành công", "color": "#57976C"},
        {"key": TrangThaiDonHang.HOAN_THANH, "label": "Hoàn thành", "color": "#57976C"},
        {"key": TrangThaiDonHang.DA_HUY, "label": "Đã hủy", "color": "#D9534F"},
    ]

    max_count = max(counts.values()) if counts else 1
    if max_count == 0:
        max_count = 1

    result = []
    for s in ORDER_STATUS_METADATA:
        count = counts.get(s["key"], 0)
        pct = round((count / max_count) * 100, 1)
        result.append({
            "key": s["key"],
            "label": s["label"],
            "count": count,
            "pct": max(pct, 5) if count > 0 else 0,
            "color": s["color"],
        })

    return result


def get_top_selling_products(
    date_range,
    top_n=5,
    sort_by="sl",
    group_level="variant",
    category_id=None,
    customer_type=None,
    product_id=None,
    amount_min=None,
    amount_max=None,
    pttt_id=None,
):
    """
    Quy tắc M5-BR03:
    - Chỉ tính trên đơn HOAN_THANH
    - Xếp hạng theo SL bán (sl) hoặc Doanh thu (rev); đồng hạng thì xếp theo tiêu chí còn lại
    - Đơn giá lấy theo CT_DONHANG.don_gia
    """
    start_dt = date_range["start_dt"]
    end_dt = date_range["end_dt"]

    qs = ChiTietDonHang.objects.filter(
        don_hang__trang_thai=TrangThaiDonHang.HOAN_THANH,
        don_hang__thoi_diem_hoan_thanh__range=(start_dt, end_dt),
    )

    if customer_type and customer_type != "ALL":
        qs = qs.filter(don_hang__loai_khach_hang_ap_dung_id=customer_type)

    if category_id:
        qs = qs.filter(bien_the__san_pham__danh_muc_id=category_id)
    if product_id:
        qs = qs.filter(bien_the__san_pham_id=product_id)
    if amount_min is not None:
        qs = qs.filter(don_hang__tong_thanh_toan__gte=amount_min)
    if amount_max is not None:
        qs = qs.filter(don_hang__tong_thanh_toan__lte=amount_max)
    if pttt_id and pttt_id != "ALL":
        qs = qs.filter(don_hang__phuong_thuc_thanh_toan_id=pttt_id)

    total_revenue_all = qs.aggregate(t=Coalesce(Sum("thanh_tien"), Value(Decimal(0))))["t"]

    if group_level == "product":
        # Group theo Sản phẩm chính
        items = (
            qs.values(
                "bien_the__san_pham__ma_sp",
                "bien_the__san_pham__ten_sp",
                "bien_the__san_pham__danh_muc__ten_dm",
            )
            .annotate(
                total_qty=Sum("so_luong"),
                total_rev=Sum("thanh_tien"),
                latest_order_time=models.Max("don_hang__thoi_diem_hoan_thanh"),
            )
        )
    else:
        # Group theo Biến thể sản phẩm (mặc định)
        items = (
            qs.values(
                "bien_the__ma_bien_the",
                "bien_the__san_pham__ten_sp",
                "bien_the__huong_vi",
                "bien_the__quy_cach",
                "bien_the__san_pham__danh_muc__ten_dm",
                "don_gia",
            )
            .annotate(
                total_qty=Sum("so_luong"),
                total_rev=Sum("thanh_tien"),
                latest_order_time=models.Max("don_hang__thoi_diem_hoan_thanh"),
            )
        )

    # Sorting
    if sort_by == "revenue":
        items = items.order_by("-total_rev", "-total_qty")
    else:
        items = items.order_by("-total_qty", "-total_rev")

    items = items[:top_n]

    result = []
    rank = 1
    for it in items:
        rev = int(it["total_rev"] or 0)
        qty = int(it["total_qty"] or 0)
        pct = round((rev / float(total_revenue_all) * 100), 1) if total_revenue_all > 0 else 0.0

        if group_level == "product":
            name = it["bien_the__san_pham__ten_sp"]
            spec = "-"
            price = "-"
            code = it["bien_the__san_pham__ma_sp"]
        else:
            name = f"{it['bien_the__san_pham__ten_sp']} {it['bien_the__huong_vi']}".strip()
            spec = it["bien_the__quy_cach"]
            price = f"{int(it['don_gia'] or 0):,}đ".replace(",", ".")
            code = it["bien_the__ma_bien_the"]

        latest_time = it.get("latest_order_time")
        latest_time_str = latest_time.strftime("%d/%m/%Y %H:%M") if latest_time else "-"

        result.append({
            "rank": rank,
            "code": code,
            "name": name,
            "category": it["bien_the__san_pham__danh_muc__ten_dm"],
            "spec": spec,
            "price": price,
            "qty": qty,
            "qty_formatted": f"{qty:,}".replace(",", "."),
            "revenue": rev,
            "revenue_formatted": f"{rev:,}đ".replace(",", "."),
            "percentage": pct,
            "latest_order_time": latest_time_str,
        })
        rank += 1

    return result


def get_recent_products(
    limit=10,
    category_id=None,
    product_id=None,
    date_range=None,
    customer_type=None,
    pttt_id=None,
    amount_min=None,
    amount_max=None,
):
    """
    Quy tắc M5-BR15:
    - Sản phẩm bán gần đây: lấy từ các đơn đặt mới nhất không hủy (-ngay_dat)
    - Áp dụng các bộ lọc báo cáo đang chọn.
    """
    qs = (
        ChiTietDonHang.objects.exclude(don_hang__trang_thai=TrangThaiDonHang.DA_HUY)
        .select_related("don_hang", "don_hang__loai_khach_hang_ap_dung", "bien_the", "bien_the__san_pham")
        .order_by("-don_hang__ngay_dat")
    )

    if category_id:
        qs = qs.filter(bien_the__san_pham__danh_muc_id=category_id)
    if product_id:
        qs = qs.filter(bien_the__san_pham_id=product_id)
    if date_range:
        qs = qs.filter(
            don_hang__ngay_dat__range=(
                date_range["start_dt"],
                date_range["end_dt"],
            )
        )
    if customer_type and customer_type != "ALL":
        qs = qs.filter(don_hang__loai_khach_hang_ap_dung_id=customer_type)
    if pttt_id and pttt_id != "ALL":
        qs = qs.filter(don_hang__phuong_thuc_thanh_toan_id=pttt_id)
    if amount_min is not None:
        qs = qs.filter(don_hang__tong_thanh_toan__gte=amount_min)
    if amount_max is not None:
        qs = qs.filter(don_hang__tong_thanh_toan__lte=amount_max)

    qs = qs[:limit]

    result = []
    for row in qs:
        cust_type_name = (
            row.don_hang.loai_khach_hang_ap_dung.ten_loai_kh
            if row.don_hang.loai_khach_hang_ap_dung
            else "Khách lẻ"
        )
        is_si = "sỉ" in cust_type_name.lower() or "si" in cust_type_name.lower()

        result.append({
            "order_code": row.don_hang.ma_dh,
            "product_name": f"{row.bien_the.san_pham.ten_sp} {row.bien_the.huong_vi}".strip(),
            "spec": row.bien_the.quy_cach,
            "qty": row.so_luong,
            "amount": int(row.thanh_tien),
            "amount_formatted": f"{int(row.thanh_tien):,}đ".replace(",", "."),
            "customer_type": "Sỉ" if is_si else "Lẻ",
            "is_si": is_si,
            "order_time": row.don_hang.ngay_dat.strftime("%d/%m %H:%M"),
            "full_time": row.don_hang.ngay_dat.strftime("%d/%m/%Y %H:%M"),
            "stock_status": "Còn hàng",
        })

    return result


def get_revenue_by_area(
    date_range,
    customer_type=None,
    product_id=None,
    amount_min=None,
    amount_max=None,
    category_id=None,
    pttt_id=None,
):
    """
    Quy tắc M5-BR07:
    - Thống kê theo Tỉnh/Thành nhận hàng từ các đơn Hoàn thành
    - Chưa xác định nếu tỉnh thành null
    - Tính số đơn HT, Doanh thu thuần, TB/đơn, % tổng, So với kỳ trước
    """
    start_dt = date_range["start_dt"]
    end_dt = date_range["end_dt"]
    prev_start_dt = date_range["prev_start_dt"]
    prev_end_dt = date_range["prev_end_dt"]

    qs_curr = DonHang.objects.filter(
        trang_thai=TrangThaiDonHang.HOAN_THANH,
        thoi_diem_hoan_thanh__range=(start_dt, end_dt),
    )
    qs_prev = DonHang.objects.filter(
        trang_thai=TrangThaiDonHang.HOAN_THANH,
        thoi_diem_hoan_thanh__range=(prev_start_dt, prev_end_dt),
    )

    if customer_type and customer_type != "ALL":
        qs_curr = qs_curr.filter(loai_khach_hang_ap_dung_id=customer_type)
        qs_prev = qs_prev.filter(loai_khach_hang_ap_dung_id=customer_type)

    qs_curr = _filter_orders(qs_curr, product_id, amount_min, amount_max, category_id, pttt_id)
    qs_prev = _filter_orders(qs_prev, product_id, amount_min, amount_max, category_id, pttt_id)
    if product_id or category_id:
        curr_source = ChiTietDonHang.objects.filter(
            don_hang__in=qs_curr,
        )
        prev_source = ChiTietDonHang.objects.filter(
            don_hang__in=qs_prev,
        )
        if product_id:
            curr_source = curr_source.filter(bien_the__san_pham_id=product_id)
            prev_source = prev_source.filter(bien_the__san_pham_id=product_id)
        if category_id:
            curr_source = curr_source.filter(
                bien_the__san_pham__danh_muc_id=category_id
            )
            prev_source = prev_source.filter(
                bien_the__san_pham__danh_muc_id=category_id
            )
        total_rev = curr_source.aggregate(t=Coalesce(Sum("thanh_tien"), Value(Decimal(0))))["t"]
        curr_agg = curr_source.values("don_hang__tinh_thanh__ten_tinh").annotate(
            count=Count("don_hang_id", distinct=True),
            revenue=Sum("thanh_tien"),
        ).order_by("-revenue")
        prev_agg = dict(
            prev_source.values("don_hang__tinh_thanh__ten_tinh")
            .annotate(revenue=Sum("thanh_tien"))
            .values_list("don_hang__tinh_thanh__ten_tinh", "revenue")
        )
        province_key = "don_hang__tinh_thanh__ten_tinh"
    else:
        total_rev = qs_curr.aggregate(t=Coalesce(Sum("tong_thanh_toan"), Value(Decimal(0))))["t"]
        curr_agg = qs_curr.values("tinh_thanh__ten_tinh").annotate(
            count=Count("ma_dh"),
            revenue=Sum("tong_thanh_toan"),
        ).order_by("-revenue")
        prev_agg = dict(
            qs_prev.values("tinh_thanh__ten_tinh")
            .annotate(revenue=Sum("tong_thanh_toan"))
            .values_list("tinh_thanh__ten_tinh", "revenue")
        )
        province_key = "tinh_thanh__ten_tinh"

    max_rev = curr_agg[0]["revenue"] if curr_agg else Decimal(1)
    if not max_rev or max_rev == 0:
        max_rev = Decimal(1)

    result = []
    for row in curr_agg:
        tinh_name = row[province_key] or "Chưa xác định"
        rev = int(row["revenue"] or 0)
        cnt = row["count"]
        avg = int(rev / cnt) if cnt > 0 else 0
        pct_total = round((rev / float(total_rev) * 100), 1) if total_rev > 0 else 0.0

        prev_rev = int(prev_agg.get(row[province_key], 0) or 0)
        pct_change = calc_percentage_change(rev, prev_rev)
        bar_pct = round((rev / float(max_rev)) * 100, 1)

        result.append({
            "province": tinh_name,
            "order_count": cnt,
            "revenue": rev,
            "revenue_formatted": f"{rev:,}đ".replace(",", "."),
            "avg_per_order": f"{avg:,}đ".replace(",", "."),
            "pct_total": f"{pct_total:.1f}%".replace(".", ","),
            "pct_change": pct_change,
            "bar_pct": bar_pct,
        })

    return result


def get_order_details(
    date_range,
    customer_type=None,
    pttt_id=None,
    search_kw=None,
    page=1,
    page_size=10,
    product_id=None,
    amount_min=None,
    amount_max=None,
    category_id=None,
    sort_by="completion_time",
    sort_dir="desc",
):
    """
    Quy tắc M5-BR06: Bảng chi tiết doanh thu
    - Các đơn Hoàn thành trong kỳ
    - Cột: Mã đơn, Ngày HT, Khách hàng, Loại KH, PTTT, Tiền hàng, Vận chuyển, Tổng TT, Hoàn tiền, Doanh thu thuần
    """
    start_dt = date_range["start_dt"]
    end_dt = date_range["end_dt"]

    qs = (
        DonHang.objects.filter(
            trang_thai=TrangThaiDonHang.HOAN_THANH,
            thoi_diem_hoan_thanh__range=(start_dt, end_dt),
        )
        .select_related("khach_hang", "loai_khach_hang_ap_dung", "phuong_thuc_thanh_toan")
        .prefetch_related("chi_tiet__bien_the__san_pham")
    )

    if customer_type and customer_type != "ALL":
        qs = qs.filter(loai_khach_hang_ap_dung_id=customer_type)
    qs = _filter_orders(qs, product_id, amount_min, amount_max, category_id)

    if pttt_id and pttt_id != "ALL":
        qs = qs.filter(phuong_thuc_thanh_toan_id=pttt_id)

    if search_kw:
        kw = search_kw.strip()
        qs = qs.filter(
            Q(ma_dh__icontains=kw)
            | Q(khach_hang__ho_ten__icontains=kw)
            | Q(ho_ten_nguoi_nhan__icontains=kw)
            | Q(sdt_nguoi_nhan__icontains=kw)
        )

    sort_fields = {
        "order_code": "ma_dh",
        "completion_time": "thoi_diem_hoan_thanh",
        "customer_name": "khach_hang__ho_ten",
        "customer_type": "loai_khach_hang_ap_dung__ten_loai_kh",
        "total": "tong_thanh_toan",
    }
    sort_field = sort_fields.get(sort_by, "thoi_diem_hoan_thanh")
    sort_prefix = "-" if sort_dir != "asc" else ""
    qs = qs.order_by(f"{sort_prefix}{sort_field}", "ma_dh")

    total_records = qs.count()
    total_pages = max(1, (total_records + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * page_size
    page_orders = qs[start_idx : start_idx + page_size]

    # Tính tổng cộng cho footer
    summary = qs.aggregate(
        sum_hang=Coalesce(Sum("tong_tien_hang"), Value(Decimal(0))),
        sum_vc=Coalesce(Sum("phi_van_chuyen"), Value(Decimal(0))),
        sum_tong=Coalesce(Sum("tong_thanh_toan"), Value(Decimal(0))),
    )

    items = []
    for dh in page_orders:
        c_type = dh.loai_khach_hang_ap_dung.ten_loai_kh if dh.loai_khach_hang_ap_dung else "Khách lẻ"
        is_si = "sỉ" in c_type.lower() or "si" in c_type.lower()
        refund = 0  # Khi tích hợp M4 sẽ lấy từ HoanTien/HauMai
        net_rev = int(dh.tong_thanh_toan) - refund

        items.append({
            "order_code": dh.ma_dh,
            "completion_time": dh.thoi_diem_hoan_thanh.strftime("%d/%m/%Y %H:%M") if dh.thoi_diem_hoan_thanh else "-",
            "customer_name": dh.khach_hang.ho_ten if dh.khach_hang else dh.ho_ten_nguoi_nhan,
            "customer_type": "Khách sỉ" if is_si else "Khách lẻ",
            "is_si": is_si,
            "payment_method": dh.phuong_thuc_thanh_toan.ten_pttt if dh.phuong_thuc_thanh_toan else "COD",
            "subtotal": f"{int(dh.tong_tien_hang):,}d".replace(",", "."),
            "shipping_fee": f"{int(dh.phi_van_chuyen):,}d".replace(",", "."),
            "total_payment": f"{int(dh.tong_thanh_toan):,}d".replace(",", "."),
            "refund": f"{refund:,}d".replace(",", "."),
            "net_revenue": f"{net_rev:,}d".replace(",", "."),
            "line_items": [
                {
                    "product_name": line.bien_the.san_pham.ten_sp,
                    "variant": f"{line.bien_the.huong_vi} · {line.bien_the.quy_cach}",
                    "quantity": line.so_luong,
                    "unit_price": f"{int(line.don_gia):,}đ".replace(",", "."),
                    "amount": f"{int(line.thanh_tien):,}đ".replace(",", "."),
                }
                for line in dh.chi_tiet.all()
            ],
        })

    return {
        "items": items,
        "total_records": total_records,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size,
        "summary": {
            "sum_subtotal": f"{int(summary['sum_hang']):,}d".replace(",", "."),
            "sum_shipping": f"{int(summary['sum_vc']):,}d".replace(",", "."),
            "sum_total": f"{int(summary['sum_tong']):,}d".replace(",", "."),
            "sum_refund": "0d",
            "sum_net_revenue": f"{int(summary['sum_tong']):,}d".replace(",", "."),
        },
    }
