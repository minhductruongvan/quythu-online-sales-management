from django.db import connection
from django.test import TestCase


class DatabaseSchemaNamingTests(TestCase):
    def test_source_schema_table_names_exist(self):
        source_tables = {
            "NHANVIEN",
            "LOAIKHACHHANG",
            "KHACHHANG",
            "DIACHIKH",
            "LICHSUTHAYDOI_KH",
            "DANHMUCSANPHAM",
            "DONVITINH",
            "SANPHAM",
            "BIENTHE_SANPHAM",
            "HINHANH_SANPHAM",
            "TINH_THANH",
            "GIOHANG",
            "DONHANG",
            "CT_DONHANG",
            "LICHSUTRANGTHAI_DH",
            "PHUONGTHUCTHANHTOAN",
            "GIAODICH_THANHTOAN",
            "GIAOHANG",
            "THONGBAO_DONHANG",
            "DANHMUC_NGUYENNHAN",
            "LICHSU_NGUYENNHAN",
            "YEUCAU_HUYDON",
            "YEUCAU_DOITRA",
            "CT_YEUCAU_DOITRA",
            "ANH_DOITRA",
            "GIAODICH_HOANTIEN",
            "LICHSU_HAUMAI",
            "NHATKY_XUAT_BAOCAO",
        }

        self.assertTrue(source_tables.issubset(set(connection.introspection.table_names())))
