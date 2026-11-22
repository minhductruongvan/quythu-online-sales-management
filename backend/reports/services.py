from datetime import datetime, time, timedelta
from decimal import Decimal
from functools import lru_cache
from django.db import models
from django.db.models import Count, Exists, OuterRef, Sum, Q, Value
from django.db.models.functions import (
    Coalesce,
    TruncDate,
    TruncHour,
    TruncMonth,
    TruncQuarter,
    TruncWeek,
)
from django.utils import timezone

from customers.models import KhachHang
from orders.models import ChiTietDonHang, DonHang, GioHang, TrangThaiDonHang

# Chỉ nhận diện khách sỉ theo MÃ loại khách hàng, không đoán theo tên.
WHOLESALE_CUSTOMER_CODE = "LKH002"


@lru_cache(maxsize=1)
def get_wholesale_code():
    """Lấy mã loại KH sỉ từ DB (ten_loai_kh='Khách sỉ'). Fallback về LKH002 nếu không tìm thấy."""
    from customers.models import LoaiKhachHang
    code = LoaiKhachHang.objects.filter(ten_loai_kh="Khách sỉ").values_list("ma_loai_kh", flat=True).first()
    return code or WHOLESALE_CUSTOMER_CODE


GROUP_BY_VALUES = ("hour", "day", "week", "month", "quarter")
GROUP_BY_LABELS = {
    "hour": "Giờ",
    "day": "Ngày",
    "week": "Tuần",
    "month": "Tháng",
    "quarter": "Quý",
}

# Quy tắc độ chi tiết của biểu đồ:
# - Hôm nay: theo giờ (24 giờ: 0h đến 23h)
# - Năm nay: theo tháng (12 tháng: Tháng 1 đến Tháng 12)
# - Các kỳ khác: theo ngày
_PRESET_GROUP_BY = {
    "today": "hour",
    "7days": "day",
    "this_month": "day",
    "last_month": "day",
    "this_quarter": "day",
    "this_year": "month",
}


def is_wholesale(ma_loai_kh):
    """Khách sỉ khi và chỉ khi mã loại khách hàng khớp mã sỉ trong DB."""
    return (ma_loai_kh or "") == get_wholesale_code()


def revenue_basis(product_id=None, category_id=None):
    """
    Cơ sở tính doanh thu (Cách A): luôn là tiền hàng (tong_tien_hang).
    Phí vận chuyển chỉ là tiền thu hộ cho đơn vị vận chuyển và hiện ở cột riêng.
    """
    return "tien_hang"


def _search_filter(keyword):
    """Một bộ điều kiện tìm kiếm duy nhất cho mọi biểu đồ/bảng/tab/xuất CSV."""
    return (
            Q(ma_dh__icontains=keyword)
            | Q(khach_hang__ma_kh__icontains=keyword)
            | Q(khach_hang__ho_ten__icontains=keyword)
            | Q(khach_hang__so_dien_thoai__icontains=keyword)
            | Q(ho_ten_nguoi_nhan__icontains=keyword)
            | Q(sdt_nguoi_nhan__icontains=keyword)
    )


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
        qs = qs.filter(tong_tien_hang__gte=amount_min)
    if amount_max is not None:
        qs = qs.filter(tong_tien_hang__lte=amount_max)
    if pttt_id and pttt_id != "ALL":
        qs = qs.filter(phuong_thuc_thanh_toan_id=pttt_id)
    keyword = (search_kw or "").strip()
    if keyword:
        qs = qs.filter(_search_filter(keyword))
    return qs


def resolve_group_by(date_range, requested=None):
    """
    Chọn độ chi tiết của biểu đồ theo kỳ báo cáo:
    Mọi kỳ (hôm nay, 7 ngày, tháng, quý, tuỳ chọn) -> theo ngày; chỉ "Năm nay" -> theo tháng.
    """
    if requested in GROUP_BY_VALUES:
        return requested
    by_preset = _PRESET_GROUP_BY.get(date_range.get("preset"))
    if by_preset:
        return by_preset
    return "day"


