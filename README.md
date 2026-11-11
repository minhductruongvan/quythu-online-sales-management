# Quý Thu Online Sales Management

Hệ thống quản lý bán hàng trực tuyến Quý Thu, xây dựng bằng Django.

## Chạy nhanh trên Windows

Yêu cầu máy đã có Python 3.12 và kết nối internet ở lần chạy đầu. Sau khi pull/clone repository, mở thư mục dự án và nhấp đúp `run.bat`. Tập lệnh sẽ tự tạo môi trường Python, cài thư viện cần thiết, tạo cơ sở dữ liệu, nạp dữ liệu/tài khoản mẫu và mở website tại `http://127.0.0.1:8000/`. Không cần chạy lệnh cài đặt, migrate hoặc seed thủ công.

Để chạy từ PyCharm, mở thư mục dự án trong PyCharm rồi chạy `.\run.bat` trong Terminal của PyCharm (hoặc nhấp đúp `run.bat` từ File Explorer). Sau lần chạy đầu, cấu hình **Quy Thu - runserver** cũng dùng được để chạy server trực tiếp. Giữ cửa sổ terminal đang chạy server mở trong khi sử dụng website; nhấn `Ctrl+C` để dừng.

> Python là nền tảng cần thiết để chạy Django. Nếu Python 3.12 chưa có trên máy, cần cài Python một lần; thư viện dự án được tập lệnh tự cài vào `.venv` và không ảnh hưởng Python toàn hệ thống. Kết nối internet cần thiết khi tải thư viện ở lần chạy đầu.

## Chạy kiểm thử

Từ thư mục `backend`:

```powershell
python manage.py test
```

## Tài khoản dùng thử

Các tài khoản mẫu được tự động chuẩn bị khi chạy `run.bat`. Đăng nhập tại `http://127.0.0.1:8000/tai-khoan/dang-nhap/` với mật khẩu mặc định `Quythu123!`. Nếu đặt `M1_DEMO_PASSWORD` trong `.env`, dùng giá trị đó. Tập lệnh làm mới mật khẩu ba tài khoản mẫu mỗi lần khởi động; chỉ dùng trong môi trường phát triển.

Tài khoản: `khachhang@gmail.com` (khách hàng), `nhanvien@gmail.com` (nhân viên) và `quanly@gmail.com` (quản lý).

## Khôi phục mật khẩu qua Gmail

Trang đăng nhập hỗ trợ gửi OTP đặt lại mật khẩu đến email khách hàng. Để gửi email thật bằng Gmail:

1. Bật Xác minh 2 bước cho tài khoản Google và tạo Mật khẩu ứng dụng.
2. Tại thư mục gốc dự án, chạy `Copy-Item .env.example .env`, rồi mở `.env` và điền địa chỉ Gmail cùng Mật khẩu ứng dụng vào `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` và `DEFAULT_FROM_EMAIL`. Không dùng mật khẩu đăng nhập Google thông thường hoặc đưa `.env` lên Git.
3. Khởi động lại Django server để nạp cấu hình.

Khi chưa cấu hình SMTP trong môi trường phát triển, email và OTP được in ra terminal đang chạy server. OTP hết hạn sau 5 phút, chỉ dùng một lần; yêu cầu gửi lại bị giới hạn theo thời gian. SMS Viettel chưa được bật.

## Luồng sử dụng

- Tài khoản đăng ký mới mặc định là khách lẻ; nhân viên hoặc quản lý phân loại khách sỉ sau khi xác minh. Giá sỉ chỉ áp dụng khi đạt số lượng tối thiểu của từng biến thể.
- Khách hàng có thể xem catalog, đăng ký/đăng nhập, quản lý địa chỉ, thêm biến thể vào giỏ, đặt hàng COD hoặc chuyển khoản giả lập, theo dõi đơn và gửi yêu cầu hậu mãi.
- Nhân viên xử lý đơn theo trạng thái, quản lý catalog, làm việc với yêu cầu hậu mãi và xem báo cáo; quản lý có các chức năng đó cùng phân quyền nhân viên và dashboard quản trị.
- Từ cửa hàng, khách chọn sản phẩm → giỏ hàng → thanh toán → theo dõi đơn. Nhân viên xử lý đơn trong `/don-hang/`; khách tìm đơn và hỗ trợ trong khu vực tài khoản.
- Nghiệp vụ và dữ liệu được lưu trong SQLite qua các model/migration Django hiện có; giao diện gọi API cùng dịch vụ nghiệp vụ thay vì tự tính giá hoặc tự đổi trạng thái.

`seed_demo_catalog` thêm 10 sản phẩm với nhiều quy cách và hương vị; `seed_demo_sales` tạo thêm 8 hồ sơ khách hàng, địa chỉ, 10 đơn hàng ở các trạng thái khác nhau, lịch sử trạng thái minh họa và một yêu cầu hủy mẫu gắn với tài khoản khách hàng mẫu. Các lệnh chỉ chạy khi `DEBUG=True`, có thể chạy lặp lại và không ghi đè các bản ghi đã tồn tại. Người dùng mới có thể tự đăng ký trực tiếp trên website.
