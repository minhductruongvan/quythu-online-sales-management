# File: backend/products/forms.py
import re
import unicodedata

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import BienTheSanPham, DanhMucSanPham, DonViTinh, SanPham


def validate_ma_dinh_danh(value):
    """
    Validator dùng chung cho mã danh mục, mã sản phẩm, mã biến thể (Chương 4 - Validators):
    Chỉ cho phép chữ cái không dấu, chữ số, dấu gạch dưới (_) và dấu gạch ngang (-),
    không chứa khoảng trắng hoặc dấu '/' để tránh lỗi đường dẫn URL và form HTML.
    """
    ma = (value or "").strip()
    if not re.match(r"^[A-Za-z0-9_-]+$", ma):
        raise ValidationError(
            "Mã chỉ được chứa chữ cái không dấu, chữ số, dấu gạch ngang (-) hoặc gạch dưới (_), không chứa khoảng trắng hay dấu '/'."
        )


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Chỉ hiện các danh mục đang hoạt động (ACTIVE) khi thêm sản phẩm mới.
        # Nếu đang sửa sản phẩm mà danh mục cũ của nó đã bị tắt, vẫn giữ lại danh mục đó để form không bị lỗi
        # và gắn nhãn rõ ràng để nhân viên biết danh mục đó đang ngừng áp dụng.
        if self.instance and self.instance.pk:
            self.fields['ma_sp'].disabled = True
            self.fields['ma_sp'].widget.attrs['readonly'] = True
            self.fields['danh_muc'].queryset = DanhMucSanPham.objects.filter(
                Q(trang_thai='ACTIVE') | Q(pk=self.instance.danh_muc_id)
            )
            self.fields['danh_muc'].label_from_instance = (
                lambda obj: f"{obj.ten_dm} (Ngừng áp dụng)" if obj.trang_thai != 'ACTIVE' else obj.ten_dm
            )
        else:
            self.fields['danh_muc'].queryset = DanhMucSanPham.objects.filter(trang_thai='ACTIVE')

    def clean_ma_sp(self):
        if self.instance and self.instance.pk:
            return self.instance.pk
        ma_sp = (self.cleaned_data.get('ma_sp') or '').strip().upper()
        validate_ma_dinh_danh(ma_sp)
        if SanPham.objects.filter(ma_sp__iexact=ma_sp).exists():
            raise forms.ValidationError(f"Mã sản phẩm '{ma_sp}' đã tồn tại trong hệ thống!")
        return ma_sp

    def clean_ten_sp(self):
        ten_sp = (self.cleaned_data.get('ten_sp') or '').strip()
        if not ten_sp:
            raise forms.ValidationError("Tên sản phẩm không được để trống!")
        return ten_sp