def _add_months(d, months):
    index = d.year * 12 + (d.month - 1) + months
    return d.replace(year=index // 12, month=index % 12 + 1, day=1)


def _iter_periods(start_d, end_d, group_by):
    """Sinh (ngày/giờ đầu kỳ, nhãn) liên tục từ start_d đến end_d, lấp kỳ không có dữ liệu."""
    if group_by == "hour":
        for h in range(24):
            yield h, f"{h}h"
    elif group_by == "day":
        cur = start_d
        while cur <= end_d:
            yield cur, cur.strftime("%d/%m")
            cur += timedelta(days=1)
    elif group_by == "week":
        # Tuần bắt đầu từ Thứ Hai, nhãn theo chuẩn ISO (T01...T53, không có T00)
        cur = start_d - timedelta(days=start_d.weekday())
        while cur <= end_d:
            iso_year, iso_week, _ = cur.isocalendar()
            yield cur, f"T{iso_week:02d}/{iso_year}"
            cur += timedelta(days=7)
    elif group_by == "month":
        # Nhãn "Tháng 1", "Tháng 2"...; chỉ kèm năm khi kỳ báo cáo vắt qua 2 năm
        # (vd "Tháng 12/2025", "Tháng 1/2026") để không bị nhầm.
        with_year = start_d.year != end_d.year
        cur = start_d.replace(day=1)
        while cur <= end_d:
            label = f"Tháng {cur.month}/{cur.year}" if with_year else f"Tháng {cur.month}"
            yield cur, label
            cur = _add_months(cur, 1)
    else:  # quarter
        cur = _add_months(start_d.replace(day=1), -((start_d.month - 1) % 3))
        while cur <= end_d:
            yield cur, f"Q{(cur.month - 1) // 3 + 1}/{cur.year}"
            cur = _add_months(cur, 3)


def _as_date(value):
    return value.date() if hasattr(value, "date") else value


def _period_key(val, group_by):
    if group_by == "hour":
        if hasattr(val, "hour"):
            if timezone.is_aware(val):
                return timezone.localtime(val).hour
            return val.hour
        if isinstance(val, str):
            try:
                dt = datetime.fromisoformat(val)
                if timezone.is_aware(dt):
                    return timezone.localtime(dt).hour
                return dt.hour
            except Exception:
                pass
        return val
    return _as_date(val)


def _order_status_label(don_hang):
    display = getattr(don_hang, "get_trang_thai_display", None)
    return display() if callable(display) else str(don_hang.trang_thai)


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


def get_dashboard_kpis(date_range, customer_type=None, product_id=None, amount_min=None, amount_max=None,
                       category_id=None):
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
            total=Coalesce(Sum("tong_tien_hang"), Value(Decimal(0)))
        )["total"]
        rev_prev = rev_prev_orders.aggregate(
            total=Coalesce(Sum("tong_tien_hang"), Value(Decimal(0)))
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
    # Khách có đặt đơn hợp lệ trong kỳ (loại trừ đơn hủy)
    ordered_curr_qs = (
        qs_orders.filter(ngay_dat__range=(start_dt, end_dt))
        .exclude(trang_thai=TrangThaiDonHang.DA_HUY)
        .exclude(khach_hang_id__isnull=True)
        .values("khach_hang_id")
    )

    # Khách tương tác trong kỳ: có giỏ hàng cập nhật hoặc có đặt đơn
    carts_active_qs = GioHang.objects.filter(ngay_cap_nhat__range=(start_dt, end_dt))
    if customer_type and customer_type != "ALL":
        carts_active_qs = carts_active_qs.filter(khach_hang__loai_khach_hang_id=customer_type)
    if product_id:
        carts_active_qs = carts_active_qs.filter(chi_tiet__bien_the__san_pham_id=product_id)
    if category_id:
        carts_active_qs = carts_active_qs.filter(chi_tiet__bien_the__san_pham__danh_muc_id=category_id)
    carts_curr_qs = carts_active_qs.exclude(khach_hang_id__isnull=True).values("khach_hang_id")

    # UNION trên DB, không kéo về Python
    active_union_curr = ordered_curr_qs.union(carts_curr_qs)
    total_active_customers = active_union_curr.count()
    ordered_count_curr = ordered_curr_qs.count()
    conv_rate_curr = (
        round(ordered_count_curr / total_active_customers * 100, 1)
        if total_active_customers > 0
        else None
    )

    # Kỳ trước
    ordered_prev_qs = (
        qs_orders.filter(ngay_dat__range=(prev_start_dt, prev_end_dt))
        .exclude(trang_thai=TrangThaiDonHang.DA_HUY)
        .exclude(khach_hang_id__isnull=True)
        .values("khach_hang_id")
    )
    carts_prev_qs = GioHang.objects.filter(ngay_cap_nhat__range=(prev_start_dt, prev_end_dt))
    if customer_type and customer_type != "ALL":
        carts_prev_qs = carts_prev_qs.filter(khach_hang__loai_khach_hang_id=customer_type)
    if product_id:
        carts_prev_qs = carts_prev_qs.filter(chi_tiet__bien_the__san_pham_id=product_id)
    if category_id:
        carts_prev_qs = carts_prev_qs.filter(chi_tiet__bien_the__san_pham__danh_muc_id=category_id)
    carts_prev_qs = carts_prev_qs.exclude(khach_hang_id__isnull=True).values("khach_hang_id")

    # UNION trên DB, không kéo về Python
    active_union_prev = ordered_prev_qs.union(carts_prev_qs)
    total_prev = active_union_prev.count()
    ordered_count_prev = ordered_prev_qs.count()
    conv_rate_prev = (
        round(ordered_count_prev / total_prev * 100, 1)
        if total_prev > 0
        else None
    )

    # 5. Giá trị trung bình / đơn
    completed_orders_cnt = qs_orders.filter(
        trang_thai=TrangThaiDonHang.HOAN_THANH,
        thoi_diem_hoan_thanh__range=(start_dt, end_dt),
    ).count()
    completed_orders_prev_cnt = qs_orders.filter(
        trang_thai=TrangThaiDonHang.HOAN_THANH,
        thoi_diem_hoan_thanh__range=(prev_start_dt, prev_end_dt),
    ).count()

    avg_order_curr = round(rev_curr / completed_orders_cnt) if completed_orders_cnt > 0 else 0
    avg_order_prev = round(rev_prev / completed_orders_prev_cnt) if completed_orders_prev_cnt > 0 else 0

    # 6. Đơn đang xử lý (5 trạng thái vận hành trong kỳ)
    PROCESSING_STATUSES = [
        TrangThaiDonHang.DA_XAC_NHAN,
        TrangThaiDonHang.DANG_CHUAN_BI,
        TrangThaiDonHang.CHO_BO_SUNG,
        TrangThaiDonHang.SAN_SANG_GIAO,
        TrangThaiDonHang.DANG_GIAO,
    ]
    processing_curr = qs_orders.filter(
        ngay_dat__range=(start_dt, end_dt),
        trang_thai__in=PROCESSING_STATUSES,
    ).count()
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
            # M5-BR05: so sánh tỉ lệ chuyển đổi bằng HIỆU số điểm phần trăm (pp), không phải % tăng trưởng
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
        group_by="auto",
        product_id=None,
        amount_min=None,
        amount_max=None,
        category_id=None,
        pttt_id=None,
        search_kw=None,
):
    """
    Biểu đồ doanh thu theo thời gian và số đơn đặt.
    group_by: 'auto' (mặc định) | 'day' | 'week' | 'month' | 'quarter'.
    'auto' theo kỳ báo cáo: mọi kỳ -> ngày; chỉ "Năm nay" -> tháng.
    """
    group_by = resolve_group_by(date_range, group_by)
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

    trunc_fn = {
        "hour": TruncHour,
        "day": TruncDate,
        "week": TruncWeek,
        "month": TruncMonth,
        "quarter": TruncQuarter,
    }[group_by]

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
        rev_by_period = (
            revenue_source.annotate(period=trunc_fn("don_hang__thoi_diem_hoan_thanh"))
            .values("period")
            .annotate(total_rev=Coalesce(Sum("thanh_tien"), Value(Decimal(0))))
            .order_by("period")
        )
    else:
        rev_by_period = (
            qs_completed.annotate(period=trunc_fn("thoi_diem_hoan_thanh"))
            .values("period")
            .annotate(total_rev=Coalesce(Sum("tong_tien_hang"), Value(Decimal(0))))
            .order_by("period")
        )

    orders_by_period = (
        qs_placed.annotate(period=trunc_fn("ngay_dat"))
        .values("period")
        .annotate(order_count=Count("ma_dh"))
        .order_by("period")
    )

    rev_map = {
        _period_key(r["period"], group_by): float(r["total_rev"])
        for r in rev_by_period
        if r["period"] is not None
    }
    ord_map = {
        _period_key(o["period"], group_by): o["order_count"]
        for o in orders_by_period
        if o["period"] is not None
    }

    labels = []
    rev_data = []
    rev_exact = []
    ord_data = []
    display_end = date_range["end_date"]
    if date_range.get("preset") == "this_year" and group_by == "month":
        # Xem "Năm nay": luôn hiện đủ 12 tháng, tháng chưa tới có giá trị 0
        display_end = display_end.replace(month=12, day=31)
    for period_start, label in _iter_periods(
            date_range["start_date"], display_end, group_by
    ):
        rev_raw = float(rev_map.get(period_start, 0.0))
        labels.append(label)
        rev_data.append(round(rev_raw / 1_000_000, 2))
        rev_exact.append(int(rev_raw))
        ord_data.append(ord_map.get(period_start, 0))

    return {
        "labels": labels,
        "revenue_millions": rev_data,
        "revenue_exact": rev_exact,
        "orders_count": ord_data,
        "group_by": group_by,
        "group_label": GROUP_BY_LABELS[group_by],
    }


