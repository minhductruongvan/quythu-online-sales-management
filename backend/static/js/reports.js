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
        const values = data.revenue_millions || [];
        const labels = data.labels || [];
        if (!values.length) {
            chart.hidden = true;
            chart.insertAdjacentHTML("afterend", '<div class="report-chart-empty">Chưa có dữ liệu doanh thu trong kỳ.</div>');
            return;
        }

        const width = 920;
        const height = 300;
        const margin = { top: 20, right: 18, bottom: 42, left: 58 };
        const plotWidth = width - margin.left - margin.right;
        const plotHeight = height - margin.top - margin.bottom;
        const maxValue = Math.max(...values, 1);
        const scaleMax = maxValue * 1.12;
        const stepX = values.length > 1 ? plotWidth / (values.length - 1) : 0;
        const points = values.map((value, index) => ({
            x: margin.left + stepX * index,
            y: margin.top + plotHeight - (value / scaleMax) * plotHeight,
            value,
            label: labels[index],
            orders: (data.orders_count || [])[index] || 0,
        }));

        const svg = makeSvgElement("svg", {
            class: "report-chart",
            viewBox: `0 0 ${width} ${height}`,
            role: "img",
            "aria-label": "Doanh thu hoàn thành theo ngày, tính bằng triệu đồng",
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
                makeSvgElement("text", {
                    x: margin.left - 10,
                    y: y + 4,
                    "text-anchor": "end",
                }),
            );
            gridGroup.lastChild.textContent = `${(scaleMax * (1 - ratio)).toFixed(1)}`;
        }
        svg.append(gridGroup);

        const linePath = points.map((point, index) =>
            `${index ? "L" : "M"} ${point.x} ${point.y}`
        ).join(" ");
        const areaPath = `${linePath} L ${points[points.length - 1].x} ${margin.top + plotHeight} L ${points[0].x} ${margin.top + plotHeight} Z`;
        svg.append(
            makeSvgElement("path", { class: "report-chart-area", d: areaPath }),
            makeSvgElement("path", { class: "report-chart-line", d: linePath }),
        );

        const labelStep = Math.max(1, Math.ceil(labels.length / 7));
        points.forEach((point, index) => {
            if (index % labelStep === 0 || index === points.length - 1) {
                const label = makeSvgElement("text", {
                    x: point.x,
                    y: height - 12,
                    "text-anchor": "middle",
                });
                label.textContent = point.label;
                svg.append(label);
            }
            const circle = makeSvgElement("circle", {
                class: "report-chart-point",
                cx: point.x,
                cy: point.y,
                r: values.length > 40 ? 2.5 : 4,
            });
            const title = makeSvgElement("title");
            title.textContent = `${point.label}: ${point.value.toLocaleString("vi-VN")} triệu đồng · ${point.orders} đơn`;
            circle.append(title);
            svg.append(circle);
        });
        chart.replaceChildren(svg);
    };

    const toggleCustomRange = () => {
        const preset = document.querySelector("[data-report-preset]");
        const range = document.querySelector("[data-report-range]");
        if (!preset || !range) return;
        const isCustom = preset.value === "custom";
        range.hidden = !isCustom;
        range.querySelectorAll("input").forEach((input) => {
            input.required = isCustom;
        });
    };

    document.addEventListener("DOMContentLoaded", () => {
        renderRevenueChart();
        const preset = document.querySelector("[data-report-preset]");
        if (preset) {
            preset.addEventListener("change", toggleCustomRange);
            toggleCustomRange();
        }
    });
})();
