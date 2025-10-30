import random
import heapq
import math
import pandas as pd
import matplotlib.pyplot as plt

# ------------------------ ПАРАМЕТРЫ ------------------------
params = {
    "SIM_TIME": 500,  # мин
    "N_REPLICATIONS": 2,
    "heap_formation_mean": 5,  # среднее время формирования кучи
    "order_interarrival_mean": 50,  # среднее время между заказами
    "loading_time_mean": 10,
    "travel_time_mean": 40,
    "stochastic_loading": True,
    "stochastic_travel": True,
    "tracing": True,
}

# ------------------------ БАЗОВЫЙ СИМУЛЯТОР ------------------------
class Event:
    def __init__(self, time, event_type, func, *args):
        self.time = time
        self.type = event_type
        self.func = func
        self.args = args

    def __lt__(self, other):
        return self.time < other.time

class Simulation:
    def __init__(self, params):
        self.t = 0
        self.events = []
        self.params = params
        self.stats = {
            "delivered_heaps": 0,
            "orders_completed": 0,
            "trips": 0,
            "busy_trucks": [],
            "busy_loaders": [],
            "bulldozer_busy": [],
            "avg_prep_time": [],
        }
        self.resources = {"bulldozer": 1, "loaders": 2, "trucks": 4}
        self.busy = {"bulldozer": 0, "loaders": 0, "trucks": 0}
        self.heaps = 0
        self.orders = []
        self.active_orders = {}

    def schedule(self, delay, event_type, func, *args):
        heapq.heappush(self.events, Event(self.t + delay, event_type, func, *args))

    def trace(self, msg):
        if self.params["tracing"]:
            print(f"[{self.t:.1f}] {msg}")

    def sample(self, mean):
        return random.expovariate(1.0 / mean)

    def record_state(self):
        self.stats["busy_trucks"].append((self.t, self.busy["trucks"]))
        self.stats["busy_loaders"].append((self.t, self.busy["loaders"]))
        self.stats["bulldozer_busy"].append((self.t, self.busy["bulldozer"]))

    # -------------------- ПРОЦЕССЫ --------------------
    def start(self):
        self.schedule(0, "order_arrival", self.order_arrival)
        self.schedule(0, "heap_formation", self.form_heap)
        self.record_state()

        while self.events and self.t < self.params["SIM_TIME"]:
            ev = heapq.heappop(self.events)
            self.t = ev.time
            ev.func(*ev.args)
            self.record_state()

        self.finish()

    def order_arrival(self):
        order_id = len(self.orders)
        n_heaps = random.randint(3, 7)
        self.orders.append(n_heaps)
        self.active_orders[order_id] = {"required": n_heaps, "done": 0, "start": self.t}
        self.trace(f"Новый заказ {order_id}: {n_heaps} куч")
        self.try_loading()
        self.schedule(self.sample(self.params["order_interarrival_mean"]), "order_arrival", self.order_arrival)

    def form_heap(self):
        if self.busy["bulldozer"] < self.resources["bulldozer"]:
            self.busy["bulldozer"] = 1
            delay = self.sample(self.params["heap_formation_mean"])
            self.schedule(delay, "heap_ready", self.heap_ready)
            self.trace("Бульдозер формирует кучу")
        else:
            self.trace("Бульдозер занят")

    def heap_ready(self):
        self.busy["bulldozer"] = 0
        self.heaps += 1
        self.trace(f"Новая куча готова, всего куч: {self.heaps}")
        self.try_loading()
        self.schedule(0, "heap_formation", self.form_heap)

    def try_loading(self):
        while (
            self.busy["loaders"] < self.resources["loaders"]
            and self.busy["trucks"] < self.resources["trucks"]
            and self.heaps >= 2
            and any(o["done"] < o["required"] for o in self.active_orders.values())
        ):
            self.start_loading()

    def start_loading(self):
        order_id = next(k for k, o in self.active_orders.items() if o["done"] < o["required"])
        self.busy["loaders"] += 1
        self.busy["trucks"] += 1
        self.heaps -= 2
        delay = (
            self.sample(self.params["loading_time_mean"])
            if self.params["stochastic_loading"]
            else self.params["loading_time_mean"]
        )
        self.schedule(delay, "loading_done", self.loading_done, order_id)
        self.trace(f"Начата загрузка для заказа {order_id}")

    def loading_done(self, order_id):
        self.busy["loaders"] -= 1
        travel_time = self.sample(self.params["travel_time_mean"])
        self.trace(f"Самосвал {order_id} выехал к месту разгрузки, время в пути {travel_time:.1f}")
        self.schedule(travel_time, "truck_arrive", self.truck_arrive, order_id)

    def truck_arrive(self, order_id):
        self.trace(f"Самосвал {order_id} прибыл к месту разгрузки")
        self.stats["delivered_heaps"] += 2
        unload_time = 5  # фиксированное или случайное время разгрузки
        self.trace(f"Самосвал {order_id} разгружается, время разгрузки {unload_time}")
        self.schedule(unload_time, "truck_return", self.truck_return, order_id)

    def truck_return(self, order_id):
        self.busy["trucks"] -= 1
        self.trace(f"Самосвал {order_id} вернулся и освобождён")
        self.stats["delivered_heaps"] += 2
        self.stats["trips"] += 1

        if order_id not in self.active_orders:
            self.try_loading()
            return

        order = self.active_orders[order_id]
        order["done"] += 2

        if order["done"] >= order["required"]:
            self.stats["orders_completed"] += 1
            prep_time = self.t - order["start"]
            self.stats["avg_prep_time"].append(prep_time)
            self.trace(f"Заказ {order_id} завершён, время подготовки {prep_time:.1f}")
            del self.active_orders[order_id]

        self.try_loading()

    def finish(self):
        if self.stats["avg_prep_time"]:
            self.stats["avg_prep_time_mean"] = sum(self.stats["avg_prep_time"]) / len(
                self.stats["avg_prep_time"]
            )
        else:
            self.stats["avg_prep_time_mean"] = float("nan")

        total_busy = sum(v for _, v in self.stats["bulldozer_busy"])
        self.stats["bulldozer_util"] = total_busy / self.params["SIM_TIME"]

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
            "bulldozer_util": r["bulldozer_util"],
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
}

# ------------------------ ВИЗУАЛИЗАЦИЯ ------------------------
# rep = runs[0]
# for key in ["busy_trucks", "busy_loaders", "bulldozer_busy"]:
#     plt.figure()
#     t, y = zip(*rep[key])
#     plt.step(t, y, where="post")
#     plt.xlabel("Время")
#     plt.ylabel(key)
#     plt.title(f"Динамика {key}")
#     plt.grid(True)
#     plt.show()
#
# df_summary.boxplot()
# plt.title("Результаты по прогону")
# plt.grid(True)
# plt.show()

print("Aggregated metrics (mean, 95% CI):")
for k, (m, l, u) in metrics.items():
    print(f"{k}: mean={m:.2f}, CI=[{l:.2f}, {u:.2f}]")
