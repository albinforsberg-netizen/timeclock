const palette = ["#e4674f", "#187c78", "#efc85b", "#5887a8", "#8b6b9b", "#9cae83", "#d08a5a"];
let dashboardData;
let trendChart;
let targetChart;
let sessionChart;
let startTimeChart;

const hours = value => `${Number(value).toFixed(2)} h`;
const labelsFor = (keys, period) => keys.map(key => period === "daily" ? key.slice(5) : period === "weekly" ? key.slice(5) : key);

function makeChartOptions() {
    return { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { displayColors: false, callbacks: { label: context => ` ${hours(context.raw)}` } } }, scales: { x: { grid: { display: false }, ticks: { color: "#66777a", font: { family: "DM Mono", size: 10 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 12 } }, y: { beginAtZero: true, grid: { color: "#e1e5df" }, ticks: { color: "#66777a", font: { family: "DM Mono", size: 10 } } } } };
}

function renderTrend(period = "daily") {
    const keys = Object.keys(dashboardData[period]).slice(period === "daily" ? -30 : -12);
    const values = keys.map(key => dashboardData[period][key]);
    if (trendChart) trendChart.destroy();
    trendChart = new Chart(document.getElementById("trend-chart"), { type: "bar", data: { labels: labelsFor(keys, period), datasets: [{ data: values, backgroundColor: "#e4674f", borderRadius: 2, borderSkipped: false, maxBarThickness: 30 }] }, options: makeChartOptions() });
}

function renderProjects() {
    const entries = Object.entries(dashboardData.projects);
    const chartEntries = entries.slice(0, 6);
    const remainder = entries.slice(6).reduce((sum, [, value]) => sum + value, 0);
    if (remainder) chartEntries.push(["Other", remainder]);
    new Chart(document.getElementById("project-chart"), { type: "doughnut", data: { labels: chartEntries.map(([label]) => label), datasets: [{ data: chartEntries.map(([, value]) => value), backgroundColor: palette, borderWidth: 0, hoverOffset: 5 }] }, options: { responsive: true, maintainAspectRatio: false, cutout: "70%", plugins: { legend: { display: false }, tooltip: { callbacks: { label: context => ` ${context.label}: ${hours(context.raw)}` } } } } });
    document.getElementById("project-legend").innerHTML = chartEntries.map(([label, value], index) => `<div class="legend-row"><span class="legend-label" style="--legend-color:${palette[index]}">${label}</span><span class="legend-value">${hours(value)}</span></div>`).join("");
}

function renderWeekdays() {
    const labels = Object.keys(dashboardData.weekdays).map(day => day.slice(0, 3));
    new Chart(document.getElementById("weekday-chart"), { type: "bar", data: { labels, datasets: [{ data: Object.values(dashboardData.weekdays), backgroundColor: "#187c78", borderRadius: 2, maxBarThickness: 42 }] }, options: makeChartOptions() });
}

function renderTarget() {
    const keys = Object.keys(dashboardData.daily).slice(-30);
    const values = keys.map(key => dashboardData.daily[key]);
    if (targetChart) targetChart.destroy();
    targetChart = new Chart(document.getElementById("target-chart"), { type: "bar", data: { labels: labelsFor(keys, "daily"), datasets: [{ label: "Hours", data: values, backgroundColor: values.map(value => value >= dashboardData.target_hours_per_day ? "#187c78" : "#e4674f"), borderRadius: 2, maxBarThickness: 28 }, { type: "line", label: "Target", data: values.map(() => dashboardData.target_hours_per_day), borderColor: "#19242a", borderDash: [5, 5], borderWidth: 1.5, pointRadius: 0 }] }, options: makeChartOptions() });
}

function renderSessionShape() {
    const labels = Object.keys(dashboardData.session_buckets);
    if (sessionChart) sessionChart.destroy();
    sessionChart = new Chart(document.getElementById("session-chart"), { type: "bar", data: { labels, datasets: [{ data: Object.values(dashboardData.session_buckets), backgroundColor: "#efc85b", borderRadius: 2, maxBarThickness: 34 }] }, options: { ...makeChartOptions(), indexAxis: "y", scales: { x: { beginAtZero: true, grid: { color: "#e1e5df" }, ticks: { color: "#66777a", font: { family: "DM Mono", size: 10 } } }, y: { grid: { display: false }, ticks: { color: "#66777a", font: { family: "DM Mono", size: 10 } } } } } });
}

function renderProjectTable(filter = "") {
    const total = dashboardData.total_hours;
    const rows = Object.entries(dashboardData.projects).filter(([name]) => name.toLowerCase().includes(filter.toLowerCase()));
    document.getElementById("project-table").innerHTML = rows.map(([name, value]) => {
        const sessions = dashboardData.project_sessions[name] || 0;
        const share = total ? (value / total) * 100 : 0;
        return `<div class="project-row"><span class="project-name">${name}</span><span class="project-bar"><i style="width:${share}%"></i></span><span class="project-hours">${hours(value)}</span><span class="project-share">${share.toFixed(1)}%</span><span class="project-average">${hours(value / sessions)}/session</span></div>`;
    }).join("");
}

