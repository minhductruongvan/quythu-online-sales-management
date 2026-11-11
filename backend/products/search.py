def search_products_by_name(queryset, keyword):
    return queryset.filter(ten_sp__icontains=keyword)