def get_customer_type_ratio(
        date_range,
        product_id=None,
        amount_min=None,
        amount_max=None,
        category_id=None,
        pttt_id=None,
        search_kw=None,
):
    """
    Tỉ trọng doanh thu sỉ / lẻ từ các đơn Hoàn thành
    M5-BR08: Khách lẻ vs Khách sỉ (sỉ = mã loại KH LKH002).
    Luôn hiển thị cả hai loại, không lọc theo loại khách đang chọn.
    """
    start_dt = date_range["start_dt"]
    end_dt = date_range["end_dt"]

    completed_orders = _filter_orders(
        DonHang.objects.filter(
            trang_thai=TrangThaiDonHang.HOAN_THANH,
            thoi_diem_hoan_thanh__range=(start_dt, end_dt),
        ),
        product_id,
        amount_min,
        amount_max,
        category_id,
        pttt_id,
        search_kw,
    )

    if product_id or category_id:
        code_field = "don_hang__loai_khach_hang_ap_dung__ma_loai_kh"
        qs = ChiTietDonHang.objects.filter(
            don_hang__in=completed_orders,
        )
        if product_id:
            qs = qs.filter(bien_the__san_pham_id=product_id)
        if category_id:
            qs = qs.filter(bien_the__san_pham__danh_muc_id=category_id)
        qs = qs.values(code_field).annotate(total=Sum("thanh_tien"))
    else:
        code_field = "loai_khach_hang_ap_dung__ma_loai_kh"
        qs = completed_orders.values(code_field).annotate(
            total=Sum("tong_tien_hang")
        )

    data = {"Khách sỉ": 0, "Khách lẻ": 0}
    for row in qs:
        val = int(row["total"] or 0)
        if is_wholesale(row.get(code_field)):
            data["Khách sỉ"] += val
        else:
            data["Khách lẻ"] += val

    total = data["Khách sỉ"] + data["Khách lẻ"]
    pct_si = round((data["Khách sỉ"] / total * 100), 1) if total > 0 else 0.0
    pct_le = round(100.0 - pct_si, 1) if total > 0 else 0.0

    if total >= 1_000_000:
        total_display = f"{total / 1_000_000:.1f} tr".replace(".", ",")
    elif total > 0:
        total_display = f"{total:,}đ".replace(",", ".")
    else:
        total_display = "0đ"

    total_formatted = f"{total:,}đ".replace(",", ".")

    return {
        "labels": ["Khách sỉ", "Khách lẻ"],
        "values": [data["Khách sỉ"], data["Khách lẻ"]],
        "percentages": [pct_si, pct_le],
        "formatted_values": [
            f"{data['Khách sỉ']:,}đ".replace(",", "."),
            f"{data['Khách lẻ']:,}đ".replace(",", "."),
        ],
        "total": total,
        "total_display": total_display,
        "total_formatted": total_formatted,
    }


