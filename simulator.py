import heapq
import random
from typing import Any, List, Dict, Optional
import truck
import event
class Simulator:
    def __init__(self, params: Dict, seed: int = 42, trace: bool = False):
        self.params = params
        self.now = 0.0
        self.events: List[event.Event] = []
        self.event_counter = 0  # tie-breaker for heap
        self.rng = random.Random(seed)
        self.trace = trace

        # state
        self.piles = params.get("initial_piles", 0)
        self.bulldozer_busy_until = 0.0  # for utilization accounting
        self.bulldozer_last_start = None
        self.loaders_total = params.get("num_loaders", 2)
        self.loaders_busy = 0
        self.loaders_busy_start_times: List[float] = []  # start times when loader becomes busy (for utilization)
        self.trucks = [truck.Truck(i) for i in range(params.get("num_trucks", 4))]

        # stats
        self.total_loaded_trucks = 0
        self.sum_cycle_times = 0.0
        self.bulldozer_work_time = 0.0
        self.loader_work_time = 0.0
        self.last_time = 0.0

        # for report
        self.samples = []

        # init
        self.schedule_initial_events()

    def log(self, msg):
        if self.trace:
            print(f"[{self.now:8.3f}] {msg}")

    def push_event(self, time: float, action: str, payload: Any = None, priority: int = 0):
        self.event_counter += 1
        heapq.heappush(self.events, event.Event(time, priority, action, payload))

    def schedule_initial_events(self):
        # first bulldozer
        t = self.now + self.draw_bulldozer_interval()
        self.push_event(t, "bulldozer_made_pile")

        # init trucks
        for truck in self.trucks:
            truck.state = "waiting"
            truck.cycle_start_time = self.now

        # Schedule first periodic report (discrete-time response)
        report_interval = self.params.get("report_interval", 5.0)
        self.push_event(self.now + report_interval, "report", {"interval": report_interval})

    # generators
    def draw_bulldozer_interval(self) -> float:
        min_t, max_t = self.params.get("bulldozer_time_range", (6.0, 12.0))
        return self.rng.uniform(min_t, max_t)

    def draw_loading_time(self) -> float:
        min_t, max_t = self.params.get("loading_time_range", (4.0, 8.0))
        return self.rng.uniform(min_t, max_t)

    def draw_travel_to_dump(self) -> float:
        min_t, max_t = self.params.get("travel_to_dump_range", (3.0, 6.0))
        return self.rng.uniform(min_t, max_t)

    def draw_unloading_time(self) -> float:
        min_t, max_t = self.params.get("unloading_time_range", (2.0, 4.0))
        return self.rng.uniform(min_t, max_t)

    def draw_return_time(self) -> float:
        min_t, max_t = self.params.get("return_time_range", (3.0, 6.0))
        return self.rng.uniform(min_t, max_t)

    # event handlers
    def handle_bulldozer_made_pile(self, ev):
        # create pile
        self.log("Bulldozer created a pile")
        # work amount for report
        work_per_push = self.params.get("bulldozer_work_per_push", 1)
        self.bulldozer_work_time += work_per_push

        self.piles += 1
        # try to start loading if possible
        self.try_start_loading()

        # schedule next pile creation
        next_t = self.now + self.draw_bulldozer_interval()
        self.push_event(next_t, "bulldozer_made_pile")

    def try_start_loading(self):

        # while possible and resources available, start as many loadings as possible
        started = 0
        for truck in self.trucks:
            if self.loaders_busy >= self.loaders_total:
                break
            if self.piles >= 2 and truck.state == "waiting":
                # start loading
                self.start_loading(truck)
                started += 1
        if started:
            self.log(f"Attempted starts -> {started} loadings started")

    def start_loading(self, truck: truck.Truck):
        truck.state = "loading"
        truck.last_loaded_time = None
        truck.total_cycles += 1
        # consume two piles
        self.piles -= 2
        self.loaders_busy += 1
        # record loader busy start
        self.loaders_busy_start_times.append(self.now)
        self.log(f"Truck {truck.id} started loading (piles left: {self.piles})")

        load_time = self.draw_loading_time()
        self.push_event(self.now + load_time, "finish_loading", {"truck_id": truck.id, "duration": load_time})

    def handle_finish_loading(self, ev):
        payload = ev
        truck_id = payload["truck_id"]
        dur = payload.get("duration", None)
        truck = self.trucks[truck_id]
        truck.state = "traveling"
        truck.last_loaded_time = self.now

        # loader free
        self.loaders_busy -= 1
        start_time = None
        if self.loaders_busy_start_times:
            start_time = self.loaders_busy_start_times.pop(0)
            self.loader_work_time += (self.now - start_time)
        self.log(f"Truck {truck.id} finished loading (load dur {dur:.3f}). Loaders busy: {self.loaders_busy}")

        # schedule travel to dump completion
        travel = self.draw_travel_to_dump()
        self.push_event(self.now + travel, "arrive_dump", {"truck_id": truck.id, "travel": travel})

        # after freeing loader, maybe other waiting trucks can start loading
        self.try_start_loading()

    def handle_arrive_dump(self, ev):
        truck_id = ev["truck_id"]
        truck = self.trucks[truck_id]
        truck.state = "unloading"
        self.log(f"Truck {truck.id} arrived at dump and starts unloading")
        unload = self.draw_unloading_time()
        self.push_event(self.now + unload, "finish_unloading", {"truck_id": truck.id, "unload": unload})

    def handle_finish_unloading(self, ev):
        truck_id = ev["truck_id"]
        truck = self.trucks[truck_id]
        truck.state = "returning"
        self.log(f"Truck {truck.id} finished unloading, returning empty")
        # truck cycle complete: record cycle time
        if truck.cycle_start_time is not None:
            cycle_time = self.now - truck.cycle_start_time
            self.total_loaded_trucks += 1
            self.sum_cycle_times += cycle_time
            self.log(f"Truck {truck.id} cycle time: {cycle_time:.3f}")
            # reset cycle start (it will be set when returns and waits again)
            truck.cycle_start_time = None

        ret = self.draw_return_time()
        self.push_event(self.now + ret, "truck_returned", {"truck_id": truck.id, "ret": ret})

    def handle_truck_returned(self, ev):
        truck_id = ev["truck_id"]
        truck = self.trucks[truck_id]
        truck.state = "waiting"
        truck.cycle_start_time = self.now
        self.log(f"Truck {truck.id} returned and is waiting for load")
        # perhaps we can start loading now
        self.try_start_loading()

    def handle_report(self, ev):
        interval = ev["interval"]
        # sample interesting variables (discrete-time response)
        sample = {
            "time": self.now,
            "piles": self.piles,
            "loaders_busy": self.loaders_busy,
            "trucks_states": [t.state for t in self.trucks],
            "total_loaded_trucks": self.total_loaded_trucks
        }
        self.samples.append(sample)
        self.log(f"REPORT: piles={self.piles}, loaders_busy={self.loaders_busy}, loaded={self.total_loaded_trucks}")
        # schedule next report
        self.push_event(self.now + interval, "report", {"interval": interval})

    # main loop
    def run(self, until: float = None, max_loaded: Optional[int] = None):
        stop_time = until if until is not None else float('inf')
        while self.events:
            ev = heapq.heappop(self.events)
            # advance time
            if ev.time > stop_time:
                self.now = stop_time
                break
            self.now = ev.time
            action = ev.action
            payload = ev.payload or {}
            # dispatch
            if action == "bulldozer_made_pile":
                self.handle_bulldozer_made_pile(payload)
            elif action == "finish_loading":
                self.handle_finish_loading(payload)
            elif action == "arrive_dump":
                self.handle_arrive_dump(payload)
            elif action == "finish_unloading":
                self.handle_finish_unloading(payload)
            elif action == "truck_returned":
                self.handle_truck_returned(payload)
            elif action == "report":
                self.handle_report(payload)
            else:
                self.log(f"Unknown event {action}")

            # stopping condition by number of loaded trucks
            if max_loaded is not None and self.total_loaded_trucks >= max_loaded:
                self.log(f"Reached target total_loaded_trucks={self.total_loaded_trucks}, stopping.")
                break

        # calculating result work time for loaders
        # + partial time if work not finished
        while self.loaders_busy_start_times:
            start = self.loaders_busy_start_times.pop(0)
            self.loader_work_time += max(0.0, self.now - start)
        # bulldozer_work_time recorded approximately per push; OK for rough metric

        return self.report_results()

    # Reporting
    def report_results(self):
        avg_cycle = (self.sum_cycle_times / self.total_loaded_trucks) if self.total_loaded_trucks > 0 else None
        loader_util = (self.loader_work_time / self.now) / max(1, self.loaders_total) if self.now > 0 else None
        bulldozer_util = (self.bulldozer_work_time / self.now) if self.now > 0 else None
        result = {
            "sim_time": self.now,
            "total_loaded_trucks": self.total_loaded_trucks,
            "avg_cycle_time": avg_cycle,
            "loader_utilization_per_machine": loader_util,
            "bulldozer_utilization": bulldozer_util,
            "final_piles": self.piles,
            "samples": self.samples,
            "trucks_states": [t.state for t in self.trucks]
        }
        return result