# ==============================================================================
# FORM DÀNH CHO USE CASE 3: THÊM VÀ CHỈNH SỬA BIẾN THỂ SẢN PHẨM (M2-UC03)
# ==============================================================================
class BienTheForm(forms.ModelForm):
    # 1. Danh sách hương vị của cửa hàng Quý Thu
    LUA_CHON_HUONG_VI = [
        ('Truyền thống', 'Vị Truyền thống'),
        ('Mè đen', 'Vị Mè đen'),
        ('Gừng', 'Vị Gừng'),
        ('Lá dứa', 'Vị Lá dứa'),
        ('Mè rang', 'Vị Mè rang'),
        ('Cacao', 'Vị Cacao'),
        ('Sầu riêng', 'Vị Sầu riêng'),
        ('Thập cẩm', 'Vị Thập cẩm'),
        ('Đặc biệt', 'Vị Đặc biệt'),
    ]

    # 2. Danh sách quy cách đóng gói của cửa hàng Quý Thu
    LUA_CHON_QUY_CACH = [
        ('120g', 'Gói nhỏ 120g'),
        ('125g', 'Gói nhỏ 125g'),
        ('150g', 'Hộp 150g'),
        ('225g', 'Gói lớn 225g'),
        ('300g', 'Hộp 300g'),
        ('450g', 'Gói đại 450g'),
        ('2 gói', 'Combo 2 gói'),
        ('3 gói', 'Combo 3 gói'),
        ('4 gói', 'Combo 4 gói'),
        ('6 gói', 'Combo 6 gói'),
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

    don_vi_tinh = forms.ModelChoiceField(
        queryset=DonViTinh.objects.all(),
        required=False,
        empty_label='-- Chọn đơn vị tính (mặc định: Gói) --',
        label='Đơn vị tính',
        widget=forms.Select(attrs={'class': 'form-select'}),
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
            'don_vi_tinh',
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
            'gia_ban_si': 'Giá bán sỉ cho đối tác (VNĐ)',
            'so_luong_toi_thieu_si': 'Mức số lượng đặt sỉ tham khảo',
        }

        # Giao diện ô nhập liệu Bootstrap đẹp và dễ nhìn
        widgets = {
            'ma_bien_the': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập mã biến thể (VD: BT005)...'}),
            'barcode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nhập 13 chữ số mã vạch...',
                'maxlength': '13',
                'pattern': '[0-9]{13}',
                'title': 'Mã vạch phải gồm đúng 13 chữ số (0-9)',
            }),
            'gia_ban_le': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: 55000', 'min': '1'}),
            'gia_ban_si': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ví dụ: 45000 (để trống nếu không có)', 'min': '1'}),
            'so_luong_toi_thieu_si': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '2147483647'}),
        }

    def __init__(self, *args, san_pham=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.san_pham = san_pham or (
            self.instance.san_pham if self.instance and self.instance.pk else None
        )
        if self.instance and self.instance.pk:
            self.fields['ma_bien_the'].disabled = True
            self.fields['ma_bien_the'].widget.attrs['readonly'] = True

            # Nếu biến thể đang sửa có hương vị hoặc quy cách lạ (chưa có trong danh sách sẵn),
            # tự thêm vào dropdown để không bị nhảy sang lựa chọn khác khi mở form sửa.
            ds_vi = list(self.fields['huong_vi'].choices)
            cac_vi_hien_co = [ma for ma, _ in ds_vi]
            if self.instance.huong_vi and self.instance.huong_vi not in cac_vi_hien_co:
                ds_vi.append((self.instance.huong_vi, self.instance.huong_vi))
                self.fields['huong_vi'].choices = ds_vi

            ds_qc = list(self.fields['quy_cach'].choices)
            cac_qc_hien_co = [ma for ma, _ in ds_qc]
            if self.instance.quy_cach and self.instance.quy_cach not in cac_qc_hien_co:
                ds_qc.append((self.instance.quy_cach, self.instance.quy_cach))
                self.fields['quy_cach'].choices = ds_qc

    def clean_ma_bien_the(self):
        if self.instance and self.instance.pk:
            return self.instance.pk
        ma_bt = (self.cleaned_data.get('ma_bien_the') or '').strip().upper()
        validate_ma_dinh_danh(ma_bt)
        if BienTheSanPham.objects.filter(ma_bien_the__iexact=ma_bt).exists():
            raise forms.ValidationError(f"Mã biến thể '{ma_bt}' đã tồn tại trong hệ thống!")
        return ma_bt

    def clean_don_vi_tinh(self):
        don_vi_tinh = self.cleaned_data.get('don_vi_tinh')
        if don_vi_tinh is None:
            return (
                DonViTinh.objects.filter(ma_dvt="DVT001").first()
                or DonViTinh.objects.filter(ten_dvt="Gói").first()
            )
        return don_vi_tinh

    # Kiểm tra mã vạch phải đúng 13 chữ số và không trùng biến thể khác (M2-BR06)
    def clean_barcode(self):
        barcode = (self.cleaned_data.get('barcode') or '').strip()

        if not re.match(r'^[0-9]{13}$', barcode):
            raise forms.ValidationError(
                "Mã vạch phải gồm đúng 13 chữ số (từ 0-9), không chứa chữ cái hoặc ký tự đặc biệt!"
            )

        truy_van = BienTheSanPham.objects.filter(barcode=barcode)
        if self.instance and self.instance.pk:
            truy_van = truy_van.exclude(pk=self.instance.pk)
        if truy_van.exists():
            raise forms.ValidationError(
                f"Mã vạch '{barcode}' đã được sử dụng cho một gói bánh khác! Vui lòng kiểm tra lại."
            )

        return barcode

    # Hàm tự động kiểm tra logic nghiệp vụ theo Business Rules M2-BR05, M2-BR07
    def clean(self):
        cleaned_data = super().clean()
        gia_le = cleaned_data.get('gia_ban_le')
        gia_si = cleaned_data.get('gia_ban_si')
        so_luong_si = cleaned_data.get('so_luong_toi_thieu_si')
        huong_vi = cleaned_data.get('huong_vi')
        quy_cach = cleaned_data.get('quy_cach')

        # Quy tắc M2-BR07: Giá bán lẻ phải lớn hơn 0, giá bán sỉ (nếu có) phải lớn hơn 0 và <= giá lẻ
        if gia_le is not None and gia_le <= 0:
            self.add_error('gia_ban_le', 'Giá bán lẻ phải lớn hơn 0!')

        if gia_si is not None and gia_si <= 0:
            self.add_error(
                'gia_ban_si',
                'Giá bán sỉ phải lớn hơn 0 (hoặc để trống nếu không áp dụng giá sỉ)!',
            )

        if gia_le is not None and gia_si is not None:
            if gia_si > gia_le:
                self.add_error('gia_ban_si', 'Giá bán sỉ phải nhỏ hơn hoặc bằng giá bán lẻ!')

        # Mức số lượng tham khảo phải là số nguyên dương.
        if so_luong_si is not None and so_luong_si < 1:
            self.add_error('so_luong_toi_thieu_si', 'Mức số lượng đặt sỉ tham khảo phải từ 1 trở lên!')

        # Quy tắc M2-BR05: Không trùng cặp (Hương vị + Quy cách) trong cùng một sản phẩm
        if self.san_pham and huong_vi and quy_cach:
            truy_van_trung = BienTheSanPham.objects.filter(
                san_pham=self.san_pham,
                huong_vi=huong_vi,
                quy_cach=quy_cach,
            )
            if self.instance and self.instance.pk:
                truy_van_trung = truy_van_trung.exclude(pk=self.instance.pk)
            if truy_van_trung.exists():
                self.add_error(
                    'quy_cach',
                    f'Sản phẩm này đã có biến thể "{huong_vi} - {quy_cach}"! Vui lòng chọn hương vị hoặc quy cách khác.',
                )

        return cleaned_data


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
        barcode = (self.cleaned_data.get('barcode') or '').strip()
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
        min_value=1,
        label="Giá bán lẻ mới (VNĐ)",
        error_messages={
            'min_value': 'Giá bán lẻ phải lớn hơn 0!',
        },
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ví dụ: 55000',
            'min': '1',
            'step': '1'
        })
    )

    # 3. Ô nhập giá bán sỉ mới
    gia_ban_si = forms.DecimalField(
        max_digits=15,
        decimal_places=0,
        required=False,
        min_value=1,
        label="Giá bán sỉ mới (VNĐ)",
        error_messages={
            'min_value': 'Giá bán sỉ phải lớn hơn 0 (hoặc để trống nếu không áp dụng giá sỉ)!',
        },
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ví dụ: 42000',
            'min': '1',
            'step': '1'
        })
    )

    # 4. Mức số lượng tham khảo cho đơn hàng bán sỉ
    so_luong_toi_thieu_si = forms.IntegerField(
        min_value=1,
        max_value=2147483647,
        label="Mức số lượng đặt sỉ tham khảo",
        error_messages={
            'min_value': 'Mức số lượng đặt sỉ tham khảo phải từ 1 trở lên!',
            'max_value': 'Mức số lượng đặt sỉ tham khảo vượt quá giới hạn cho phép!',
        },
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ví dụ: 10',
            'min': '1',
            'max': '2147483647',
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

        # Mức số lượng tham khảo phải từ một gói trở lên.
        if so_luong_toi_thieu is not None and so_luong_toi_thieu < 1:
            self.add_error(
                'so_luong_toi_thieu_si',
                'Mức số lượng đặt sỉ tham khảo phải từ 1 trở lên!'
            )

        return cleaned_data


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['ma_dm'].disabled = True
            self.fields['ma_dm'].widget.attrs['readonly'] = True

    def clean_ma_dm(self):
        if self.instance and self.instance.pk:
            return self.instance.pk
        ma_dm = (self.cleaned_data.get('ma_dm') or '').strip().upper()
        validate_ma_dinh_danh(ma_dm)
        if DanhMucSanPham.objects.filter(ma_dm__iexact=ma_dm).exists():
            raise forms.ValidationError(f"Mã danh mục '{ma_dm}' đã tồn tại trong hệ thống!")
        return ma_dm

    # Kiểm tra tên danh mục không được để trống và không trùng hoa/thường (chuẩn hóa Unicode NFC)
    def clean_ten_dm(self):
        ten_dm = unicodedata.normalize("NFC", (self.cleaned_data.get('ten_dm') or '').strip())
        if not ten_dm:
            raise forms.ValidationError("Tên danh mục không được để trống!")

        ten_chuan = ten_dm.casefold()
        danh_muc_khac = DanhMucSanPham.objects.all()
        if self.instance and self.instance.pk:
            danh_muc_khac = danh_muc_khac.exclude(pk=self.instance.pk)
        for dm in danh_muc_khac:
            if unicodedata.normalize("NFC", (dm.ten_dm or '').strip()).casefold() == ten_chuan:
                raise forms.ValidationError(f"Tên danh mục '{ten_dm}' đã tồn tại!")
        return ten_dm
