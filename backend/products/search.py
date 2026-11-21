import unicodedata


def normalize_search_text(text):
    """Chuẩn hóa Unicode NFC và đưa về chữ thường (casefold) để khớp chính xác tiếng Việt có dấu."""
    return unicodedata.normalize("NFC", text or "").strip().casefold()


def search_products_by_name(queryset, keyword):
    """
    Tìm sản phẩm theo tên không phân biệt chữ hoa/thường (hỗ trợ đầy đủ tiếng Việt
    có dấu trên SQLite vì LIKE mặc định của SQLite chỉ không phân biệt hoa/thường với ASCII).
    """
    tu_khoa = normalize_search_text(keyword)
    if not tu_khoa:
        return queryset

    ma_sp_khop = [
        ma_sp
        for ma_sp, ten_sp in queryset.values_list("ma_sp", "ten_sp")
        if tu_khoa in normalize_search_text(ten_sp)
    ]

    return queryset.filter(ma_sp__in=ma_sp_khop)


def search_products_for_staff(queryset, keyword):
    """
    Tìm sản phẩm phía nhân viên theo tên sản phẩm, mã sản phẩm hoặc mã vạch biến thể
    không phân biệt chữ hoa/thường (hỗ trợ tiếng Việt có dấu).
    """
    from .models import BienTheSanPham

    tu_khoa = normalize_search_text(keyword)
    if not tu_khoa:
        return queryset

    tat_ca_sp = list(queryset.values_list("ma_sp", "ten_sp"))
    tat_ca_ma_sp = [ma_sp for ma_sp, _ in tat_ca_sp]
    ma_sp_khop = {
        ma_sp
        for ma_sp, ten_sp in tat_ca_sp
        if tu_khoa in normalize_search_text(ten_sp)
        or tu_khoa in normalize_search_text(ma_sp)
    }

    if tat_ca_ma_sp:
        for san_pham_id, barcode in BienTheSanPham.objects.filter(
            san_pham_id__in=tat_ca_ma_sp
        ).values_list("san_pham_id", "barcode"):
            if tu_khoa in normalize_search_text(barcode):
                ma_sp_khop.add(san_pham_id)

    return queryset.filter(ma_sp__in=ma_sp_khop)
