# File: backend/products/forms.py
from django import forms
from .models import SanPham, BienTheSanPham


# ==============================================================================
# FORM DÀNH CHO USE CASE 2: QUẢN LÝ SẢN PHẨM GỐC
# ==============================================================================
class SanPhamForm(forms.ModelForm):
    # Danh sách 2 trạng thái kinh doanh
    DANH_SACH_TRANG_THAI = [
        ('ACTIVE', 'Đang kinh doanh (ACTIVE - Khách hàng xem được)'),
        ('INACTIVE', 'Ngừng kinh doanh (INACTIVE - Tạm ẩn khỏi khách hàng)'),
    ]

    # Ô chọn trạng thái
    trang_thai = forms.ChoiceField(
        choices=DANH_SACH_TRANG_THAI,
        label='Trạng thái kinh doanh',
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='ACTIVE',
    )

    class Meta:
        model = SanPham
        fields = ['ma_sp', 'danh_muc', 'ten_sp', 'mo_ta', 'trang_thai']
        labels = {
            'ma_sp': 'Mã sản phẩm (Ví dụ: SP002)',
            'danh_muc': 'Chọn danh mục',
            'ten_sp': 'Tên sản phẩm',
            'mo_ta': 'Mô tả sản phẩm',
        }
        widgets = {
            'ma_sp': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập mã SP...'}),
            'danh_muc': forms.Select(attrs={'class': 'form-select'}),
            'ten_sp': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập tên sản phẩm...'}),
            'mo_ta': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Nhập mô tả chi tiết...'}),
        }


# ==============================================================================
# FORM DÀNH CHO USE CASE 3: THÊM VÀ CHỈNH SỬA BIẾN THỂ SẢN PHẨM (M2-UC03)
# ==============================================================================
class BienTheForm(forms.ModelForm):
    # 1. Danh sách 4 hương vị theo khảo sát Quý Thu (M2-BR04)
    LUA_CHON_HUONG_VI = [
        ('Truyền thống', 'Vị Truyền thống'),
        ('Mè đen', 'Vị Mè đen'),
        ('Gừng', 'Vị Gừng'),
        ('Lá dứa', 'Vị Lá dứa'),
    ]

    # 2. Danh sách các quy cách khối lượng theo khảo sát Quý Thu (M2-BR04)
    LUA_CHON_QUY_CACH = [
        ('120g', 'Gói nhỏ 120g'),
        ('125g', 'Gói nhỏ 125g'),
        ('150g', 'Hộp 150g'),
        ('225g', 'Gói lớn 225g'),
    ]

    # 3. Trạng thái kinh doanh của biến thể (M2-BR09)
    LUA_CHON_TRANG_THAI = [
        ('ACTIVE', 'Đang bán (Khách hàng có thể đặt)'),
        ('INACTIVE', 'Ngừng bán (Ẩn biến thể này)'),
    ]

    # 4. Tạo các ô chọn Dropdown thân thiện trên giao diện
    huong_vi = forms.ChoiceField(
        choices=LUA_CHON_HUONG_VI,
        label='Hương vị bánh',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    quy_cach = forms.ChoiceField(
        choices=LUA_CHON_QUY_CACH,
        label='Quy cách khối lượng đóng gói',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    trang_thai = forms.ChoiceField(
        choices=LUA_CHON_TRANG_THAI,
        label='Trạng thái bán của gói bánh',
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='ACTIVE'
    )

    class Meta:
        model = BienTheSanPham
        # Danh sách các trường dữ liệu mà nhân viên sẽ nhập
        fields = [
            'ma_bien_the',
            'huong_vi',
            'quy_cach',
            'barcode',
            'gia_ban_le',
            'gia_ban_si',
            'so_luong_toi_thieu_si',
            'trang_thai'
        ]

        # Đặt nhãn hiển thị tiếng Việt rõ ràng
        labels = {
            'ma_bien_the': 'Mã biến thể (Ví dụ: BT001, BT002)',
            'barcode': 'Mã vạch bao bì (EAN-13 gồm 13 số)',
            'gia_ban_le': 'Giá bán lẻ niêm yết (VNĐ)',
            'gia_ban_si': 'Giá bán sỉ cho đại lý (VNĐ)',
            'so_luong_toi_thieu_si': 'Số lượng gói tối thiểu để được giá sỉ',
        }

        # Giao diện ô nhập liệu Bootstrap đẹp và dễ nhìn
        widgets = {
            'ma_bien_the': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập mã biến thể (VD: BT005)...'}),
            'barcode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập 13 chữ số mã vạch...'}),
            'gia_ban_le': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: 55000', 'min': '0'}),
            'gia_ban_si': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: 45000', 'min': '0'}),
            'so_luong_toi_thieu_si': forms.NumberInput(attrs={'class': 'form-control', 'value': 10, 'min': '1'}),
        }

    # Hàm tự động kiểm tra logic nghiệp vụ theo Business Rules M2-BR07
    def clean(self):
        cleaned_data = super().clean()
        gia_le = cleaned_data.get('gia_ban_le')
        gia_si = cleaned_data.get('gia_ban_si')
        so_luong_si = cleaned_data.get('so_luong_toi_thieu_si')

        # Quy tắc M2-BR07: Giá bán không được là số âm
        if gia_le is not None and gia_le < 0:
            self.add_error('gia_ban_le', 'Giá bán lẻ không được là số âm!')

        if gia_si is not None and gia_si < 0:
            self.add_error('gia_ban_si', 'Giá bán sỉ không được là số âm!')

        # Quy tắc M2-BR07: Giá bán sỉ phải nhỏ hơn hoặc bằng giá bán lẻ
        if gia_le is not None and gia_si is not None:
            if gia_si > gia_le:
                self.add_error('gia_ban_si', 'Quy tắc M2-BR07: Giá bán sỉ phải nhỏ hơn hoặc bằng giá bán lẻ!')

        # Quy tắc M2-BR07: Số lượng tối thiểu hưởng giá sỉ phải từ 1 trở lên
        if so_luong_si is not None and so_luong_si < 1:
            self.add_error('so_luong_toi_thieu_si', 'Số lượng tối thiểu hưởng giá sỉ phải là số nguyên từ 1 trở lên!')

        return cleaned_data

