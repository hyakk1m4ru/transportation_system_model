import heapq
import random

from event import Event


class Simulation:
    def __init__(self, params):
        self.t = 0.0
        self.last_t = 0.0
        self.events = []
        self.params = params

        self.stats = {
            "delivered_heaps": 0,
            "orders_completed": 0,
            "trips": 0,
            # time series sampled at event times: list of (time, value)
            "busy_trucks": [],
            "busy_loaders": [],
            "bulldozer_busy": [],
            "avg_prep_time": [],
        }

        self.resources = {"bulldozer": 1, "loaders": 2, "trucks": 4}
        self.busy = {"bulldozer": 0, "loaders": 0, "trucks": 0}
        self.area_busy = {r: 0.0 for r in self.resources}  # интеграл занятости по времени (unit-seconds)
        self.heaps = 0
        self.orders = []
        self.active_orders = {}
        self.stop_flag = False

    def schedule(self, delay, event_type, func, *args):
        heapq.heappush(self.events, Event(self.t + delay, event_type, func, *args))

    def trace(self, msg):
        if self.params.get("tracing"):
            print(f"[{self.t:.1f}] {msg}")

    def trace_state(self):
        if self.params.get("tracing"):
            self.trace(
                f"Состояние: занятых самосвалов={self.busy['trucks']}, "
                f"погрузчиков={self.busy['loaders']}, "
                f"бульдозер={self.busy['bulldozer']}"
            )

    def sample(self, mean):
        return random.expovariate(1.0 / mean)

    def record_state(self):
        # сохраняем снимок состояния в момент времени self.t
        self.stats["busy_trucks"].append((self.t, self.busy["trucks"]))
        self.stats["busy_loaders"].append((self.t, self.busy["loaders"]))
        self.stats["bulldozer_busy"].append((self.t, self.busy["bulldozer"]))

    # -------------------- ПРОЦЕССЫ --------------------

    def start(self):
        self.schedule(0, "order_arrival", self.order_arrival)
        self.schedule(0, "heap_formation", self.form_heap)
        self.record_state()
        self.last_t = self.t

        while self.events and self.t < self.params["SIM_TIME"] and not self.stop_flag:
            ev = heapq.heappop(self.events)
            # интегрируем занятость за интервал [self.t, ev.time)
            dt = max(0.0, ev.time - self.t)
            if dt > 0:
                for r in self.busy:
                    # area_busy хранит суммарное число занятых единиц * время
                    self.area_busy[r] += self.busy[r] * dt
            # продвигаем время
            self.t = ev.time
            ev.func(*ev.args)
            self.record_state()
            self.last_t = self.t

        # учесть остаток времени до конца моделирования (если нужно)
        if self.t < self.params["SIM_TIME"]:
            dt = self.params["SIM_TIME"] - self.t
            for r in self.busy:
                self.area_busy[r] += self.busy[r] * dt
            self.t = self.params["SIM_TIME"]
            self.record_state()

        self.finish()

    def order_arrival(self):
        if len(self.orders) >= self.params["MAX_ORDERS"]:
            self.trace("Достигнут лимит заказов, новые не создаются")
            return

        order_id = len(self.orders)
        n_heaps = random.randint(3, 7)
        self.orders.append(n_heaps)
        self.active_orders[order_id] = {"required": n_heaps, "done": 0, "start": self.t}
        self.trace(f"Новый заказ {order_id}: {n_heaps} куч")
        self.try_loading()

        if len(self.orders) < self.params["MAX_ORDERS"]:
            self.schedule(
                self.sample(self.params["order_interarrival_mean"]),
                "order_arrival",
                self.order_arrival,
            )

    def form_heap(self):
        if self.busy["bulldozer"] < self.resources["bulldozer"]:
            self.busy["bulldozer"] = 1
            delay = self.sample(self.params["heap_formation_mean"])
            self.schedule(delay, "heap_ready", self.heap_ready)
            self.trace("Бульдозер формирует кучу")
            self.trace_state()
            # записать состояние сразу после изменения
            self.record_state()
        else:
            self.trace("Бульдозер занят")

    def heap_ready(self):
        self.busy["bulldozer"] = 0
        self.heaps += 1
        self.trace(f"Новая куча готова, всего куч: {self.heaps}")
        # записать состояние сразу после изменения
        self.record_state()
        self.try_loading()
        self.schedule(0, "heap_formation", self.form_heap)

    def try_loading(self):
        # запускаем загрузки, пока есть ресурсы, груды и заказы
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
        self.trace_state()
        self.record_state()

    def loading_done(self, order_id):
        self.busy["loaders"] -= 1
        # изменили состояние — записать
        self.record_state()
        travel_time = self.sample(self.params["travel_time_mean"]) if self.params["stochastic_travel"] else self.params["travel_time_mean"]
        self.trace(f"Самосвал {order_id}-го заказа выехал к месту разгрузки, время в пути {travel_time:.1f}")
        self.schedule(travel_time, "truck_arrive", self.truck_arrive, order_id)

    def truck_arrive(self, order_id):
        self.trace(f"Самосвал {order_id}-го заказа прибыл к месту разгрузки")
        self.stats["delivered_heaps"] += 2
        unload_time = 5  # фиксированное или случайное время разгрузки
        self.trace(f"Самосвал {order_id}-го заказа разгружается, время разгрузки {unload_time}")
        self.schedule(unload_time, "truck_return", self.truck_return, order_id)

    def truck_return(self, order_id):
        self.busy["trucks"] -= 1
        self.trace(f"Самосвал {order_id}-го заказа вернулся и освобождён")
        self.stats["delivered_heaps"] += 2
        self.stats["trips"] += 1
        # записать состояние после изменения
        self.record_state()

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

            # если достигнуто нужное число завершённых заказов — остановка моделирования
            if self.stats["orders_completed"] >= self.params["MAX_ORDERS"]:
                self.trace("Достигнуто максимальное число выполненных заказов. Симуляция завершается.")
                self.stop_flag = True
                return

        self.try_loading()

    def finish(self):
        # среднее время подготовки
        if self.stats["avg_prep_time"]:
            self.stats["avg_prep_time_mean"] = sum(self.stats["avg_prep_time"]) / len(self.stats["avg_prep_time"])
        else:
            self.stats["avg_prep_time_mean"] = float("nan")

        # средняя загрузка по времени (fraction of total capacity)
        utilization = {}
        sim_time = float(self.params["SIM_TIME"])
        for r in self.resources:
            # превращаем unit-seconds в долю от (resources[r] * SIM_TIME)
            utilization[r] = self.area_busy[r] / (self.resources[r] * sim_time)
        self.stats["utilization"] = utilization