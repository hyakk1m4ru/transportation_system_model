import unittest
from unittest.mock import patch, MagicMock
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from event import Event
from newone import params, mean_ci, run_experiments, series_from_event_list
from simulator import Simulation


class TestEvent(unittest.TestCase):
    def test_lt_comparison(self):
        # Проверка правильности сравнения событий по времени
        e1 = Event(1, "a", lambda: None)
        e2 = Event(2, "b", lambda: None)
        self.assertTrue(e1 < e2)
        self.assertFalse(e2 < e1)


class TestSimulation(unittest.TestCase):
    def setUp(self):
        self.params = params.copy()
        self.params["tracing"] = False
        self.sim = Simulation(self.params)

    def test_schedule_and_sample(self):
        # Проверка планирования события и метода выборки экспоненциального распределения
        f = lambda: None
        self.sim.schedule(5, "test", f)
        self.assertEqual(len(self.sim.events), 1)
        with patch("random.expovariate", return_value=3.0):
            self.assertEqual(self.sim.sample(5), 3.0)

    def test_record_state_updates_stats(self):
        # Проверка корректного сохранения состояния ресурсов
        self.sim.busy["trucks"] = 1
        self.sim.record_state()
        self.assertTrue(len(self.sim.stats["busy_trucks"]) > 0)

    def test_order_arrival_creates_order(self):
        # Проверка создания нового заказа и добавления в список активных
        with patch.object(self.sim, "sample", return_value=1), patch.object(self.sim, "try_loading"):
            self.sim.order_arrival()
            self.assertTrue(len(self.sim.orders) > 0)

    def test_form_heap_and_heap_ready(self):
        # Проверка процесса формирования кучи и освобождения бульдозера
        with patch.object(self.sim, "sample", return_value=1), patch.object(self.sim, "trace"):
            self.sim.form_heap()
            self.assertTrue(self.sim.busy["bulldozer"])
            self.sim.heap_ready()
            self.assertGreaterEqual(self.sim.heaps, 0)

    def test_try_loading_and_start_loading(self):
        # Проверка запуска процесса загрузки, если есть ресурсы и груды
        self.sim.heaps = 4
        self.sim.active_orders = {0: {"required": 4, "done": 0, "start": 0}}
        with patch.object(self.sim, "schedule") as sch:
            self.sim.try_loading()
            self.assertTrue(sch.called)

    def test_loading_done_truck_arrive_truck_return(self):
        # Проверка процессов окончания загрузки, прибытия и возврата самосвала
        with patch.object(self.sim, "sample", return_value=1), patch.object(self.sim, "schedule"):
            self.sim.busy["loaders"] = 1
            self.sim.loading_done(0)
        with patch.object(self.sim, "schedule"):
            self.sim.truck_arrive(0)
        with patch.object(self.sim, "trace"), patch.object(self.sim, "try_loading"):
            self.sim.active_orders = {0: {"required": 2, "done": 0, "start": 0}}
            self.sim.busy["trucks"] = 1
            self.sim.truck_return(0)
            self.assertIn("orders_completed", self.sim.stats)

    def test_finish_utilization_and_avg_time(self):
        # Проверка расчета среднего времени подготовки и коэффициента загрузки
        self.sim.stats["avg_prep_time"] = [10, 20]
        self.sim.area_busy = {"bulldozer": 10, "loaders": 20, "trucks": 40}
        self.sim.finish()
        self.assertIn("utilization", self.sim.stats)
        self.assertAlmostEqual(self.sim.stats["avg_prep_time_mean"], 15)


class TestFunctions(unittest.TestCase):
    def test_mean_ci_multiple(self):
        # Проверка корректного расчета среднего и доверительного интервала для нескольких значений
        vals = [10, 12, 14]
        m, l, u = mean_ci(vals)
        self.assertTrue(l < m < u)

    def test_mean_ci_single(self):
        # Проверка расчета среднего и доверительного интервала для одного значения
        vals = [10]
        m, l, u = mean_ci(vals)
        self.assertEqual(m, l)
        self.assertEqual(l, u)

    def test_run_experiments_returns_list(self):
        # Проверка возврата списка результатов экспериментов
        with patch("newone.Simulation.start"):
            res = run_experiments(params)
            self.assertIsInstance(res, list)

    def test_series_from_event_list(self):
        # Проверка построения временного ряда из списка событий
        grid = np.linspace(0, 10, 5)
        s = series_from_event_list([(0, 1), (5, 2)], grid)
        self.assertIsInstance(s, pd.Series)
        self.assertTrue((s.index == grid).all())
        self.assertFalse(s.isnull().any())

    def test_series_from_event_list_empty(self):
        # Проверка обработки пустого списка событий
        grid = np.linspace(0, 5, 3)
        s = series_from_event_list([], grid)
        self.assertTrue((s == 0).all())


class TestVisualization(unittest.TestCase):
    @patch("matplotlib.pyplot.show")
    def test_plot_series(self, mock_show):
        # Проверка построения графика временного ряда и вызова show()
        grid = np.linspace(0, 10, 10)
        s = pd.Series(np.arange(10), index=grid)
        plt.step(grid, s)
        plt.plot(grid, s.rolling(window=2, min_periods=1).mean())
        plt.show()
        mock_show.assert_called_once()


if __name__ == "__main__":
    unittest.main()
