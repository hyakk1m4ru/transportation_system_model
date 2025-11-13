import random
import heapq
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from simulator import Simulation

# ------------------------ ПАРАМЕТРЫ ------------------------
params = {
    "SIM_TIME": 5000,
    "N_REPLICATIONS": 5,
    "MAX_ORDERS": 10,  # количество заказов на один прогон
    "heap_formation_mean": 5,
    "order_interarrival_mean": 50,
    "loading_time_mean": 10,
    "travel_time_mean": 40,
    "stochastic_loading": True,
    "stochastic_travel": True,
    "tracing": True,
}

# ------------------------ БАЗОВЫЙ СИМУЛЯТОР ------------------------


# ------------------------ ЭКСПЕРИМЕНТ ------------------------
def run_experiments(params):
    runs = []
    for r in range(params["N_REPLICATIONS"]):
        sim = Simulation(params)
        sim.start()
        runs.append(sim.stats)
    return runs

runs = run_experiments(params)

# ------------------------ АНАЛИЗ ------------------------
df_summary = pd.DataFrame(
    [
        {
            "delivered_heaps": r["delivered_heaps"],
            "trips": r["trips"],
            "orders_completed": r["orders_completed"],
            "avg_prep_time": r["avg_prep_time_mean"],
            "bulldozer_util": r["utilization"]["bulldozer"],
            "loaders_util": r["utilization"]["loaders"],
            "trucks_util": r["utilization"]["trucks"],
        }
        for r in runs
    ]
)

def mean_ci(vals):
    n = len(vals)
    m = sum(vals) / n
    if n <= 1:
        return m, m, m
    s = (sum((v - m) ** 2 for v in vals) / (n - 1)) ** 0.5
    h = 1.96 * s / (n ** 0.5)
    return m, m - h, m + h

metrics = {
    "delivered_heaps_mean_ci": mean_ci(df_summary["delivered_heaps"]),
    "trips_mean_ci": mean_ci(df_summary["trips"]),
    "orders_completed_mean_ci": mean_ci(df_summary["orders_completed"]),
    "avg_prep_time_mean_ci": mean_ci(
        [x for x in df_summary["avg_prep_time"] if not math.isnan(x)]
    ),
    "bulldozer_util_mean_ci": mean_ci(df_summary["bulldozer_util"]),
    "loaders_util_mean_ci": mean_ci(df_summary["loaders_util"]),
    "trucks_util_mean_ci": mean_ci(df_summary["trucks_util"]),
}
rep = runs[0]
window_seconds = 50  # окно скользящего среднего

# максимальное время события в первой симуляции
max_time = 1000
# создаём сетку от 0 до фактического конца событий
time_grid = np.linspace(0, max_time, len(rep["busy_trucks"]))  # можно взять длину любого списка событий

def series_from_event_list(event_list, grid):
    if not event_list:
        return pd.Series(0, index=grid)
    times, values = zip(*event_list)
    s = pd.Series(values, index=pd.Index(times))
    s = s[~s.index.duplicated(keep='last')]
    s_grid = s.reindex(grid, method='ffill').fillna(0)
    return s_grid

plt.rcParams.update({"figure.figsize": (10, 4)})

for name, evt_key in [("Trucks busy", "busy_trucks"),
                       ("Loaders busy", "busy_loaders"),
                       ("Bulldozer busy", "bulldozer_busy")]:
    s_grid = series_from_event_list(rep[evt_key], time_grid)
    # окно скользящего среднего в точках
    points = max(1, int(window_seconds * len(time_grid) / max_time))
    rolling = s_grid.rolling(window=points, min_periods=1).mean()

    plt.figure()
    plt.step(time_grid, s_grid, where='post', label="Instant (step)", linewidth=1)
    plt.plot(time_grid, rolling, linewidth=2, label=f"Rolling mean ({window_seconds}s)")
    plt.xlabel("Time")
    plt.ylabel(name)
    plt.title(f"Time series: {name}")
    plt.grid(True, linestyle=':', linewidth=0.6)
    plt.legend()
    plt.tight_layout()
    plt.show()

# ------------------------ РЕЗУЛЬТАТЫ ------------------------
print("Aggregated metrics (mean, 95% CI):")
for k, (m, l, u) in metrics.items():
    print(f"{k}: mean={m:.4f}, CI=[{l:.4f}, {u:.4f}]")