import re  # Thư viện dùng để kiểm tra đúng 13 chữ số


# ==============================================================================
# FORM DÀNH CHO USE CASE 4: QUẢN LÝ VÀ CẬP NHẬT MÃ VẠCH (M2-UC04)
# ==============================================================================
class CapNhatMaVachForm(forms.Form):
    # 1. Ẩn mã biến thể đi để biết đang sửa mã vạch cho gói bánh nào
    ma_bien_the = forms.CharField(widget=forms.HiddenInput())

    # 2. Ô nhập mã vạch EAN-13
    barcode = forms.CharField(
        max_length=13,
        label="Mã vạch EAN-13 (13 chữ số)",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ví dụ: 8938501230018',
            'maxlength': '13'
        })
    )

    # 3. Hàm tự động kiểm tra tính hợp lệ của mã vạch
    def clean_barcode(self):
        # Lấy mã vạch nhân viên nhập vào, cắt bỏ khoảng trắng thừa
        barcode = self.cleaned_data.get('barcode', '').strip()
        ma_bien_the = self.cleaned_data.get('ma_bien_the')

        # KIỂM TRA 1 (Ngoại lệ E2): Phải là đúng 13 chữ số từ 0 đến 9
        if not re.match(r'^[0-9]{13}$', barcode):
            raise forms.ValidationError(
                "Lỗi định dạng: Mã vạch phải gồm đúng 13 chữ số (từ 0-9), không chứa chữ cái hoặc ký tự đặc biệt!"
            )

        # KIỂM TRA 2 (Quy tắc M2-BR06 & Ngoại lệ E3): Không được trùng với biến thể khác
        # Tìm xem đã có gói bánh nào khác dùng mã vạch này chưa (loại trừ chính gói đang sửa)
        da_trung_ma = BienTheSanPham.objects.filter(barcode=barcode).exclude(ma_bien_the=ma_bien_the).exists()
        if da_trung_ma:
            raise forms.ValidationError(
                f"Mã vạch '{barcode}' đã được sử dụng cho một gói bánh khác! Vui lòng kiểm tra lại."
            )

        return barcode