function dateKey(date) {
    return date.toISOString().slice(0, 10);
}

function renderSignals() {
    const days = Object.values(dashboardData.daily);
    const target = dashboardData.target_hours_per_day;
    const targetDays = days.filter(value => value >= target).length;
    const latestKey = Object.keys(dashboardData.daily).at(-1);
    const latestDate = new Date(`${latestKey}T12:00:00`);
    let streak = 0;
    for (let cursor = new Date(latestDate); dashboardData.daily[dateKey(cursor)] > 0; cursor.setDate(cursor.getDate() - 1)) streak += 1;
    const longest = dashboardData.longest_session;
    const busiest = Object.entries(dashboardData.daily).sort(([, first], [, second]) => second - first)[0];
    const signals = [
        ["Target hit rate", `${days.length ? ((targetDays / days.length) * 100).toFixed(0) : 0}%`, `${targetDays} of ${days.length} active days`],
        ["Current streak", `${streak} day${streak === 1 ? "" : "s"}`, "consecutive logged days"],
        ["Longest session", hours(longest.hours), `${longest.date} / ${longest.project}`],
        ["Busiest day", hours(busiest ? busiest[1] : 0), busiest ? busiest[0] : "No data"],
    ];
    document.getElementById("signal-grid").innerHTML = signals.map(([label, value, note]) => `<article class="signal"><span>${label}</span><strong>${value}</strong><small>${note}</small></article>`).join("");
}

function renderHeatmap() {
    const keys = Object.keys(dashboardData.daily);
    const latestDate = new Date(`${keys.at(-1)}T12:00:00`);
    const startDate = new Date(latestDate);
    startDate.setDate(startDate.getDate() - 111);
    const cells = [];
    for (let index = 0; index < 112; index += 1) {
        const date = new Date(startDate);
        date.setDate(startDate.getDate() + index);
        const value = dashboardData.daily[dateKey(date)] || 0;
        const level = value === 0 ? 0 : value < 4 ? 1 : value < 7 ? 2 : value < 8.5 ? 3 : 4;
        cells.push(`<i class="heat-cell level-${level}" title="${dateKey(date)}: ${hours(value)}"></i>`);
    }
    document.getElementById("heatmap").innerHTML = cells.join("");
    document.getElementById("heatmap-range").textContent = `${dateKey(startDate)} / ${dateKey(latestDate)}`;
}

function renderStartTimes() {
    const labels = Object.keys(dashboardData.start_hours_time);
    startTimeChart = new Chart(document.getElementById("start-time-chart"), { type: "bar", data: { labels, datasets: [{ data: Object.values(dashboardData.start_hours_time), backgroundColor: "#5887a8", borderRadius: 2, maxBarThickness: 34 }] }, options: makeChartOptions() });
}

function renderRecent() {
    document.getElementById("recent-sessions").innerHTML = dashboardData.sessions.map(session => `<tr><td>${session.date}</td><td>${session.project}</td><td class="numeric">${hours(session.hours)}</td></tr>`).join("");
}

async function start() {
    dashboardData = await fetch("data/dashboard.json").then(response => response.json());
    document.getElementById("total-hours").textContent = hours(dashboardData.total_hours);
    document.getElementById("session-count").textContent = dashboardData.session_count;
    document.getElementById("active-days").textContent = dashboardData.active_days;
    document.getElementById("average-day").textContent = hours(dashboardData.total_hours / dashboardData.active_days);
    document.getElementById("updated").textContent = `UPDATED ${dashboardData.generated_at.replace("T", " ")}`;
    renderTrend(); renderProjects(); renderWeekdays(); renderTarget(); renderSessionShape(); renderProjectTable(); renderSignals(); renderHeatmap(); renderStartTimes(); renderRecent();
    document.querySelectorAll(".period-button").forEach(button => button.addEventListener("click", () => { document.querySelector(".period-button.is-active").classList.remove("is-active"); button.classList.add("is-active"); renderTrend(button.dataset.period); }));
    document.getElementById("project-filter").addEventListener("input", event => renderProjectTable(event.target.value));
}

start().catch(error => {
    console.error("Unable to load dashboard data", error);
    document.getElementById("updated").textContent = "DATA UNAVAILABLE";
    document.querySelectorAll(".chart-panel").forEach(panel => {
        if (panel.querySelector("canvas")) {
            const notice = document.createElement("p");
            notice.className = "data-notice";
            notice.textContent = "Dashboard data has not been generated yet.";
            panel.appendChild(notice);
        }
    });
});