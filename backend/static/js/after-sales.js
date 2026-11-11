(() => {
    const csrf = () => document.querySelector('[name="csrfmiddlewaretoken"]')?.value || "";
    const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[char]);
    const formatDate = value => {
        if (!value) return "—";
        const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value));
        const parsed = dateOnly
            ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]))
            : new Date(value);
        return Number.isNaN(parsed.getTime()) ? "—" : new Intl.DateTimeFormat("vi-VN", {
            day: "2-digit", month: "2-digit", year: "numeric",
            hour: "2-digit", minute: "2-digit"
        }).format(parsed);
    };
    const formatMoney = value => value === null || value === undefined
        ? "—"
        : `${new Intl.NumberFormat("vi-VN").format(Number(value))} ₫`;
    const labels = {
        ma_yc_huy: "Mã yêu cầu",
        don_hang: "Mã đơn hàng",
        khach_hang: "Khách hàng",
        ten_trang_thai: "Trạng thái",
        trang_thai_don: "Trạng thái đơn hàng",
        trang_thai_thanh_toan: "Trạng thái thanh toán",
        qua_han_xu_ly: "Quá hạn xử lý",
        ho_ten_nguoi_nhan: "Người nhận",
        dia_chi_giao_hang: "Địa chỉ giao",
        so_lan_giao_lai: "Số lần giao lại",
        loai_yeu_cau: "Loại yêu cầu",
        ten_loai_yeu_cau: "Loại yêu cầu",
        ma_yeu_cau: "Mã yêu cầu",
        cap_nhat_cuoi: "Cập nhật lần cuối",
        thoi_diem: "Thời điểm",
        moc: "Mốc xử lý",
        tac_nhan: "Người thực hiện",
        ten_tac_nhan: "Người thực hiện",
        ghi_chu: "Ghi chú",
        ma_thong_bao: "Mã thông báo",
        tieu_de: "Tiêu đề",
        noi_dung: "Nội dung",
        da_doc: "Đã đọc",
        ma_dh: "Mã đơn hàng",
        ma_giao_dich_hoan: "Mã giao dịch hoàn",
        ma_hoan_tien: "Mã yêu cầu hoàn tiền",
        ma_nguyen_nhan: "Mã nguyên nhân",
        ma_van_don: "Mã vận đơn",
        so_tai_khoan: "Số tài khoản",
        ten_nguoi_nhan_tien: "Tên người nhận tiền",
        ngan_hang_nhan: "Ngân hàng nhận tiền",
        dia_chi_kho: "Địa chỉ kho hoàn về",
        ten_nguoi_nhan_moi: "Người nhận mới",
        sdt_nguoi_nhan_moi: "Số điện thoại người nhận mới",
        dia_chi_giao_moi: "Địa chỉ giao mới",
        ten_nguyen_nhan: "Nguyên nhân",
        ten_loai_xu_ly: "Loại xử lý",
        thoi_diem_gui: "Thời điểm gửi",
        thoi_diem_tao: "Thời điểm tạo",
        thoi_diem_xu_ly: "Thời điểm xử lý",
        thoi_diem_hoan: "Thời điểm hoàn tiền",
        so_tien_de_xuat: "Số tiền đề xuất",
        so_tien_hoan: "Số tiền hoàn",
        so_tien_da_thanh_toan: "Số tiền đã thanh toán",
        tai_khoan_nhan: "Tài khoản nhận tiền",
        ghi_chu_khach: "Ghi chú của khách",
        ghi_chu_noi_bo: "Ghi chú xử lý",
        phan_hoi_khach: "Phản hồi khách hàng",
        ly_do_tu_choi: "Lý do từ chối",
        ly_do_that_bai: "Lý do thất bại",
        ngay_giao_lai_du_kien: "Ngày giao lại dự kiến"
    };
    const sectionLabels = {
        cancel: "Yêu cầu hủy đơn",
        delivery: "Giao hàng thất bại",
        exchange: "Yêu cầu đổi trả",
        refund: "Yêu cầu hoàn tiền",
        reasons: "Danh mục nguyên nhân",
        history: "Lịch sử hậu mãi",
        stats: "Thống kê hậu mãi",
        notifications: "Thông báo"
    };
    const statusLabels = {
        CHO_XAC_NHAN: "Chờ xác nhận",
        CHUA_THANH_TOAN: "Chưa thanh toán",
        CHO_XU_LY: "Chờ xử lý",
        CHO_HOAN: "Chờ hoàn tiền",
        DA_NHAN_HANG: "Đã nhận hàng",
        DA_HOAN_TAT: "Đã hoàn tất",
        TU_CHOI: "Đã từ chối",
        HUY: "Đã hủy",
        HUY_DON: "Hủy đơn",
        DOI_TRA: "Đổi trả",
        GIAO_THAT_BAI: "Giao hàng thất bại"
    };
    const humanLabel = key => labels[key] || key.replace(/_/g, " ");
    const humanValue = value => statusLabels[value]
        || String(value).replace(/_/g, " ").toLocaleLowerCase("vi-VN")
            .replace(/^./, character => character.toLocaleUpperCase("vi-VN"));
    const renderFields = data => {
        if (!data || typeof data !== "object" || Array.isArray(data)) return "";
        const displayFields = {
            trang_thai: "ten_trang_thai",
            loai_yeu_cau: "ten_loai_yeu_cau",
            loai_xu_ly: "ten_loai_xu_ly",
            huong_xu_ly: "ten_huong_xu_ly",
            ket_qua_giao: "ten_ket_qua_giao"
        };
        return `<dl class="after-sales-details">${Object.entries(data)
            .filter(([key, value]) => value !== null && value !== ""
                && typeof value !== "object"
                && key !== "tai_khoan_hoan"
                && key !== "tai_khoan_nhan"
                && !(displayFields[key] && data[displayFields[key]]))
            .map(([key, value]) => {
                let display = value;
                if (typeof value === "boolean") display = value ? "Có" : "Không";
                else if (key.startsWith("thoi_diem_") || key.startsWith("ngay_") || key === "cap_nhat_cuoi") display = formatDate(value);
                else if (key.startsWith("so_tien_") || key === "gia_tri_don") display = formatMoney(value);
                else if (["trang_thai", "trang_thai_don", "trang_thai_thanh_toan", "loai_xu_ly", "huong_xu_ly", "ket_qua_giao", "loai_yeu_cau", "tac_nhan"].includes(key)) {
                    display = humanValue(value);
                }
                return `<div><dt>${esc(humanLabel(key))}</dt><dd>${esc(display)}</dd></div>`;
            }).join("")}</dl>`;
    };
    const renderRefundAccount = account => {
        if (!account || typeof account !== "object") return "";
        const fields = [
            ["Tên người nhận", account.ten_nguoi_nhan_tien],
            ["Số tài khoản", account.so_tai_khoan],
            ["Ngân hàng", account.ngan_hang_nhan],
            ["Thông tin tài khoản", account.thong_tin_tai_khoan],
        ].filter(([, value]) => value);
        return fields.length ? `<dl class="after-sales-details">${fields.map(([label, value]) =>
            `<div><dt>${label}</dt><dd>${esc(value)}</dd></div>`).join("")}</dl>` : "";
    };
    const renderStats = data => {
        const summary = Array.isArray(data?.the_tong_hop) ? data.the_tong_hop : [];
        const details = Array.isArray(data?.chi_tiet) ? data.chi_tiet : [];
        return `<h2>Thống kê hậu mãi</h2>
            <form class="module-inline-form" data-stats-filter>
                <label>Từ ngày<input type="date" name="tu_ngay" value="${esc(data?.tu_ngay || "")}"></label>
                <label>Đến ngày<input type="date" name="den_ngay" value="${esc(data?.den_ngay || "")}"></label>
                <button class="module-button secondary" type="submit">Lọc thống kê</button>
            </form>
            <p class="module-muted">Thời gian: ${esc(data?.tu_ngay || "—")} – ${esc(data?.den_ngay || "—")}</p>
            ${data?.thong_bao ? `<p class="module-alert">${esc(data.thong_bao)}</p>` : ""}
            <div class="module-grid">${summary.map(item => `<article class="module-panel">
                <span class="module-eyebrow">${esc(item.ten_loai_xu_ly)}</span>
                <h3>${Number(item.tong || 0)} yêu cầu</h3>
                <p class="module-muted">Kỳ trước: ${Number(item.ky_truoc || 0)} ·
                    Biến động: ${item.thay_doi_phan_tram === null ? "—" : `${esc(item.thay_doi_phan_tram)}%`}</p>
            </article>`).join("")}</div>
            ${details.length ? `<div class="module-table-wrap"><table class="module-table">
                <thead><tr><th>Nguyên nhân</th><th>Loại xử lý</th><th>Số lượng</th><th>Tỷ lệ</th><th>Giá trị đơn</th><th>Đơn hàng áp dụng</th></tr></thead>
                <tbody>${details.map(item => `<tr><td>${esc(item.ten_nguyen_nhan)}</td>
                    <td>${esc(item.ten_loai_xu_ly)}</td><td>${Number(item.so_luong || 0)}</td>
                    <td>${item.ty_le === null ? "—" : `${esc(item.ty_le)}%`}</td>
                    <td>${formatMoney(item.gia_tri_don)}</td><td>${(item.don_hang_lien_quan || []).map(esc).join(", ") || "—"}</td></tr>`).join("")}</tbody>
            </table></div>` : `<p class="module-empty">Chưa có dữ liệu trong khoảng thời gian này.</p>`}`;
    };
    const notice = (node, text, error = false) => {
        node.className = `module-alert${error ? " error" : " success"}`;
        node.textContent = text;
    };
    async function api(url, method = "GET", data = null) {
        const headers = { Accept: "application/json" };
        const options = { method, credentials: "same-origin", headers };
        if (data !== null) {
            headers["X-CSRFToken"] = csrf();
            if (data instanceof FormData) {
                options.body = data;
            } else {
                headers["Content-Type"] = "application/json";
                options.body = JSON.stringify(data);
            }
        }
        const response = await fetch(url, options);
        const result = await response.json();
        if (!response.ok) {
            const details = result.errors ? Object.values(result.errors).flat().join(" ") : result.message || result.detail;
            throw new Error(details || "Không thể hoàn tất thao tác.");
        }
        return result;
    }

    async function setupCustomer(root) {
        const status = root.querySelector("#after-sales-message");
        const cancelOrder = root.querySelector("#cancel-order");
        const cancelReason = root.querySelector("#cancel-reason");
        const cancelNote = root.querySelector("#cancel-note");
        const returnOrder = root.querySelector("#return-order");
        const returnLines = root.querySelector("#return-lines");
        const returnType = root.querySelector("#return-type");
        const returnReason = root.querySelector("#return-reason");
        const returnNote = root.querySelector("#return-note");
        const returnImages = root.querySelector("#return-images");
        const returnRefundAccount = root.querySelector("#return-refund-account");
        const history = root.querySelector("#after-sales-history");
        const notifications = root.querySelector("#after-sales-notifications");
        let eligibleLines = [];
        let cancelReasonOptions = [];
        let returnReasonOptions = [];
        const refresh = async () => {
            const [ordersResult, cancelReasons, returnReasons, historyResult, notificationResult] = await Promise.all([
                api("/api/orders/"),
                api("/api/after-sales/nguyen-nhan/?loai=HUY_DON"),
                api("/api/after-sales/nguyen-nhan/?loai=DOI_TRA"),
                api("/api/after-sales/lich-su/"),
                api("/api/after-sales/thong-bao/")
            ]);
            const orders = ordersResult.data;
            const options = orders.map(order => `<option value="${esc(order.ma_dh)}">${esc(order.ma_dh)} · ${esc(order.ten_trang_thai)} · ${esc(order.ten_tinh)}</option>`).join("");
            cancelOrder.innerHTML = options || '<option value="">Chưa có đơn hàng</option>';
            returnOrder.innerHTML = options || '<option value="">Chưa có đơn hàng</option>';
            const reasonOptions = list => list.map(item => `<option value="${esc(item.ma_nguyen_nhan)}">${esc(item.ten_nguyen_nhan)}</option>`).join("");
            root._returnReasons = returnReasons.data;
            cancelReasonOptions = cancelReasons.data;
            cancelReason.innerHTML = reasonOptions(cancelReasons.data);
            cancelReason.dispatchEvent(new Event("change"));
            returnReasonOptions = returnReasons.data;
            returnReason.innerHTML = reasonOptions(returnReasonOptions);
            returnReason.dispatchEvent(new Event("change"));
            const entries = historyResult.data?.ket_qua || [];
            history.innerHTML = `<h3>Lịch sử yêu cầu</h3>${entries.length ? `<div class="module-table-wrap"><table class="module-table"><thead><tr><th>Đơn</th><th>Loại yêu cầu</th><th>Trạng thái</th><th>Cập nhật</th><th></th></tr></thead><tbody>${entries.map(item => `<tr><td>${esc(item.ma_dh)}</td><td>${esc(item.ten_loai_yeu_cau || humanValue(item.loai_yeu_cau))}</td><td><span class="module-pill">${esc(item.ten_trang_thai || item.trang_thai)}</span></td><td>${formatDate(item.cap_nhat_cuoi || item.thoi_diem_tao)}</td><td><button class="module-button secondary" data-timeline="${esc(item.loai_yeu_cau)}" data-id="${esc(item.ma_yeu_cau)}">Timeline</button>${item.trang_thai === "CHO_XU_LY" && ["HUY_DON", "DOI_TRA"].includes(item.loai_yeu_cau) ? ` <button class="module-button danger" data-withdraw="${esc(item.loai_yeu_cau)}" data-id="${esc(item.ma_yeu_cau)}">Thu hồi</button>` : ""}</td></tr>`).join("")}</tbody></table></div>` : '<p class="module-muted">Chưa có lịch sử hậu mãi.</p>'}`;
            const notices = notificationResult.data || [];
            notifications.innerHTML = `<h3>Thông báo</h3>${notices.length ? notices.map(item => `<article class="module-alert ${item.da_doc ? "" : "success"}"><strong>${esc(item.tieu_de)}</strong><p>${esc(item.noi_dung)}</p><small>${formatDate(item.thoi_diem_gui)}</small>${item.da_doc ? "" : `<button class="module-button secondary" data-read="${esc(item.ma_thong_bao)}">Đánh dấu đã đọc</button>`}</article>`).join("") : '<p class="module-muted">Bạn chưa có thông báo.</p>'}`;
            if (orders.length && !new URLSearchParams(location.search).get("ma_dh")) {
                cancelOrder.value = orders[0].ma_dh;
                returnOrder.value = orders.find(item => ["GIAO_THANH_CONG", "HOAN_THANH"].includes(item.trang_thai))?.ma_dh || orders[0].ma_dh;
            }
            await loadEligibleLines();
        };
        const loadEligibleLines = async () => {
            if (!returnOrder.value) return;
            try {
                const result = await api(`/api/after-sales/doi-tra/dong/${encodeURIComponent(returnOrder.value)}/`);
                eligibleLines = result.data;
                renderEligibleLines();
            } catch (error) {
                eligibleLines = [];
                returnLines.textContent = error.message;
            }
        };
        const renderEligibleLines = () => {
            const isExchange = returnType.value === "DOI";
            returnLines.innerHTML = eligibleLines.length ? eligibleLines.map(line => {
                const variants = (line.bien_the_thay_the || []).map(variant =>
                    `<option value="${esc(variant.ma_bien_the)}">${esc(variant.ten_bien_the)}</option>`
                ).join("");
                return `<label class="module-alert"><input type="checkbox" name="dong" value="${esc(line.ma_ctdh)}"> ${esc(line.ten_san_pham)} · còn ${line.so_luong_con_lai} sản phẩm <input type="number" min="1" max="${line.so_luong_con_lai}" value="1" data-quantity="${esc(line.ma_ctdh)}" aria-label="Số lượng">${isExchange ? `<select data-replacement="${esc(line.ma_ctdh)}" aria-label="Biến thể thay thế"><option value="">Chọn biến thể thay thế</option>${variants}</select>` : ""}</label>`;
            }).join("") : "Không có sản phẩm còn đủ điều kiện đổi/trả.";
        };

        returnOrder.addEventListener("change", loadEligibleLines);
        returnType.addEventListener("change", renderEligibleLines);
        const updateRefundAccountVisibility = () => {
            const show = returnType.value === "TRA";
            returnRefundAccount.hidden = !show;
            returnRefundAccount.querySelectorAll("input").forEach(input => {
                input.required = show;
            });
        };
        returnType.addEventListener("change", updateRefundAccountVisibility);
        updateRefundAccountVisibility();
        returnReason.addEventListener("change", () => {
            const reason = returnReasonOptions.find(item => item.ma_nguyen_nhan === returnReason.value);
            returnNote.required = Boolean(reason?.bat_buoc_ghi_chu);
            returnImages.required = Boolean(reason?.bat_buoc_anh);
        });
        cancelReason.addEventListener("change", () => {
            const reason = cancelReasonOptions.find(item => item.ma_nguyen_nhan === cancelReason.value);
            cancelNote.required = Boolean(reason?.bat_buoc_ghi_chu);
        });
        root.querySelector("#refresh-after-sales").addEventListener("click", async () => {
            try { await refresh(); notice(status, "Đã làm mới thông tin hậu mãi."); }
            catch (error) { notice(status, error.message, true); }
        });
        root.querySelector("#cancel-request-form").addEventListener("submit", async event => {
            event.preventDefault();
            const values = Object.fromEntries(new FormData(event.currentTarget).entries());
            try {
                const result = await api("/api/after-sales/huy/", "POST", values);
                notice(status, result.message);
                await refresh();
            } catch (error) { notice(status, error.message, true); }
        });
        root.querySelector("#return-request-form").addEventListener("submit", async event => {
            event.preventDefault();
            const form = event.currentTarget;
            const formData = new FormData(form);
            const selected = [...root.querySelectorAll('input[name="dong"]:checked')].map(input => ({
                ma_ctdh: input.value,
                so_luong: Number(root.querySelector(`[data-quantity="${CSS.escape(input.value)}"]`).value),
                ma_bien_the_doi: root.querySelector(`[data-replacement="${CSS.escape(input.value)}"]`)?.value || ""
            }));
            if (!selected.length) { notice(status, "Chọn ít nhất một dòng hàng cần đổi/trả.", true); return; }
            if (returnType.value === "DOI" && selected.some(item => !item.ma_bien_the_doi)) {
                notice(status, "Chọn biến thể thay thế cho từng dòng hàng cần đổi.", true);
                return;
            }
            const files = [...returnImages.files];
            if (files.length > 5 || files.some(file => file.size > 5 * 1024 * 1024)) {
                notice(status, "Chỉ đính kèm tối đa 5 ảnh, mỗi ảnh không quá 5 MB.", true);
                return;
            }
            formData.set("dong", JSON.stringify(selected));
            try {
                const result = await api("/api/after-sales/doi-tra/", "POST", formData);
                notice(status, result.message);
                await refresh();
            } catch (error) { notice(status, error.message, true); }
        });
        root.addEventListener("click", async event => {
            const timeline = event.target.closest("[data-timeline]");
            const read = event.target.closest("[data-read]");
            const withdraw = event.target.closest("[data-withdraw]");
            try {
                if (timeline) {
                    const result = await api(`/api/after-sales/lich-su/${encodeURIComponent(timeline.dataset.timeline)}/${encodeURIComponent(timeline.dataset.id)}/`);
                    notice(status, result.data.cac_moc.map(item => `${formatDate(item.thoi_diem)} · ${item.moc}`).join(" | "));
                }
                if (read) {
                    await api(`/api/after-sales/thong-bao/${encodeURIComponent(read.dataset.read)}/da-doc/`, "POST", {});
                    await refresh();
                }
                if (withdraw) {
                    const base = withdraw.dataset.withdraw === "HUY_DON" ? "huy" : "doi-tra";
                    await api(`/api/after-sales/${base}/${encodeURIComponent(withdraw.dataset.id)}/thu-hoi/`, "POST", {});
                    notice(status, "Đã thu hồi yêu cầu hậu mãi.");
                    await refresh();
                }
            } catch (error) { notice(status, error.message, true); }
        });

        try {
            await refresh();
            const requested = new URLSearchParams(location.search).get("ma_dh");
            if (requested) {
                cancelOrder.value = requested;
                returnOrder.value = requested;
                await loadEligibleLines();
            }
        } catch (error) { notice(status, error.message, true); }
    }

    async function setupStaff(root) {
        const status = root.querySelector("#staff-after-sales-message");
        const content = root.querySelector("#staff-after-sales-content");
        const endpoints = {
            cancel: "/api/after-sales/staff/huy/",
            delivery: "/api/after-sales/staff/giao-that-bai/",
            exchange: "/api/after-sales/staff/doi-tra/",
            refund: "/api/after-sales/staff/hoan-tien/",
            reasons: "/api/after-sales/staff/nguyen-nhan/",
            history: "/api/after-sales/lich-su/",
            stats: "/api/after-sales/staff/thong-ke/",
            notifications: "/api/after-sales/staff/thong-bao/"
        };
        let active = "";
        const rowsFrom = data => Array.isArray(data) ? data : data?.ket_qua || [];
        const button = (label, action, id, type = "cancel") =>
            `<button type="button" class="module-button secondary" data-item-action="${action}" data-item-id="${esc(id)}" data-type="${type}">${label}</button>`;

        const load = async (section, query = "") => {
            active = section;
            const url = new URL(endpoints[section], window.location.origin);
            if (query) url.search = query;
            const pageUrl = new URL(window.location.href);
            pageUrl.searchParams.set("tab", section);
            if (section !== "stats" || !query) {
                pageUrl.searchParams.delete("tu_ngay");
                pageUrl.searchParams.delete("den_ngay");
            } else {
                new URLSearchParams(query).forEach((value, key) => pageUrl.searchParams.set(key, value));
            }
            if (window.location.href !== pageUrl.href) window.history.pushState({ section }, "", pageUrl);
            root.querySelectorAll("[data-section]").forEach(node => {
                node.classList.toggle("secondary", node.dataset.section !== section);
            });
            content.innerHTML = '<div class="module-empty">Đang tải dữ liệu…</div>';
            const result = await api(url.toString());
            const data = result.data;
            const deliveryReasons = section === "delivery"
                ? rowsFrom((await api(`${endpoints.reasons}?loai_xu_ly=GIAO_THAT_BAI&dang_ap_dung=1`)).data)
                : [];
            if (section === "stats") {
                content.innerHTML = renderStats(data);
                return;
            }
            if (!Array.isArray(data) && !data?.ket_qua) {
                content.innerHTML = `<h2>${esc(sectionLabels[section] || "Thông tin")}</h2>${renderFields(data)}`;
                return;
            }
            const rows = rowsFrom(data);
            if (section === "reasons") {
                content.innerHTML = `<div class="module-heading"><div><h2>Danh mục nguyên nhân</h2><p>Quản lý nguyên nhân theo loại xử lý.</p></div></div>
                    <form id="reason-form" class="module-form-grid"><div><label>Loại xử lý</label><select name="loai_xu_ly"><option value="HUY_DON">Hủy đơn</option><option value="GIAO_THAT_BAI">Giao thất bại</option><option value="DOI_TRA">Đổi/trả</option></select></div><div><label>Tên nguyên nhân</label><input name="ten_nguyen_nhan" required maxlength="100"></div><div><label>Mô tả</label><input name="mo_ta" maxlength="255"></div><button class="module-button">Thêm nguyên nhân</button></form>
                    <div class="module-table-wrap" style="margin-top:18px"><table class="module-table after-sales-reasons">
                        <thead><tr><th>Mã</th><th>Loại</th><th>Tên nguyên nhân</th><th>Mô tả</th><th>Yêu cầu</th><th>Trạng thái</th><th>Thao tác</th></tr></thead>
                        <tbody>${rows.map(item => `<tr><td>${esc(item.ma_nguyen_nhan)}</td><td colspan="6"><form class="after-sales-reason-row" data-reason-update="${esc(item.ma_nguyen_nhan)}">
                            <select name="loai_xu_ly" aria-label="Loại xử lý"><option value="HUY_DON" ${item.loai_xu_ly === "HUY_DON" ? "selected" : ""}>Hủy đơn</option><option value="GIAO_THAT_BAI" ${item.loai_xu_ly === "GIAO_THAT_BAI" ? "selected" : ""}>Giao thất bại</option><option value="DOI_TRA" ${item.loai_xu_ly === "DOI_TRA" ? "selected" : ""}>Đổi/trả</option></select>
                            <input name="ten_nguyen_nhan" aria-label="Tên nguyên nhân" value="${esc(item.ten_nguyen_nhan)}" required maxlength="100">
                            <input name="mo_ta" aria-label="Mô tả" value="${esc(item.mo_ta || "")}" maxlength="255">
                            <span class="after-sales-reason-options"><label><input type="checkbox" name="bat_buoc_anh" ${item.bat_buoc_anh ? "checked" : ""}> Ảnh</label><label><input type="checkbox" name="bat_buoc_ghi_chu" ${item.bat_buoc_ghi_chu ? "checked" : ""}> Ghi chú</label><label><input type="checkbox" name="loi_do_cua_hang" ${item.loi_do_cua_hang ? "checked" : ""}> Lỗi cửa hàng</label></span>
                            <span>${item.dang_ap_dung ? "Đang áp dụng" : "Ngừng áp dụng"} · ${item.so_lan_su_dung} lần</span>
                            <span class="after-sales-reason-actions"><button class="module-button secondary" type="submit">Lưu</button><button class="module-button secondary" type="button" data-reason-action="toggle" data-id="${esc(item.ma_nguyen_nhan)}" data-active="${item.dang_ap_dung}">${item.dang_ap_dung ? "Ngừng" : "Kích hoạt"}</button><button class="module-button danger" type="button" data-reason-action="delete" data-id="${esc(item.ma_nguyen_nhan)}">Xóa</button></span>
                        </form></td></tr>`).join("")}</tbody>
                    </table></div>`;
                return;
            }
            const deliveryStockForm = section === "delivery"
                ? `<form class="module-inline-form" data-staff-form="delivery-stock"><label>Mã xử lý hoàn hàng<input name="ma_xu_ly" required maxlength="10"></label><button class="module-button secondary" type="submit">Xác nhận đã nhập kho</button></form>`
                : "";
            content.innerHTML = deliveryStockForm + (rows.length ? `<div class="module-grid">${rows.map(item => {
                const id = item.ma_yc_huy || item.ma_yc_doi_tra || item.ma_xu_ly || item.ma_hoan_tien || item.ma_thong_bao || item.ma_yeu_cau || item.ma_dh || "";
                const title = item.ma_dh ? `Đơn ${item.ma_dh}` : id || "Bản ghi hậu mãi";
                let actions = "";
                if (section === "cancel" && item.trang_thai === "CHO_XU_LY") {
                    actions = button("Duyệt", "DUYET", id) + button("Từ chối", "TU_CHOI", id);
                } else if (section === "delivery") {
                    const reasonOptions = deliveryReasons.map(reason =>
                        `<option value="${esc(reason.ma_nguyen_nhan)}">${esc(reason.ten_nguyen_nhan)}</option>`
                    ).join("");
                    const tomorrow = new Date();
                    tomorrow.setDate(tomorrow.getDate() + 1);
                    const retryDate = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, "0")}-${String(tomorrow.getDate()).padStart(2, "0")}`;
                    actions = `<form class="module-form-grid" data-staff-form="delivery" data-id="${esc(id)}">
                        <label>Nguyên nhân<select name="ma_nguyen_nhan" required>${reasonOptions}</select></label>
                        <label>Hướng xử lý<select name="huong_xu_ly"><option value="GIAO_LAI">Giao lại</option><option value="DOI_THONG_TIN_GIAO_LAI">Cập nhật địa chỉ rồi giao lại</option><option value="HOAN_VE_KHO">Hoàn về kho</option></select></label>
                        <label data-delivery-date>Ngày giao lại<input type="date" name="ngay_giao_lai" value="${retryDate}"></label>
                        <label data-delivery-address>Địa chỉ giao mới<input name="dia_chi_giao_moi" maxlength="500"></label>
                        <label data-warehouse-address hidden>Địa chỉ kho hoàn về<input name="dia_chi_kho" maxlength="500"></label>
                        <label data-recipient-name hidden>Người nhận mới<input name="ten_nguoi_nhan_moi" maxlength="100"></label>
                        <label data-recipient-phone hidden>Số điện thoại người nhận mới<input name="sdt_nguoi_nhan_moi" maxlength="15"></label>
                        <label>Đơn vị vận chuyển<input name="don_vi_van_chuyen" maxlength="100"></label>
                        <label>Mã vận đơn<input name="ma_van_don" maxlength="50"></label>
                        <label>Bên chịu phí<select name="ben_chiu_phi"><option value="CUA_HANG">Cửa hàng</option><option value="KHACH_HANG">Khách hàng</option></select></label>
                        <label>Ghi chú<textarea name="ghi_chu" maxlength="500"></textarea></label>
                        <label>Phản hồi khách<textarea name="phan_hoi_khach" maxlength="500"></textarea></label>
                        <button class="module-button" type="submit">Lưu hướng xử lý</button></form>`;
                } else if (section === "exchange" && item.trang_thai === "CHO_XU_LY") {
                    actions = button("Duyệt · chờ nhận hàng", "duyet", id, section)
                        + button("Duyệt · không thu hồi", "duyet-khong-thu-hoi", id, section)
                        + button("Từ chối", "tu-choi", id, section);
                } else if (section === "exchange" && item.trang_thai === "DANG_CHO_NHAN_HANG") {
                    const lineForms = (item.dong || []).map(line => `<div class="module-panel" data-return-line="${esc(line.ma_dong)}">
                        <strong>${esc(line.ten_san_pham)} · ${line.so_luong} sản phẩm</strong>
                        <label>Kết quả<select name="ketqua-${esc(line.ma_dong)}"><option value="DAT">Đạt</option><option value="KHONG_DAT">Không đạt</option></select></label>
                        <label>Số lượng đạt<input type="number" min="1" max="${line.so_luong}" value="${line.so_luong}" name="soluong-${esc(line.ma_dong)}"></label>
                        <label>Kho nhập<select name="kho-${esc(line.ma_dong)}"><option value="KHO_BAN">Kho bán</option><option value="KHO_LOI">Kho lỗi</option></select></label>
                        <label>Ghi chú<input name="ghichu-${esc(line.ma_dong)}"></label></div>`).join("");
                    actions = `<form class="module-form-grid" data-staff-form="exchange-receive" data-id="${esc(id)}">
                        ${lineForms}<label>Ghi chú xử lý<input name="ghi_chu"></label>
                        <label>Mã vận đơn gửi lại<input name="ma_van_don_gui_lai"></label>
                        <button class="module-button" type="submit">Ghi nhận nhận hàng</button></form>`;
                } else if (section === "exchange" && item.trang_thai === "DA_NHAN_HANG") {
                    actions = `<form class="module-form-grid" data-staff-form="exchange-complete" data-id="${esc(id)}">
                        <label>Mã vận đơn đổi hàng (nếu có)<input name="ma_van_don_doi"></label>
                        <button class="module-button" type="submit">Hoàn tất đổi/trả</button></form>`;
                } else if (section === "refund" && item.trang_thai === "CHO_HOAN") {
                    actions = `<form class="module-form-grid" data-staff-form="refund-confirm" data-id="${esc(id)}">
                        <label>Số tiền hoàn<input name="so_tien" type="number" min="1" value="${esc(item.so_tien_de_xuat)}" required></label>
                        <label>Mã giao dịch hoàn<input name="ma_giao_dich_hoan" maxlength="50" required></label>
                        <label>Phương thức<select name="phuong_thuc"><option value="CHUYEN_KHOAN">Chuyển khoản</option><option value="PHUONG_THUC_GOC">Phương thức gốc</option></select></label>
                        ${item.tai_khoan_nhan ? `<div><strong>Thông tin khách cung cấp</strong>${renderRefundAccount(item.tai_khoan_nhan)}</div>` : `<label>Tài khoản nhận tiền<input name="thong_tin_tai_khoan" maxlength="255" required></label>`}
                        <label>Lý do điều chỉnh (nếu hoàn thấp hơn đề xuất)<input name="ly_do_dieu_chinh" maxlength="255"></label>
                        <button class="module-button" type="submit">Xác nhận đã hoàn</button>
                        ${button("Ghi nhận thất bại", "that-bai", id, section)}</form>`;
                } else if (section === "notifications" && !item.da_doc) {
                    actions = button("Đánh dấu đã đọc", "read", id, section);
                }
                const statusLabel = item.ten_trang_thai || item.ten_huong_xu_ly
                    || item.ten_ket_qua_giao || item.ten_loai_xu_ly
                    || (item.trang_thai && humanValue(item.trang_thai))
                    || (item.loai_yeu_cau && humanValue(item.loai_yeu_cau)) || "Mới";
                const hasTimeline = ["cancel", "exchange", "refund", "history"].includes(section)
                    || (section === "delivery" && item.ma_xu_ly);
                const timelineButton = hasTimeline
                    ? '<button type="button" class="module-button secondary" data-load-timeline>Timeline</button>'
                    : "";
                return `<article class="module-panel" data-after-sales-card data-type="${esc(item.loai_yeu_cau || (section === "cancel" ? "HUY_DON" : section === "exchange" ? "DOI_TRA" : section === "refund" ? "HOAN_TIEN" : "GIAO_THAT_BAI"))}" data-id="${esc(id)}"><span class="module-eyebrow">${esc(sectionLabels[section] || "Hậu mãi")}</span><h3>${esc(title)}</h3><p><span class="module-pill">${esc(statusLabel)}</span></p>${renderFields(item)}${renderRefundAccount(item.tai_khoan_hoan || item.tai_khoan_nhan)}<div class="module-inline-form">${actions}${timelineButton}</div><div data-timeline-content></div></article>`;
            }).join("")}</div>` : '<div class="module-empty">Không có hồ sơ cần xử lý.</div>');
            content.querySelectorAll('[data-staff-form="delivery"] select[name="huong_xu_ly"]')
                .forEach(select => select.dispatchEvent(new Event("change", { bubbles: true })));
        };

        root.addEventListener("click", async event => {
            const tab = event.target.closest("[data-section]");
            const action = event.target.closest("[data-item-action]");
            const reasonAction = event.target.closest("[data-reason-action]");
            const timelineButton = event.target.closest("[data-load-timeline]");
            if (timelineButton) {
                const card = timelineButton.closest("[data-after-sales-card]");
                const timelineContent = card.querySelector("[data-timeline-content]");
                try {
                    const result = await api(`/api/after-sales/lich-su/${encodeURIComponent(card.dataset.type)}/${encodeURIComponent(card.dataset.id)}/`);
                    timelineContent.innerHTML = `<ol class="after-sales-timeline">${(result.data.cac_moc || []).map(moc =>
                        `<li><strong>${esc(moc.moc)}</strong> · ${formatDate(moc.thoi_diem)}<br><span>${esc(moc.ghi_chu || "")}</span></li>`
                    ).join("") || "<li>Chưa có mốc timeline.</li>"}</ol>`;
                } catch (error) { notice(status, error.message, true); }
                return;
            }
            if (tab) {
                try { await load(tab.dataset.section); }
                catch (error) { notice(status, error.message, true); }
                return;
            }
            if (reasonAction) {
                const id = encodeURIComponent(reasonAction.dataset.id);
                try {
                    if (reasonAction.dataset.reasonAction === "delete") {
                        if (!window.confirm("Xóa nguyên nhân này? Nếu đã được sử dụng, hệ thống sẽ từ chối xóa.")) return;
                        await api(`/api/after-sales/staff/nguyen-nhan/${id}/`, "DELETE");
                    } else {
                        const operation = reasonAction.dataset.active === "true" ? "ngung-su-dung" : "kich-hoat";
                        await api(`/api/after-sales/staff/nguyen-nhan/${id}/${operation}/`, "POST", {});
                    }
                    notice(status, "Đã cập nhật danh mục nguyên nhân.");
                    await load("reasons");
                } catch (error) { notice(status, error.message, true); }
                return;
            }
            if (!action) return;
            const id = encodeURIComponent(action.dataset.itemId);
            const type = action.dataset.type;
            try {
                let url = "";
                let payload = {};
                if (type === "cancel") {
                    url = `/api/after-sales/staff/huy/${id}/xu-ly/`;
                    payload = { quyet_dinh: action.dataset.itemAction };
                    if (action.dataset.itemAction === "TU_CHOI") {
                        payload.ly_do_tu_choi = window.prompt("Nhập lý do từ chối yêu cầu hủy:") || "";
                        if (!payload.ly_do_tu_choi) return;
                    }
                } else if (type === "delivery") {
                    url = `/api/after-sales/staff/giao-that-bai/${id}/xu-ly/`;
                    payload = { huong_xu_ly: "GIAO_LAI", ngay_giao_lai: new Date(Date.now() + 86400000).toISOString().slice(0, 10) };
                } else if (type === "exchange") {
                    const operation = action.dataset.itemAction === "duyet-khong-thu-hoi"
                        ? "duyet"
                        : action.dataset.itemAction;
                    url = `/api/after-sales/staff/doi-tra/${id}/${operation}/`;
                    if (action.dataset.itemAction === "tu-choi") {
                        payload = { ly_do: window.prompt("Nhập lý do từ chối yêu cầu đổi/trả:") || "" };
                        if (!payload.ly_do) return;
                    } else {
                        payload = { khong_thu_hoi_hang: action.dataset.itemAction === "duyet-khong-thu-hoi" };
                    }
                } else if (type === "refund") {
                    url = `/api/after-sales/staff/hoan-tien/${id}/${action.dataset.itemAction}/`;
                    if (action.dataset.itemAction === "that-bai") {
                        payload = { ly_do: window.prompt("Nhập lý do giao dịch hoàn tiền thất bại:") || "" };
                        if (!payload.ly_do) return;
                    }
                } else if (type === "notifications") {
                    url = `/api/after-sales/staff/thong-bao/${id}/da-doc/`;
                }
                const result = await api(url, "POST", payload);
                notice(status, result.message || "Đã cập nhật.");
                await load(active);
            } catch (error) { notice(status, error.message, true); }
        });
        root.addEventListener("submit", async event => {
            const form = event.target.closest("[data-stats-filter]");
            if (!form) return;
            event.preventDefault();
            const params = new URLSearchParams(new FormData(form));
            try { await load("stats", params.toString()); }
            catch (error) { notice(status, error.message, true); }
        });
        root.addEventListener("submit", async event => {
            const form = event.target.closest("#reason-form");
            if (form) {
                event.preventDefault();
                try {
                    const result = await api(endpoints.reasons, "POST", Object.fromEntries(new FormData(form).entries()));
                    notice(status, result.message);
                    await load("reasons");
                } catch (error) { notice(status, error.message, true); }
                return;
            }
            const editReason = event.target.closest("[data-reason-update]");
            if (editReason) {
                event.preventDefault();
                const values = Object.fromEntries(new FormData(editReason).entries());
                ["bat_buoc_anh", "bat_buoc_ghi_chu", "loi_do_cua_hang"].forEach(name => {
                    values[name] = editReason.querySelector(`[name="${name}"]`).checked;
                });
                try {
                    const id = encodeURIComponent(editReason.dataset.reasonUpdate);
                    const result = await api(`/api/after-sales/staff/nguyen-nhan/${id}/`, "PATCH", values);
                    notice(status, result.message);
                    await load("reasons");
                } catch (error) { notice(status, error.message, true); }
                return;
            }
            const staffForm = event.target.closest("[data-staff-form]");
            if (!staffForm) return;
            event.preventDefault();
            const values = Object.fromEntries(new FormData(staffForm).entries());
            const id = encodeURIComponent(staffForm.dataset.id);
            let url;
            let payload = values;
            if (staffForm.dataset.staffForm === "delivery") {
                url = `/api/after-sales/staff/giao-that-bai/${id}/xu-ly/`;
                if (!values.ngay_giao_lai) delete values.ngay_giao_lai;
            } else if (staffForm.dataset.staffForm === "delivery-stock") {
                url = `/api/after-sales/staff/giao-that-bai/xu-ly/${encodeURIComponent(values.ma_xu_ly)}/nhap-kho/`;
                payload = {};
            } else if (staffForm.dataset.staffForm === "exchange-receive") {
                url = `/api/after-sales/staff/doi-tra/${id}/nhan-hang/`;
                payload.ket_qua_dong = [...staffForm.querySelectorAll("[data-return-line]")].map(line => {
                    const code = line.dataset.returnLine;
                    const result = values[`ketqua-${code}`];
                    return {
                        ma_dong: code,
                        ket_qua: result,
                        ...(result === "DAT" ? {
                            so_luong_dat: Number(values[`soluong-${code}`]),
                            kho_nhap: values[`kho-${code}`]
                        } : {}),
                        ghi_chu: values[`ghichu-${code}`] || ""
                    };
                });
                root.addEventListener("change", event => {
                    const select = event.target.closest('[data-staff-form="delivery"] select[name="huong_xu_ly"]');
                    if (!select) return;
                    const form = select.form;
                    const address = form.querySelector("[data-delivery-address]");
                    const warehouse = form.querySelector("[data-warehouse-address]");
                    const date = form.querySelector("[data-delivery-date]");
                    const recipientName = form.querySelector("[data-recipient-name]");
                    const recipientPhone = form.querySelector("[data-recipient-phone]");
                    const changeAddress = select.value === "DOI_THONG_TIN_GIAO_LAI";
                    const returnToWarehouse = select.value === "HOAN_VE_KHO";
                    address.hidden = !changeAddress;
                    address.querySelector("input").required = changeAddress;
                    warehouse.hidden = !returnToWarehouse;
                    warehouse.querySelector("input").required = returnToWarehouse;
                    recipientName.hidden = !changeAddress;
                    recipientPhone.hidden = !changeAddress;
                    date.hidden = returnToWarehouse;
                    date.querySelector("input").required = !returnToWarehouse;
                });
                Object.keys(payload).filter(key => /^(ketqua|soluong|kho|ghichu)-/.test(key))
                    .forEach(key => delete payload[key]);
            } else if (staffForm.dataset.staffForm === "exchange-complete") {
                url = `/api/after-sales/staff/doi-tra/${id}/hoan-tat/`;
            } else {
                url = `/api/after-sales/staff/hoan-tien/${id}/xac-nhan/`;
            }
            try {
                const result = await api(url, "POST", payload);
                notice(status, `${result.message}${result.data?.ma_xu_ly ? ` · Mã xử lý: ${result.data.ma_xu_ly}` : ""}`);
                await load(active);
            } catch (error) { notice(status, error.message, true); }
        });
        window.addEventListener("popstate", () => {
            if (!root.isConnected) return;
            const params = new URLSearchParams(window.location.search);
            const section = endpoints[params.get("tab")] ? params.get("tab") : "cancel";
            const query = section === "stats"
                ? new URLSearchParams([...params].filter(([key]) => ["tu_ngay", "den_ngay"].includes(key))).toString()
                : "";
            load(section, query).catch(error => notice(status, error.message, true));
        });
        const params = new URLSearchParams(window.location.search);
        const initialSection = endpoints[params.get("tab")] ? params.get("tab") : "cancel";
        const initialQuery = initialSection === "stats"
            ? new URLSearchParams([...params].filter(([key]) => ["tu_ngay", "den_ngay"].includes(key))).toString()
            : "";
        load(initialSection, initialQuery).catch(error => notice(status, error.message, true));
    }

    document.addEventListener("DOMContentLoaded", () => {
        const customer = document.querySelector("#customer-after-sales");
        const staff = document.querySelector("#staff-after-sales");
        if (customer) setupCustomer(customer);
        if (staff) setupStaff(staff);
    });
})();
