
document.addEventListener("DOMContentLoaded", function () {
    const tbody = document.getElementById("ordersTableBody");

    const search = document.getElementById("orderSearch");
    const payment = document.getElementById("paymentFilter");
    const channel = document.getElementById("channelFilter");
    const fromDate = document.getElementById("fromDate");
    const toDate = document.getElementById("toDate");

    const resultCount = document.getElementById("resultCount");
    const paginationCount = document.getElementById("paginationCount");
    const noResult = document.getElementById("noFilterResult");

    const prevPage = document.getElementById("prevPage");
    const nextPage = document.getElementById("nextPage");
    const pageInfo = document.getElementById("pageInfo");

    const tabs = document.querySelectorAll(".status-tab");

    const pageSize = 5;
    let currentPage = 1;
    let activeStatus = "all";

    // 1. TẠO DỮ LIỆU MẪU NẾU DATABASE CHƯA CÓ ĐƠN HÀNG
    function createDemoOrders() {
        if (tbody.querySelector(".order-row")) return;

        const demoOrders = [
            ["DH001", "KH001", "0905123456", "2026-11-01", "Website", "1.500.000", "Đã thanh toán", "Hoàn thành"],
            ["DH002", "KH002", "0912345678", "2026-11-02", "Facebook", "850.000", "Chưa thanh toán", "Chờ xác nhận"],
            ["DH003", "KH003", "0934567890", "2026-11-02", "TikTok", "2.200.000", "Đã thanh toán", "Đã xác nhận"],
            ["DH004", "KH004", "0978123456", "2026-11-03", "Trực tiếp", "650.000", "Chưa thanh toán", "Đang chuẩn bị hàng"],
            ["DH005", "KH005", "0909876543", "2026-11-03", "Website", "3.100.000", "Đã thanh toán", "Đang giao"],
            ["DH006", "KH006", "0987654321", "2026-11-04", "Facebook", "920.000", "Đã hoàn tiền", "Giao thất bại"],
            ["DH007", "KH007", "0961234567", "2026-11-04", "TikTok", "1.800.000", "Đã thanh toán", "Hoàn thành"],
            ["DH008", "KH008", "0945678123", "2026-11-05", "Website", "450.000", "Chưa thanh toán", "Chờ xác nhận"]
        ];

        const emptyRow = tbody.querySelector(".empty-orders");
        if (emptyRow) emptyRow.closest("tr").remove();

        demoOrders.forEach(order => {
            const row = document.createElement("tr");
            row.className = "order-row";

            row.dataset.status = order[7];
            row.dataset.payment = order[6];
            row.dataset.channel = order[4];
            row.dataset.date = order[3];

            const paymentClass =
                order[6] === "Đã thanh toán" ? "paid" :
                order[6] === "Đã hoàn tiền" ? "refunded" : "unpaid";

            const statusClass =
                order[7] === "Hoàn thành" ? "completed" :
                order[7] === "Đang giao" ? "shipping" :
                order[7] === "Giao thất bại" ? "failed" : "pending";

            row.innerHTML = `
                <td><input type="checkbox" class="row-checkbox"></td>
                <td><strong class="order-code"></strong></td>
                <td>
                    <div class="customer-cell">
                        <strong></strong>
                        <span></span>
                    </div>
                </td>
                <td></td>
                <td></td>
                <td class="amount-cell"></td>
                <td><span class="payment-label ${paymentClass}"></span></td>
                <td><span class="order-status ${statusClass}"></span></td>
                <td><button type="button" class="btn-detail">Chi tiết →</button></td>
            `;

            const cells = row.querySelectorAll("td");
            cells[1].querySelector("strong").textContent = order[0];
            cells[2].querySelector("strong").textContent = order[1];
            cells[2].querySelector("span").textContent = order[2];
            cells[3].textContent = order[3];
            cells[4].textContent = order[4];
            cells[5].textContent = order[5] + " ₫";
            cells[6].querySelector("span").textContent = order[6];
            cells[7].querySelector("span").textContent = order[7];

            tbody.appendChild(row);
        });
    }

    createDemoOrders();

    let rows = [...tbody.querySelectorAll(".order-row")];

    // 2. LỌC VÀ PHÂN TRANG
    function filterOrders() {
        const keyword = search.value.trim().toLowerCase();

        const filteredRows = rows.filter(row => {
            const text = row.innerText.toLowerCase();
            const date = row.dataset.date || "";

            return (
                text.includes(keyword) &&
                (activeStatus === "all" || row.dataset.status === activeStatus) &&
                (!payment.value || row.dataset.payment === payment.value) &&
                (!channel.value || row.dataset.channel === channel.value) &&
                (!fromDate.value || date >= fromDate.value) &&
                (!toDate.value || date <= toDate.value)
            );
        });

        const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
        currentPage = Math.min(currentPage, totalPages);

        rows.forEach(row => {
            row.hidden = true;
        });

        const start = (currentPage - 1) * pageSize;
        const currentRows = filteredRows.slice(start, start + pageSize);

        currentRows.forEach(row => {
            row.hidden = false;
        });

        resultCount.textContent = filteredRows.length;
        paginationCount.textContent = currentRows.length;

        noResult.hidden = filteredRows.length !== 0;

        pageInfo.textContent = `Trang ${currentPage}/${totalPages}`;
        prevPage.disabled = currentPage <= 1;
        nextPage.disabled = currentPage >= totalPages;

        document.getElementById("selectAll").checked = false;
        document.querySelectorAll(".row-checkbox").forEach(box => {
            box.checked = false;
        });

        return filteredRows;
    }

    // 3. TÌM KIẾM
    search.addEventListener("input", function () {
        currentPage = 1;
        filterOrders();
    });

    // 4. LỌC TRẠNG THÁI
    tabs.forEach(tab => {
        tab.addEventListener("click", function () {
            tabs.forEach(item => item.classList.remove("active"));
            this.classList.add("active");

            activeStatus = this.dataset.filter;
            currentPage = 1;
            filterOrders();
        });
    });

    // 5. LỌC NÂNG CAO
    document.getElementById("applyFilter").addEventListener("click", function () {
        if (fromDate.value && toDate.value && fromDate.value > toDate.value) {
            alert("Ngày bắt đầu không được lớn hơn ngày kết thúc.");
            return;
        }

        currentPage = 1;
        filterOrders();
    });

    // 6. XÓA BỘ LỌC
    document.getElementById("resetFilter").addEventListener("click", function () {
        search.value = "";
        payment.value = "";
        channel.value = "";
        fromDate.value = "";
        toDate.value = "";

        activeStatus = "all";
        currentPage = 1;

        tabs.forEach(item => item.classList.remove("active"));
        document.querySelector('[data-filter="all"]').classList.add("active");

        filterOrders();
    });

    // 7. PHÂN TRANG
    prevPage.addEventListener("click", function () {
        if (currentPage > 1) {
            currentPage--;
            filterOrders();
        }
    });

    nextPage.addEventListener("click", function () {
        currentPage++;
        filterOrders();
    });

    // 8. CHỌN TẤT CẢ
    document.getElementById("selectAll").addEventListener("change", function () {
        rows.filter(row => !row.hidden).forEach(row => {
            row.querySelector(".row-checkbox").checked = this.checked;
        });
    });

    // 9. XEM CHI TIẾT ĐƠN HÀNG
const detailModal = new bootstrap.Modal(
    document.getElementById("orderDetailModal")
);

tbody.addEventListener("click", function (event) {
    const button = event.target.closest(".btn-detail");
    if (!button) return;

    const row = button.closest(".order-row");
    if (!row) return;

    const cells = row.querySelectorAll("td");

    document.getElementById("detailCode").textContent =
        cells[1].innerText.trim();

    document.getElementById("detailCustomer").textContent =
        cells[2].querySelector("strong").textContent;

    document.getElementById("detailPhone").textContent =
        cells[2].querySelector("span").textContent;

    document.getElementById("detailDate").textContent =
        cells[3].innerText.trim();

    document.getElementById("detailChannel").textContent =
        cells[4].innerText.trim();

    document.getElementById("detailTotal").textContent =
        cells[5].innerText.trim();

    document.getElementById("detailPayment").textContent =
        cells[6].innerText.trim();

    document.getElementById("detailStatus").textContent =
        cells[7].innerText.trim();

    detailModal.show();
});

    // 10. XUẤT CSV
    document.getElementById("exportOrdersBtn").addEventListener("click", function () {
        const visibleRows = rows.filter(row => !row.hidden);

        if (!visibleRows.length) {
            alert("Không có đơn hàng để xuất.");
            return;
        }

        const data = [
            ["Mã đơn hàng", "Khách hàng", "Ngày đặt", "Kênh bán",
             "Tổng tiền", "Thanh toán", "Trạng thái"]
        ];

        visibleRows.forEach(row => {
            const cells = row.querySelectorAll("td");
            data.push([
                cells[1].innerText.trim(),
                cells[2].innerText.trim().replace(/\s+/g, " "),
                cells[3].innerText.trim(),
                cells[4].innerText.trim(),
                cells[5].innerText.trim(),
                cells[6].innerText.trim(),
                cells[7].innerText.trim()
            ]);
        });

        const csv = "\uFEFF" + data.map(line =>
            line.map(value => `"${value.replace(/"/g, '""')}"`).join(",")
        ).join("\r\n");

        const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");

        link.href = url;
        link.download = "danh-sach-don-hang.csv";
        link.click();

        URL.revokeObjectURL(url);
    });

    // 11. MỞ FORM TẠO ĐƠN HÀNG
const createModal = new bootstrap.Modal(
    document.getElementById("createOrderModal")
);

document.getElementById("createOrderBtn").addEventListener("click", function () {
    document.getElementById("createOrderForm").reset();
    createModal.show();
});

    filterOrders();
})

// 12. KIỂM TRA FORM
document.getElementById("createOrderForm").addEventListener(
    "submit",
    function (event) {
        event.preventDefault();

        if (!this.reportValidity()) return;

        const customer = document.getElementById("newCustomer").value.trim();
        const phone = document.getElementById("newPhone").value.trim();
        const channel = document.getElementById("newChannel").value;
        const payment = document.getElementById("newPayment").value;
        const total = Number(document.getElementById("newTotal").value);

        if (!total || total <= 0) {
            alert("Tổng tiền phải lớn hơn 0.");
            return;
        }

        alert(
            "Thông tin hợp lệ!\n\n" +
            "Khách hàng: " + customer + "\n" +
            "Số điện thoại: " + phone + "\n" +
            "Kênh bán: " + channel + "\n" +
            "Thanh toán: " + payment + "\n" +
            "Tổng tiền: " + total.toLocaleString("vi-VN") + " VNĐ\n\n" +
            "Đây là bước kiểm tra giao diện. Đơn hàng chưa được lưu."
        );

        createModal.hide();
    }
);