# ==============================================================================
# FORM DÀNH CHO USE CASE 5: THIẾT LẬP VÀ CẬP NHẬT GIÁ BÁN (M2-UC05)
# ==============================================================================
class CapNhatGiaForm(forms.Form):
    # 1. Ẩn mã biến thể để biết đang sửa giá cho gói bánh nào
    ma_bien_the = forms.CharField(widget=forms.HiddenInput())

    # 2. Ô nhập giá bán lẻ mới
    gia_ban_le = forms.DecimalField(
        max_digits=15,
        decimal_places=0,
        min_value=0,
        label="Giá bán lẻ mới (VNĐ)",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ví dụ: 55000',
            'min': '0',
            'step': '1000'
        })
    )

    # 3. Ô nhập giá bán sỉ mới
    gia_ban_si = forms.DecimalField(
        max_digits=15,
        decimal_places=0,
        min_value=0,
        label="Giá bán sỉ mới (VNĐ)",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ví dụ: 42000',
            'min': '0',
            'step': '1000'
        })
    )

    # 4. Ô nhập số lượng tối thiểu để được giá sỉ
    so_luong_toi_thieu_si = forms.IntegerField(
        min_value=1,
        label="Số lượng tối thiểu hưởng giá sỉ",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ví dụ: 10',
            'min': '1'
        })
    )

    # 5. Hàm kiểm tra quy tắc giá M2-BR07 (Ngoại lệ E2)
    def clean(self):
        cleaned_data = super().clean()
        gia_le = cleaned_data.get('gia_ban_le')
        gia_si = cleaned_data.get('gia_ban_si')
        so_luong_toi_thieu = cleaned_data.get('so_luong_toi_thieu_si')

        # Kiểm tra quy tắc M2-BR07: Giá sỉ phải nhỏ hơn hoặc bằng giá lẻ
        if gia_le is not None and gia_si is not None:
            if gia_si > gia_le:
                self.add_error(
                    'gia_ban_si',
                    'Giá bán sỉ không được lớn hơn giá bán lẻ!'
                )

        # Kiểm tra quy tắc M2-BR07: Số lượng tối thiểu >= 1
        if so_luong_toi_thieu is not None and so_luong_toi_thieu < 1:
            self.add_error(
                'so_luong_toi_thieu_si',
                'Số lượng tối thiểu hưởng giá sỉ phải từ 1 gói trở lên!'
            )

        return cleaned_data

from .models import HinhAnhSanPham


# ==============================================================================
# FORM DÀNH CHO USE CASE 6: QUẢN LÝ HÌNH ẢNH SẢN PHẨM (M2-UC06)
# ==============================================================================
class HinhAnhForm(forms.ModelForm):
    class Meta:
        model = HinhAnhSanPham
        fields = ['duong_dan', 'anh_chinh']
        labels = {
            'duong_dan': 'Đường dẫn hình ảnh (URL)',
            'anh_chinh': 'Đặt làm ảnh đại diện chính của sản phẩm',
        }
        widgets = {
            'duong_dan': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Dán link ảnh (https://...) hoặc đường dẫn ảnh vào đây...'
            }),
            'anh_chinh': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    # Kiểm tra đường dẫn ảnh có hợp lệ không
    def clean_duong_dan(self):
        duong_dan = self.cleaned_data.get('duong_dan', '').strip()
        if not duong_dan:
            raise forms.ValidationError("Đường dẫn ảnh không được để trống!")
        return duong_dan

from .models import DanhMucSanPham


# ==============================================================================
# FORM DÀNH CHO USE CASE 9: QUẢN LÝ DANH MỤC SẢN PHẨM (M2-UC09)
# ==============================================================================
class DanhMucForm(forms.ModelForm):
    # Trạng thái danh mục
    DANH_SACH_TRANG_THAI = [
        ('ACTIVE', 'Đang áp dụng (Cho phép gán sản phẩm)'),
        ('INACTIVE', 'Ngừng áp dụng (Tạm khóa danh mục này)'),
    ]

    trang_thai = forms.ChoiceField(
        choices=DANH_SACH_TRANG_THAI,
        label='Trạng thái hoạt động',
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='ACTIVE'
    )

    class Meta:
        model = DanhMucSanPham
        fields = ['ma_dm', 'ten_dm', 'mo_ta', 'trang_thai']
        labels = {
            'ma_dm': 'Mã danh mục (Ví dụ: DM002)',
            'ten_dm': 'Tên danh mục',
            'mo_ta': 'Mô tả tóm tắt về nhóm sản phẩm này',
        }
        widgets = {
            'ma_dm': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập mã DM...'}),
            'ten_dm': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: Quà biếu đặc sản...'}),
            'mo_ta': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Mô tả nhóm danh mục...'}),
        }

    # Kiểm tra tên danh mục không được để trống
    def clean_ten_dm(self):
        ten_dm = self.cleaned_data.get('ten_dm', '').strip()
        if not ten_dm:
            raise forms.ValidationError("Tên danh mục không được để trống!")
        return ten_dm