def get_order_status_summary(date_range, customer_type=None, product_id=None, amount_min=None, amount_max=None,
                             category_id=None):
    """
    4 nhóm trạng thái đơn hàng (Chờ xác nhận, Đang xử lý, Đã giao, Đã hủy) hiển thị dạng 4 thẻ KPI
    """
    start_dt = date_range["start_dt"]
    end_dt = date_range["end_dt"]
    prev_start_dt = date_range["prev_start_dt"]
    prev_end_dt = date_range["prev_end_dt"]

    qs_curr = DonHang.objects.filter(ngay_dat__range=(start_dt, end_dt))
    qs_prev = DonHang.objects.filter(ngay_dat__range=(prev_start_dt, prev_end_dt))
    if customer_type and customer_type != "ALL":
        qs_curr = qs_curr.filter(loai_khach_hang_ap_dung_id=customer_type)
        qs_prev = qs_prev.filter(loai_khach_hang_ap_dung_id=customer_type)
    qs_curr = _filter_orders(qs_curr, product_id, amount_min, amount_max, category_id)
    qs_prev = _filter_orders(qs_prev, product_id, amount_min, amount_max, category_id)

    curr_counts = dict(qs_curr.values("trang_thai").annotate(c=Count("ma_dh")).values_list("trang_thai", "c"))
    prev_counts = dict(qs_prev.values("trang_thai").annotate(c=Count("ma_dh")).values_list("trang_thai", "c"))

    groups = [
        {
            "key": "pending",
            "label": "Chờ xác nhận",
            "statuses": [TrangThaiDonHang.CHO_XAC_NHAN],
            "color": "#d9822b",
        },
        {
            "key": "processing",
            "label": "Đang xử lý",
            "statuses": [
                TrangThaiDonHang.DA_XAC_NHAN,
                TrangThaiDonHang.DANG_CHUAN_BI,
                TrangThaiDonHang.CHO_BO_SUNG,
                TrangThaiDonHang.SAN_SANG_GIAO,
                TrangThaiDonHang.DANG_GIAO,
            ],
            "color": "#4a7c9b",
        },
        {
            "key": "delivered",
            "label": "Đã giao",
            "statuses": [TrangThaiDonHang.GIAO_THANH_CONG, TrangThaiDonHang.HOAN_THANH],
            "color": "#4d8c57",
        },
        {
            "key": "cancelled",
            "label": "Đã hủy",
            "statuses": [TrangThaiDonHang.DA_HUY],
            "color": "#c54a4a",
        },
    ]

    result = []
    for g in groups:
        curr_val = sum(curr_counts.get(st, 0) for st in g["statuses"])
        prev_val = sum(prev_counts.get(st, 0) for st in g["statuses"])
        pct_change = calc_percentage_change(curr_val, prev_val)
        result.append({
            "key": g["key"],
            "label": g["label"],
            "count": curr_val,
            "formatted": f"{curr_val:,}".replace(",", "."),
            "pct_change": pct_change,
            "color": g["color"],
        })

    return result


