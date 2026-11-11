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

        const width = 1000;
        const height = 320;
        const margin = { top: 24, right: 54, bottom: 46, left: 62 };
        const plotWidth = width - margin.left - margin.right;
        const plotHeight = height - margin.top - margin.bottom;
        const revenueMax = Math.max(...revenue, 1) * 1.12;
        const ordersMax = Math.max(...orders, 1) * 1.12;
        const stepX = plotWidth / labels.length;
        const xAt = index => margin.left + stepX * (index + 0.5);
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
            preserveAspectRatio: "xMidYMid meet",
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

        const barWidth = Math.max(3, Math.min(32, stepX * 0.48));
        const bars = makeSvgElement("g", { class: "report-chart-bars" });
        points.forEach(point => {
            const bar = makeSvgElement("rect", {
                x: point.x - barWidth / 2,
                y: point.revenueY,
                width: barWidth,
                height: margin.top + plotHeight - point.revenueY,
                rx: Math.min(4, barWidth / 2),
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
        range.querySelectorAll("input").forEach(input => {
            input.required = isCustom;
        });
    };

    function setupReportPage(page = document.querySelector(".report-page")) {
        if (!page) return;
        page.querySelectorAll("[data-report-form]").forEach(form => {
            toggleCustomRange(form);
            form.addEventListener("change", event => {
                if (event.target.matches("[data-report-preset]")) toggleCustomRange(form);
            });
        });
        page.querySelectorAll("[data-order-sort]").forEach(button => {
            button.addEventListener("click", () => {
                const form = page.querySelector("[data-report-form]");
                if (!form) return;
                const field = form.elements.namedItem("order_sort");
                const direction = form.elements.namedItem("order_sort_dir");
                if (!field || !direction) return;
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
})();
