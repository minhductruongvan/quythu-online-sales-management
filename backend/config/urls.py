from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Khi người dùng vào trang web thì dẫn sang app products
    path('products/', include('products.urls')),
    path('', include('products.urls')),  # Vào thẳng trang chủ là thấy sản phẩm
]