def get_order_status_distribution(date_range, customer_type=None, product_id=None, amount_min=None, amount_max=None,
                                  category_id=None):
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
        {"key": TrangThaiDonHang.CHO_XAC_NHAN, "label": "Chờ xác nhận", "color": "#d9822b"},
        {"key": TrangThaiDonHang.DA_XAC_NHAN, "label": "Đã xác nhận", "color": "#4a7c9b"},
        {"key": TrangThaiDonHang.DANG_CHUAN_BI, "label": "Đang chuẩn bị hàng", "color": "#4a7c9b"},
        {"key": TrangThaiDonHang.CHO_BO_SUNG, "label": "Chờ bổ sung hàng", "color": "#4a7c9b"},
        {"key": TrangThaiDonHang.SAN_SANG_GIAO, "label": "Sẵn sàng giao", "color": "#4a7c9b"},
        {"key": TrangThaiDonHang.DANG_GIAO, "label": "Đang giao", "color": "#4a7c9b"},
        {"key": TrangThaiDonHang.GIAO_THANH_CONG, "label": "Giao thành công", "color": "#4d8c57"},
        {"key": TrangThaiDonHang.HOAN_THANH, "label": "Hoàn thành", "color": "#4d8c57"},
        {"key": TrangThaiDonHang.DA_HUY, "label": "Đã hủy", "color": "#c54a4a"},
    ]

    total_orders = sum(counts.values()) if counts else 0

    result = []
    for s in ORDER_STATUS_METADATA:
        count = counts.get(s["key"], 0)
        pct = round((count / total_orders) * 100, 1) if total_orders > 0 and count > 0 else 0
        result.append({
            "key": s["key"],
            "label": s["label"],
            "count": count,
            "pct": pct,
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
        search_kw=None,
):
    """
    Quy tắc M5-BR03:
    - Chỉ tính trên đơn HOAN_THANH
    - Xếp hạng theo SL bán (sl) hoặc Doanh thu (revenue); đồng hạng thì xếp theo tiêu chí còn lại
    - Doanh thu ở đây là TIỀN HÀNG (CT_DONHANG.thanh_tien), không gồm phí vận chuyển
    - Giá bán TB = doanh thu / số lượng
    - Áp dụng đủ bộ lọc, kể cả ô tìm kiếm q
    """
    start_dt = date_range["start_dt"]
    end_dt = date_range["end_dt"]

    orders = DonHang.objects.filter(
        trang_thai=TrangThaiDonHang.HOAN_THANH,
        thoi_diem_hoan_thanh__range=(start_dt, end_dt),
    )
    if customer_type and customer_type != "ALL":
        orders = orders.filter(loai_khach_hang_ap_dung_id=customer_type)
    orders = _filter_orders(
        orders, product_id, amount_min, amount_max, category_id, pttt_id, search_kw
    )

    qs = ChiTietDonHang.objects.filter(don_hang__in=orders)
    if category_id:
        qs = qs.filter(bien_the__san_pham__danh_muc_id=category_id)
    if product_id:
        qs = qs.filter(bien_the__san_pham_id=product_id)

    total_revenue_all = qs.aggregate(t=Coalesce(Sum("thanh_tien"), Value(Decimal(0))))["t"]

    if group_level == "product":
        items = (
            qs.values(
                "bien_the__san_pham__ma_sp",
                "bien_the__san_pham__ten_sp",
                "bien_the__san_pham__danh_muc__ten_dm",
            )
            .annotate(
                total_qty=Sum("so_luong"),
                total_rev=Sum("thanh_tien"),
                order_count=Count("don_hang", distinct=True),
                latest_order_time=models.Max("don_hang__thoi_diem_hoan_thanh"),
            )
        )
    else:
        items = (
            qs.values(
                "bien_the__ma_bien_the",
                "bien_the__san_pham__ma_sp",
                "bien_the__san_pham__ten_sp",
                "bien_the__huong_vi",
                "bien_the__quy_cach",
                "bien_the__san_pham__danh_muc__ten_dm",
                "bien_the__gia_ban_le",
            )
            .annotate(
                total_qty=Sum("so_luong"),
                total_rev=Sum("thanh_tien"),
                order_count=Count("don_hang", distinct=True),
                latest_order_time=models.Max("don_hang__thoi_diem_hoan_thanh"),
            )
        )

    if sort_by == "revenue":
        items = items.order_by("-total_rev", "-total_qty")
    else:
        items = items.order_by("-total_qty", "-total_rev")

    if top_n:
        items = items[:top_n]

    result = []
    for rank, it in enumerate(items, start=1):
        rev = int(it["total_rev"] or 0)
        qty = int(it["total_qty"] or 0)
        pct = round((rev / float(total_revenue_all) * 100), 1) if total_revenue_all > 0 else 0.0
        avg_price = int(rev / qty) if qty > 0 else int(it.get("bien_the__gia_ban_le") or 0)

        if group_level == "product":
            name = it["bien_the__san_pham__ten_sp"]
            spec = "-"
            code = it["bien_the__san_pham__ma_sp"]
            product_code = it["bien_the__san_pham__ma_sp"]
        else:
            ten_sp = (it["bien_the__san_pham__ten_sp"] or "").strip()
            huong_vi = (it["bien_the__huong_vi"] or "").strip()
            quy_cach = (it["bien_the__quy_cach"] or "").strip()
            parts = [p for p in (huong_vi, quy_cach) if p and p != "-"]
            spec = " · ".join(parts) if parts else "-"
            name = ten_sp
            code = it["bien_the__ma_bien_the"]
            product_code = it.get("bien_the__san_pham__ma_sp") or ""

        latest_time = it.get("latest_order_time")
        latest_time_str = timezone.localtime(latest_time).strftime("%d/%m/%Y %H:%M") if latest_time else "-"
        order_count = int(it.get("order_count") or 0)

        result.append({
            "rank": rank,
            "code": code,
            "product_code": product_code,
            "name": name,
            "category": it["bien_the__san_pham__danh_muc__ten_dm"],
            "spec": spec,
            # "price" = Giá bán TB (doanh thu / số lượng), không phải đơn giá niêm yết
            "price": f"{avg_price:,}đ".replace(",", "."),
            "price_raw": avg_price,
            "qty": qty,
            "qty_formatted": f"{qty:,}".replace(",", "."),
            "order_count": order_count,
            "order_count_formatted": f"{order_count:,}".replace(",", "."),
            "revenue": rev,
            "revenue_raw": rev,
            "revenue_formatted": f"{rev:,}đ".replace(",", "."),
            "percentage": pct,
            "latest_order_time": latest_time_str,
        })

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
        search_kw=None,
):
    """
    Quy tắc M5-BR15 - Giao dịch bán gần đây:
    - Mỗi dòng là một dòng hàng của đơn đặt gần nhất, không gồm đơn hủy (-ngay_dat)
    - Gồm cả đơn chưa hoàn thành nên có cột trạng thái đơn
    - Áp dụng đủ bộ lọc báo cáo đang chọn, kể cả ô tìm kiếm q
    """
    orders = DonHang.objects.exclude(trang_thai=TrangThaiDonHang.DA_HUY)
    if date_range:
        orders = orders.filter(
            ngay_dat__range=(date_range["start_dt"], date_range["end_dt"])
        )
    if customer_type and customer_type != "ALL":
        orders = orders.filter(loai_khach_hang_ap_dung_id=customer_type)
    orders = _filter_orders(
        orders, product_id, amount_min, amount_max, category_id, pttt_id, search_kw
    )

    qs = (
        ChiTietDonHang.objects.filter(don_hang__in=orders)
        .select_related(
            "don_hang",
            "don_hang__loai_khach_hang_ap_dung",
            "bien_the",
            "bien_the__san_pham",
            "bien_the__san_pham__danh_muc",
        )
        .order_by("-don_hang__ngay_dat", "don_hang__ma_dh", "pk")
    )
    if category_id:
        qs = qs.filter(bien_the__san_pham__danh_muc_id=category_id)
    if product_id:
        qs = qs.filter(bien_the__san_pham_id=product_id)

    if limit:
        qs = qs[:limit]

    result = []
    for row in qs:
        lkh = row.don_hang.loai_khach_hang_ap_dung
        is_si = is_wholesale(getattr(lkh, "ma_loai_kh", None))

        ten_sp = (row.bien_the.san_pham.ten_sp or "").strip()
        huong_vi = (row.bien_the.huong_vi or "").strip()
        quy_cach = (row.bien_the.quy_cach or "").strip()
        parts = [p for p in (huong_vi, quy_cach) if p and p != "-"]
        variant = " · ".join(parts) if parts else "-"

        result.append({
            "order_code": row.don_hang.ma_dh,
            "order_status": _order_status_label(row.don_hang),
            "order_status_key": row.don_hang.trang_thai,
            "product_code": row.bien_the.san_pham.ma_sp,
            "product_name": ten_sp,
            "category": row.bien_the.san_pham.danh_muc.ten_dm if row.bien_the.san_pham.danh_muc else "-",
            "spec": variant,
            "unit_price": int(row.don_gia),
            "unit_price_raw": int(row.don_gia),
            "unit_price_formatted": f"{int(row.don_gia):,}đ".replace(",", "."),
            "qty": row.so_luong,
            "amount": int(row.thanh_tien),
            "amount_raw": int(row.thanh_tien),
            "amount_formatted": f"{int(row.thanh_tien):,}đ".replace(",", "."),
            "customer_type": "Sỉ" if is_si else "Lẻ",
            "is_si": is_si,
            "order_time": timezone.localtime(row.don_hang.ngay_dat).strftime("%d/%m %H:%M"),
            "full_time": timezone.localtime(row.don_hang.ngay_dat).strftime("%d/%m/%Y %H:%M"),
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
        search_kw=None,
):
    """
    Quy tắc M5-BR07 - Doanh thu theo khu vực:
    - Nhóm theo Tỉnh/Thành nhận hàng từ các đơn Hoàn thành; 'Chưa xác định' nếu tỉnh thành null
    - Doanh thu = tiền hàng (không gồm phí vận chuyển) khi không lọc sản phẩm/danh mục;
      khi có lọc sản phẩm/danh mục chỉ tính tiền hàng của các dòng khớp (xem revenue_basis)
    - Cột: số đơn HT, số khách, doanh thu, TB/đơn, % tổng, so với kỳ trước
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

    qs_curr = _filter_orders(
        qs_curr, product_id, amount_min, amount_max, category_id, pttt_id, search_kw
    )
    qs_prev = _filter_orders(
        qs_prev, product_id, amount_min, amount_max, category_id, pttt_id, search_kw
    )
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
        curr_agg = list(
            curr_source.values("don_hang__tinh_thanh__ten_tinh")
            .annotate(
                count=Count("don_hang_id", distinct=True),
                customers=Count("don_hang__khach_hang", distinct=True),
                revenue=Sum("thanh_tien"),
            )
            .order_by("-revenue")
        )
        prev_agg = dict(
            prev_source.values("don_hang__tinh_thanh__ten_tinh")
            .annotate(revenue=Sum("thanh_tien"))
            .values_list("don_hang__tinh_thanh__ten_tinh", "revenue")
        )
        province_key = "don_hang__tinh_thanh__ten_tinh"
    else:
        total_rev = qs_curr.aggregate(t=Coalesce(Sum("tong_tien_hang"), Value(Decimal(0))))["t"]
        curr_agg = list(
            qs_curr.values("tinh_thanh__ten_tinh")
            .annotate(
                count=Count("ma_dh"),
                customers=Count("khach_hang", distinct=True),
                revenue=Sum("tong_tien_hang"),
            )
            .order_by("-revenue")
        )
        prev_agg = dict(
            qs_prev.values("tinh_thanh__ten_tinh")
            .annotate(revenue=Sum("tong_tien_hang"))
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
        cnt = row["count"]  # Khi có product_id/category_id: số đơn thực có dòng hàng khớp (Count distinct don_hang_id từ ChiTietDonHang) → đúng
        avg = int(rev / cnt) if cnt > 0 else 0
        pct_total = round((rev / float(total_rev) * 100), 1) if total_rev > 0 else 0.0

        prev_rev = int(prev_agg.get(row[province_key], 0) or 0)
        pct_change = calc_percentage_change(rev, prev_rev)
        bar_pct = round((rev / float(max_rev)) * 100, 1)

        result.append({
            "province": tinh_name,
            "order_count": cnt,
            "customer_count": row["customers"],
            "revenue": rev,
            "revenue_raw": rev,
            "revenue_formatted": f"{rev:,}đ".replace(",", "."),
            "avg_per_order": f"{avg:,}đ".replace(",", "."),
            "avg_per_order_raw": avg,
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
    qs = _filter_orders(
        qs, product_id, amount_min, amount_max, category_id, pttt_id, search_kw
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
    if page_size:
        total_pages = max(1, (total_records + page_size - 1) // page_size)
        page = max(1, min(page, total_pages))
        start_idx = (page - 1) * page_size
        page_orders = qs[start_idx: start_idx + page_size]
    else:
        total_pages = 1
        page = 1
        page_orders = qs

    # Tính tổng cộng cho footer
    if product_id or category_id:
        matching_lines = ChiTietDonHang.objects.filter(don_hang__in=qs)
        if product_id:
            matching_lines = matching_lines.filter(bien_the__san_pham_id=product_id)
        if category_id:
            matching_lines = matching_lines.filter(bien_the__san_pham__danh_muc_id=category_id)

        agg = matching_lines.aggregate(
            sum_sl=Coalesce(Sum("so_luong"), Value(0)),
            sum_thanh_tien=Coalesce(Sum("thanh_tien"), Value(Decimal(0))),
        )
        sum_sl = agg["sum_sl"]
        sum_hang_val = agg["sum_thanh_tien"]
        sum_vc_val = Decimal(0)
        sum_tong_val = sum_hang_val
    else:
        summary = qs.aggregate(
            sum_hang=Coalesce(Sum("tong_tien_hang"), Value(Decimal(0))),
            sum_vc=Coalesce(Sum("phi_van_chuyen"), Value(Decimal(0))),
            sum_tong=Coalesce(Sum("tong_thanh_toan"), Value(Decimal(0))),
        )
        sum_sl = ChiTietDonHang.objects.filter(don_hang__in=qs).aggregate(
            total=Coalesce(Sum("so_luong"), Value(0))
        )["total"]
        sum_hang_val = summary["sum_hang"]
        sum_vc_val = summary["sum_vc"]
        sum_tong_val = summary["sum_tong"]

    items = []
    for dh in page_orders:
        lkh = dh.loai_khach_hang_ap_dung
        is_si = is_wholesale(getattr(lkh, "ma_loai_kh", None))

        raw_lines = list(dh.chi_tiet.all())
        if product_id:
            lines = [l for l in raw_lines if l.bien_the and l.bien_the.san_pham_id == product_id]
        elif category_id:
            lines = [l for l in raw_lines if
                     l.bien_the and l.bien_the.san_pham and l.bien_the.san_pham.danh_muc_id == category_id]
        else:
            lines = raw_lines

        if product_id or category_id:
            total_qty = sum(l.so_luong for l in lines)
            subtotal_raw = int(sum(l.thanh_tien for l in lines))
            shipping_fee_raw = 0
            total_payment_raw = subtotal_raw
        else:
            total_qty = sum(l.so_luong for l in lines)
            subtotal_raw = int(dh.tong_tien_hang)
            shipping_fee_raw = int(dh.phi_van_chuyen)
            total_payment_raw = int(dh.tong_thanh_toan)

        refund = 0  # Giữ chỗ chờ tích hợp M4 (hoàn tiền)
        net_rev = subtotal_raw - refund

        items.append({
            "order_code": dh.ma_dh,
            "completion_time": timezone.localtime(dh.thoi_diem_hoan_thanh).strftime("%d/%m/%Y %H:%M") if dh.thoi_diem_hoan_thanh else "-",
            "customer_name": dh.khach_hang.ho_ten if dh.khach_hang else dh.ho_ten_nguoi_nhan,
            "customer_code": dh.khach_hang.ma_kh if dh.khach_hang else "",
            "customer_type": "Khách sỉ" if is_si else "Khách lẻ",
            "is_si": is_si,
            "payment_method": dh.phuong_thuc_thanh_toan.ten_pttt if dh.phuong_thuc_thanh_toan else "Không xác định",
            "quantity": total_qty,
            "quantity_formatted": f"{total_qty:,}".replace(",", "."),
            "subtotal": f"{subtotal_raw:,}đ".replace(",", "."),
            "subtotal_raw": subtotal_raw,
            "shipping_fee": f"{shipping_fee_raw:,}đ".replace(",", "."),
            "shipping_fee_raw": shipping_fee_raw,
            "total_payment": f"{total_payment_raw:,}đ".replace(",", "."),
            "total_payment_raw": total_payment_raw,
            "refund": f"{refund:,}đ".replace(",", "."),
            "net_revenue": f"{net_rev:,}đ".replace(",", "."),
            "line_items": [
                {
                    "product_name": line.bien_the.san_pham.ten_sp if (
                                line.bien_the and line.bien_the.san_pham) else "Sản phẩm",
                    "product_code": line.bien_the.san_pham.ma_sp if (line.bien_the and line.bien_the.san_pham) else "",
                    "variant": (
                        f"{line.bien_the.huong_vi} · {line.bien_the.quy_cach}".strip(" ·")
                        if line.bien_the
                        else ""
                    ),
                    "quantity": line.so_luong,
                    "unit_price": f"{int(line.don_gia):,}đ".replace(",", "."),
                    "amount": f"{int(line.thanh_tien):,}đ".replace(",", "."),
                }
                for line in lines
            ],
        })

    return {
        "items": items,
        "total_records": total_records,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size,
        "summary": {
            "sum_quantity": f"{int(sum_sl):,}".replace(",", "."),
            "sum_subtotal": f"{int(sum_hang_val):,}đ".replace(",", "."),
            "sum_shipping": f"{int(sum_vc_val):,}đ".replace(",", "."),
            "sum_total": f"{int(sum_tong_val):,}đ".replace(",", "."),
            "sum_refund": "0đ",
            "sum_net_revenue": f"{int(sum_hang_val):,}đ".replace(",", "."),
        },
    }