(() => {
    const makeSvgElement = (name, attributes = {}) => {
        const element = document.createElementNS("http://www.w3.org/2000/svg", name);
        Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
        return element;
    };

    const renderRevenueChart = () => {
        const dataElement = document.getElementById("report-timeline");
        const chart = document.getElementById("revenue-chart");
        if (!dataElement || !chart) return;

        const data = JSON.parse(dataElement.textContent);
        const revenue = data.revenue_millions || [];
        const orders = data.orders_count || [];
        const labels = data.labels || [];
        if (!labels.length || (!revenue.some(value => value > 0) && !orders.some(value => value > 0))) {
            chart.replaceChildren();
            const empty = document.createElement("div");
            empty.className = "report-chart-empty";
            empty.textContent = "Chưa có dữ liệu trong kỳ này.";
            chart.append(empty);
            return;
        }

        const width = 920;
        const height = 300;
        const margin = { top: 20, right: 48, bottom: 42, left: 58 };
        const plotWidth = width - margin.left - margin.right;
        const plotHeight = height - margin.top - margin.bottom;
        const revenueMax = Math.max(...revenue, 1) * 1.12;
        const ordersMax = Math.max(...orders, 1) * 1.12;
        const stepX = labels.length > 1 ? plotWidth / (labels.length - 1) : 0;
        const xAt = index => labels.length > 1
            ? margin.left + stepX * index
            : margin.left + plotWidth / 2;
        const points = labels.map((label, index) => ({
            x: xAt(index),
            y: margin.top + plotHeight - ((orders[index] || 0) / ordersMax) * plotHeight,
            revenueY: margin.top + plotHeight - ((revenue[index] || 0) / revenueMax) * plotHeight,
            revenue: revenue[index] || 0,
            orders: orders[index] || 0,
            label,
        }));
        const svg = makeSvgElement("svg", {
            class: "report-chart",
            viewBox: `0 0 ${width} ${height}`,
            role: "img",
            "aria-label": "Doanh thu dạng cột và số đơn dạng đường theo kỳ",
            preserveAspectRatio: "none",
        });
        const gridGroup = makeSvgElement("g");
        for (let index = 0; index <= 4; index += 1) {
            const ratio = index / 4;
            const y = margin.top + plotHeight * ratio;
            gridGroup.append(
                makeSvgElement("line", {
                    class: "report-chart-grid",
                    x1: margin.left,
                    x2: width - margin.right,
                    y1: y,
                    y2: y,
                }),
            );
            const revenueLabel = makeSvgElement("text", {
                x: margin.left - 10, y: y + 4, "text-anchor": "end",
            });
            revenueLabel.textContent = (revenueMax * (1 - ratio)).toFixed(1);
            gridGroup.append(revenueLabel);
            const ordersLabel = makeSvgElement("text", {
                x: width - margin.right + 10, y: y + 4, "text-anchor": "start",
            });
            ordersLabel.textContent = Math.round(ordersMax * (1 - ratio));
            gridGroup.append(ordersLabel);
        }
        svg.append(gridGroup);

        const barWidth = Math.max(4, Math.min(24, labels.length > 1 ? stepX * 0.58 : plotWidth * 0.42));
        const bars = makeSvgElement("g", { class: "report-chart-bars" });
        points.forEach(point => {
            const bar = makeSvgElement("rect", {
                x: point.x - barWidth / 2,
                y: point.revenueY,
                width: barWidth,
                height: margin.top + plotHeight - point.revenueY,
                rx: 2,
            });
            const title = makeSvgElement("title");
            title.textContent = `${point.label}: ${point.revenue.toLocaleString("vi-VN")} triệu đồng`;
            bar.append(title);
            bars.append(bar);
        });
        svg.append(bars);

        const linePath = points.map((point, index) =>
            `${index ? "L" : "M"} ${point.x} ${point.y}`
        ).join(" ");
        svg.append(makeSvgElement("path", { class: "report-chart-orders", d: linePath }));

        const labelStep = Math.max(1, Math.ceil(labels.length / 7));
        points.forEach((point, index) => {
            if (index % labelStep === 0 || index === points.length - 1) {
                const label = makeSvgElement("text", {
                    x: point.x, y: height - 12, "text-anchor": "middle",
                });
                label.textContent = point.label;
                svg.append(label);
            }
            const circle = makeSvgElement("circle", {
                class: "report-chart-order-point",
                cx: point.x,
                cy: point.y,
                r: labels.length > 40 ? 2.5 : 4,
            });
            const title = makeSvgElement("title");
            title.textContent = `${point.label}: ${point.orders} đơn`;
            circle.append(title);
            svg.append(circle);
        });
        chart.replaceChildren(svg);
    };

    const toggleCustomRange = form => {
        const preset = form.querySelector("[data-report-preset]");
        const range = form.querySelector("[data-report-range]");
        if (!preset || !range) return;
        const isCustom = preset.value === "custom";
        range.hidden = !isCustom;
        if (isCustom) {
            const extraFilters = form.querySelector(".report-extra-filters");
            if (extraFilters) extraFilters.open = true;
        }
        range.querySelectorAll("input").forEach(input => {
            input.required = isCustom;
        });
    };

    const showFilterError = message => {
        const page = document.querySelector(".report-page");
        if (!page) return;
        let error = page.querySelector("[data-report-error]");
        if (!error) {
            error = document.createElement("p");
            error.className = "report-filter-error-message";
            error.setAttribute("role", "alert");
            error.dataset.reportError = "";
            page.prepend(error);
        }
        error.textContent = message;
    };

    const replaceReportPage = html => {
        const parsed = new DOMParser().parseFromString(html, "text/html");
        const newPage = parsed.querySelector(".report-page");
        const currentPage = document.querySelector(".report-page");
        if (!newPage || !currentPage) {
            const errorText = parsed.querySelector(".report-filter-error p")?.textContent;
            showFilterError(errorText || "Không thể tải dữ liệu báo cáo. Vui lòng thử lại.");
            return false;
        }
        currentPage.replaceWith(newPage);
        const nextData = parsed.getElementById("report-timeline");
        const currentData = document.getElementById("report-timeline");
        if (nextData && currentData) currentData.textContent = nextData.textContent;
        document.title = parsed.title;
        setupReportPage(newPage);
        renderRevenueChart();
        return true;
    };

    const fetchReport = async (url, updateHistory = false) => {
        const response = await fetch(url, {
            headers: { "X-Requested-With": "XMLHttpRequest" },
            credentials: "same-origin",
        });
        const html = await response.text();
        if (updateHistory && response.ok) window.history.pushState({}, "", url);
        replaceReportPage(html);
    };

    function setupReportPage(page = document.querySelector(".report-page")) {
        if (!page) return;
        page.addEventListener("click", event => {
            const link = event.target.closest("a[href]");
            if (!link) return;
            if (!["/reports/chi-tiet/", "/reports/dashboard/"].includes(link.pathname)) return;
            event.preventDefault();
            const url = new URL(link.href);
            if (link.classList.contains("report-tab") || link.closest(".report-pager")) {
                const groupBy = page.querySelector('[name="group_by"]')?.value;
                const pageSize = page.querySelector('[name="page_size"]')?.value;
                if (groupBy) url.searchParams.set("group_by", groupBy);
                if (pageSize) url.searchParams.set("page_size", pageSize);
            }
            fetchReport(url, true)
                .catch(() => showFilterError("Không thể kết nối để cập nhật báo cáo. Vui lòng thử lại."));
        });
        page.querySelectorAll("[data-report-form]").forEach(form => {
            toggleCustomRange(form);
            form.addEventListener("change", event => {
                const field = event.target;
                if (!field.matches("select, input")) return;
                if (field.matches("[data-report-preset]")) {
                    toggleCustomRange(form);
                    if (field.value === "custom") return;
                }
                form.requestSubmit();
            });
            form.addEventListener("submit", event => {
                event.preventDefault();
                toggleCustomRange(form);
                if ([...form.querySelectorAll("[data-report-range] input[required]")].some(input => !input.value)) return;
                const url = new URL(form.action, window.location.origin);
                url.search = new URLSearchParams(new FormData(form)).toString();
                fetchReport(url, true).catch(() => showFilterError("Không thể kết nối để cập nhật báo cáo. Vui lòng thử lại."));
            });
        });
        page.querySelectorAll("[data-order-sort]").forEach(button => {
            button.addEventListener("click", () => {
                const form = page.querySelector("[data-report-form]");
                if (!form) return;
                const field = form.elements.namedItem("order_sort");
                const direction = form.elements.namedItem("order_sort_dir");
                direction.value = field.value === button.dataset.orderSort && direction.value === "asc" ? "desc" : "asc";
                field.value = button.dataset.orderSort;
                form.requestSubmit();
            });
        });
    }

    document.addEventListener("DOMContentLoaded", () => {
        setupReportPage();
        renderRevenueChart();
    });

    window.addEventListener("popstate", () => {
        fetchReport(window.location.href).catch(() => showFilterError("Không thể tải lại báo cáo đã chọn."));
    });
})();
