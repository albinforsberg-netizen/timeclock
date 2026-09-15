const palette = ["#e4674f", "#187c78", "#efc85b", "#5887a8", "#8b6b9b", "#9cae83", "#d08a5a"];
let dashboardData;
let trendChart;
let projectChart;
let targetChart;
let sessionChart;
let startTimeChart;
let cadenceChart;
let breadthChart;
let projectTrendChart;
let activePeriod = "daily";
let activeRange = "30";
let activeProject = "";

const hours = value => `${Number(value).toFixed(2)} h`;
const labelsFor = (keys, period) => keys.map(key => period === "daily" ? key.slice(5) : period === "weekly" ? key.slice(5) : key);

function normaliseDashboardData(data) {
    data.daily = data.daily || {};
    data.weekly = data.weekly || {};
    data.monthly = data.monthly || {};
    data.quarterly = data.quarterly || {};
    data.projects = data.projects || {};
    data.project_sessions = data.project_sessions || {};
    data.monthly_projects = data.monthly_projects || {};
    data.daily_sessions = data.daily_sessions || {};
    data.daily_projects = data.daily_projects || {};
    data.start_hours_time = data.start_hours_time || data.start_hours || {};
    data.session_buckets = data.session_buckets || {};
    data.target_hours_per_day = data.target_hours_per_day || 8;
    data.project_count = data.project_count || Object.keys(data.projects).length;
    data.session_stats = data.session_stats || {
        average: data.session_count ? data.total_hours / data.session_count : 0,
        median: data.session_count ? data.total_hours / data.session_count : 0,
    };
    data.longest_session = data.longest_session || { date: "", project: "", hours: 0 };
    data.weekend_hours = data.weekend_hours || Object.entries(data.daily).reduce((sum, [day, value]) => {
        const weekday = new Date(`${day}T12:00:00`).getDay();
        return sum + (weekday === 0 || weekday === 6 ? value : 0);
    }, 0);
    return data;
}

function makeChartOptions() {
    return { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { displayColors: false, callbacks: { label: context => ` ${hours(context.raw)}` } } }, scales: { x: { grid: { display: false }, ticks: { color: "#66777a", font: { family: "DM Mono", size: 10 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 12 } }, y: { beginAtZero: true, grid: { color: "#e1e5df" }, ticks: { color: "#66777a", font: { family: "DM Mono", size: 10 } } } } };
}

function rangeLimit(period) {
    if (activeRange === "all") return undefined;
    const days = Number(activeRange);
    const divisor = period === "daily" ? 1 : period === "weekly" ? 7 : period === "monthly" ? 30 : 90;
    return Math.ceil(days / divisor);
}

function renderTrend(period = activePeriod) {
    activePeriod = period;
    const limit = rangeLimit(period);
    const keys = Object.keys(dashboardData[period]).slice(limit ? -limit : undefined);
    const values = keys.map(key => dashboardData[period][key]);
    const smoothingWindow = period === "daily" ? 7 : period === "weekly" ? 4 : 0;
    const trend = smoothingWindow ? values.map((_, index) => {
        const window = values.slice(Math.max(0, index - smoothingWindow + 1), index + 1);
        return window.reduce((sum, value) => sum + value, 0) / window.length;
    }) : [];
    if (trendChart) trendChart.destroy();
    const datasets = [{ data: values, backgroundColor: "#e4674f", borderRadius: 2, borderSkipped: false, maxBarThickness: 30 }];
    if (smoothingWindow) datasets.push({ type: "line", label: `${smoothingWindow}-period pace`, data: trend, borderColor: "#19242a", borderWidth: 2, pointRadius: 0, tension: 0.25 });
    trendChart = new Chart(document.getElementById("trend-chart"), { type: "bar", data: { labels: labelsFor(keys, period), datasets }, options: makeChartOptions() });
}

function renderProjects() {
    const entries = Object.entries(dashboardData.projects).filter(([name]) => !activeProject || name === activeProject);
    const chartEntries = entries.slice(0, 6);
    const remainder = entries.slice(6).reduce((sum, [, value]) => sum + value, 0);
    if (remainder) chartEntries.push(["Other", remainder]);
    if (projectChart) projectChart.destroy();
    projectChart = new Chart(document.getElementById("project-chart"), { type: "doughnut", data: { labels: chartEntries.map(([label]) => label), datasets: [{ data: chartEntries.map(([, value]) => value), backgroundColor: palette, borderWidth: 0, hoverOffset: 5 }] }, options: { responsive: true, maintainAspectRatio: false, cutout: "70%", plugins: { legend: { display: false }, tooltip: { callbacks: { label: context => ` ${context.label}: ${hours(context.raw)}` } } } } });
    document.getElementById("project-legend").innerHTML = chartEntries.map(([label, value], index) => `<div class="legend-row"><span class="legend-label" style="--legend-color:${palette[index]}">${label}</span><span class="legend-value">${hours(value)}</span></div>`).join("");
}

