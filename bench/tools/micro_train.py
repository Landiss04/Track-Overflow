import sys, time, statistics; sys.path.insert(0, sys.argv[1])
from common.hw_link.cores import TrainCore
sys.path.insert(0, "Train-Ctrl_HW")
def good(s): return dict(actual_speed=s,commanded_speed=10.0,authority_blocks=3,emergency_brake_state=False,service_brake_state=False,door_state=[False,False],light_state=[False,False],cabin_temperature=22.0)
for n in (1,6,12):
    c=TrainCore(); ids=[f"R{i}" for i in range(n)]; xs=[]
    for t in range(3000):
        r={"dt":0.1,"tick":t,"sim_time_s":18000+t*.1,"inputs":{"trains":{i:{"line":"Red","inputs":good(1+t%5)} for i in ids}}}
        a=time.perf_counter(); c.step(r); xs.append((time.perf_counter()-a)*1000)
    xs.sort(); print(n,"trains mean %.3f p99 %.3f max %.3f ms"%(statistics.fmean(xs),xs[int(len(xs)*.99)],xs[-1]))
