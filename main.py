


import simulator


if __name__ == "__main__":

    params = {
        "initial_piles": 1,
        "num_loaders": 2,
        "num_trucks": 4,

        # интервалы (в секундах или условных единицах)
        "bulldozer_time_range": (2, 7),
        "loading_time_range": (1, 3),
        "travel_to_dump_range": (2, 3),
        "unloading_time_range": (1, 3),
        "return_time_range": (2, 3),

        "report_interval": 5.0
    }


    sim = simulator.Simulator(params, seed=12345, trace=True)
    res = sim.run(until=500.0, max_loaded=50)

    print("\nSIMULATION SUMMARY")
    print(f"Simulated time: {res['sim_time']:.3f}")
    print(f"Total loaded truck cycles completed: {res['total_loaded_trucks']}")
    if res['avg_cycle_time'] is not None:
        print(f"Average truck cycle time: {res['avg_cycle_time']:.3f}")
    print(f"Loader utilization per machine (fraction of time busy): {res['loader_utilization_per_machine']}")
    print(f"Bulldozer work time fraction (approx): {res['bulldozer_utilization']}")
    print(f"Final piles on site: {res['final_piles']}")
    print(f"Last truck states: {res['trucks_states']}")
    # print few samples
    print("\nSome periodic samples (time, piles, loaders_busy, total_loaded):")
    for s in res['samples'][:10]:
        print(f" t={s['time']:.1f} piles={s['piles']} loaders_busy={s['loaders_busy']} loaded={s['total_loaded_trucks']}")