function renderProjectTrend() {
    const months = Object.keys(dashboardData.monthly_projects).slice(-12);
    const projects = activeProject ? [activeProject] : Object.keys(dashboardData.projects).slice(0, 5);
    const datasets = projects.map((project, index) => ({
        label: project,
        data: months.map(month => dashboardData.monthly_projects[month][project] || 0),
        backgroundColor: palette[index],
        borderWidth: 0,
        borderRadius: 2,
    }));
    if (projectTrendChart) projectTrendChart.destroy();
    projectTrendChart = new Chart(document.getElementById("project-trend-chart"), { type: "bar", data: { labels: months, datasets }, options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false }, plugins: { legend: { display: true, position: "bottom", labels: { color: "#66777a", boxWidth: 10, font: { family: "DM Mono", size: 10 } } }, tooltip: { callbacks: { label: context => ` ${context.dataset.label}: ${hours(context.raw)}` } } }, scales: { x: { stacked: true, grid: { display: false }, ticks: { color: "#66777a", font: { family: "DM Mono", size: 10 } } }, y: { stacked: true, beginAtZero: true, grid: { color: "#e1e5df" }, ticks: { color: "#66777a", font: { family: "DM Mono", size: 10 } } } } } });
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
    const rows = Object.entries(dashboardData.projects).filter(([name]) => (!activeProject || name === activeProject) && name.toLowerCase().includes(filter.toLowerCase()));
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
    const deepWorkSessions = (dashboardData.session_buckets["2-4 hours"] || 0) + (dashboardData.session_buckets["4+ hours"] || 0);
    const averageDay = days.length ? days.reduce((sum, value) => sum + value, 0) / days.length : 0;
    const dayVariation = days.length ? Math.sqrt(days.reduce((sum, value) => sum + ((value - averageDay) ** 2), 0) / days.length) : 0;
    const signals = [
        ["Target hit rate", `${days.length ? ((targetDays / days.length) * 100).toFixed(0) : 0}%`, `${targetDays} of ${days.length} active days`],
        ["Current streak", `${streak} day${streak === 1 ? "" : "s"}`, "consecutive logged days"],
        ["Longest session", hours(longest.hours), `${longest.date} / ${longest.project}`],
        ["Busiest day", hours(busiest ? busiest[1] : 0), busiest ? busiest[0] : "No data"],
        ["Deep-work share", `${dashboardData.session_count ? ((deepWorkSessions / dashboardData.session_count) * 100).toFixed(0) : 0}%`, "sessions lasting 2+ hours"],
        ["Day variation", `±${hours(dayVariation)}`, "standard deviation per active day"],
        ["Blocks per day", (dashboardData.session_count / (days.length || 1)).toFixed(1), "average sessions per active day"],
        ["Context load", (dashboardData.project_count / (days.length || 1)).toFixed(2), "projects per active day"],
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

function renderDayStructure() {
    const keys = Object.keys(dashboardData.daily_sessions).slice(-30);
    const labels = labelsFor(keys, "daily");
    const countOptions = {
        ...makeChartOptions(),
        plugins: { ...makeChartOptions().plugins, tooltip: { callbacks: { label: context => ` ${context.raw} sessions` } } },
    };
    cadenceChart = new Chart(document.getElementById("cadence-chart"), { type: "bar", data: { labels, datasets: [{ data: keys.map(key => dashboardData.daily_sessions[key]), backgroundColor: "#efc85b", borderRadius: 2, maxBarThickness: 28 }] }, options: countOptions });
    breadthChart = new Chart(document.getElementById("breadth-chart"), { type: "bar", data: { labels, datasets: [{ data: keys.map(key => dashboardData.daily_projects[key] || 0), backgroundColor: "#8b6b9b", borderRadius: 2, maxBarThickness: 28 }] }, options: { ...countOptions, plugins: { ...countOptions.plugins, tooltip: { callbacks: { label: context => ` ${context.raw} projects` } } } } });
}

function countWeekdays(start, end) {
    let count = 0;
    for (const cursor = new Date(start); cursor <= end; cursor.setDate(cursor.getDate() + 1)) {
        if (cursor.getDay() !== 0 && cursor.getDay() !== 6) count += 1;
    }
    return count;
}

function renderForecast() {
    const latestKey = Object.keys(dashboardData.daily).at(-1);
    const latestDate = new Date(`${latestKey}T12:00:00`);
    const monthStart = new Date(latestDate.getFullYear(), latestDate.getMonth(), 1, 12);
    const monthEnd = new Date(latestDate.getFullYear(), latestDate.getMonth() + 1, 0, 12);
    const elapsedWeekdays = countWeekdays(monthStart, latestDate);
    const monthWeekdays = countWeekdays(monthStart, monthEnd);
    const monthKey = latestKey.slice(0, 7);
    const monthHours = dashboardData.monthly[monthKey] || 0;
    const expected = monthWeekdays * dashboardData.target_hours_per_day;
    const projected = elapsedWeekdays ? (monthHours / elapsedWeekdays) * monthWeekdays : 0;
    const weeks = Object.values(dashboardData.weekly).slice(-4);
    const averageWeek = weeks.length ? weeks.reduce((sum, value) => sum + value, 0) / weeks.length : 0;
    const progress = monthWeekdays ? (elapsedWeekdays / monthWeekdays) * 100 : 0;
    const cards = [
        ["Logged this month", hours(monthHours), `${elapsedWeekdays} workdays elapsed`],
        ["Projected finish", hours(projected), `pace vs ${hours(expected)} target`],
        ["Projected variance", `${projected - expected >= 0 ? "+" : ""}${hours(projected - expected)}`, "pace above / below target"],
        ["Average recent week", hours(averageWeek), "last four logged weeks"],
    ];
    document.getElementById("forecast-grid").innerHTML = cards.map(([label, value, note]) => `<article class="forecast-card"><span>${label}</span><strong>${value}</strong><small>${note}</small></article>`).join("");
    document.getElementById("forecast-progress").style.width = `${Math.min(progress, 100)}%`;
    document.getElementById("forecast-progress-label").textContent = `${Math.round(progress)}% of workdays`;
    document.getElementById("forecast-start").textContent = monthStart.toISOString().slice(0, 10);
    document.getElementById("forecast-end").textContent = monthEnd.toISOString().slice(0, 10);
}

function renderRecent() {
    document.getElementById("recent-sessions").innerHTML = dashboardData.sessions.map(session => `<tr><td>${session.date}</td><td>${session.project}</td><td class="numeric">${hours(session.hours)}</td></tr>`).join("");
}

function updateControlStatus() {
    const rangeLabel = activeRange === "all" ? "all history" : `last ${activeRange} days`;
    const projectLabel = activeProject || "all projects";
    document.getElementById("control-status").textContent = `Showing ${projectLabel} / ${rangeLabel}`;
}

function populateProjectFocus() {
    const select = document.getElementById("project-focus");
    Object.keys(dashboardData.projects).forEach(project => {
        const option = document.createElement("option");
        option.value = project;
        option.textContent = project;
        select.appendChild(option);
    });
}

async function start() {
    const dataUrl = new URL("assets/dashboard-data.json", window.location.href);
    dataUrl.searchParams.set("v", document.lastModified);
    dashboardData = await fetch(dataUrl).then(response => {
        if (!response.ok) throw new Error(`Dashboard data request failed: ${response.status}`);
        return response.json();
    });
    dashboardData = normaliseDashboardData(dashboardData);
    populateProjectFocus();
    document.getElementById("total-hours").textContent = hours(dashboardData.total_hours);
    document.getElementById("session-count").textContent = dashboardData.session_count;
    document.getElementById("active-days").textContent = dashboardData.active_days;
    document.getElementById("average-day").textContent = hours(dashboardData.total_hours / dashboardData.active_days);
    document.getElementById("average-session").textContent = hours(dashboardData.session_stats.average);
    document.getElementById("median-session").textContent = hours(dashboardData.session_stats.median);
    document.getElementById("project-count").textContent = dashboardData.project_count;
    document.getElementById("weekend-share").textContent = `${dashboardData.total_hours ? ((dashboardData.weekend_hours / dashboardData.total_hours) * 100).toFixed(1) : 0}%`;
    document.getElementById("updated").textContent = `UPDATED ${dashboardData.generated_at.replace("T", " ")}`;
    renderTrend(); renderProjects(); renderProjectTrend(); renderWeekdays(); renderTarget(); renderSessionShape(); renderProjectTable(); renderSignals(); renderHeatmap(); renderStartTimes(); renderDayStructure(); renderForecast(); renderRecent();
    document.querySelectorAll(".period-button").forEach(button => button.addEventListener("click", () => { document.querySelector(".period-button.is-active").classList.remove("is-active"); button.classList.add("is-active"); renderTrend(button.dataset.period); }));
    document.getElementById("project-filter").addEventListener("input", event => renderProjectTable(event.target.value));
    document.getElementById("range-filter").addEventListener("change", event => { activeRange = event.target.value; updateControlStatus(); renderTrend(); });
    document.getElementById("project-focus").addEventListener("change", event => { activeProject = event.target.value; updateControlStatus(); renderProjects(); renderProjectTrend(); renderProjectTable(document.getElementById("project-filter").value); });
    updateControlStatus();
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