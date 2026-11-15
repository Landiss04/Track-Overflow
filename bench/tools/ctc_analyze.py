import json, collections, statistics, sys
d = json.load(open(sys.argv[1])); frames = d["shared"]["frames"]; p = d["profiles"][0]
S = p["samples"]; DT = 5.0  # ms per sample at 200 Hz
nm = lambda i: f'{frames[i]["name"]} [{frames[i].get("file","").split("/")[-1]}:{frames[i].get("line")}]'
fn = lambda i: f'{frames[i]["name"]} [{frames[i].get("file","").split("/")[-1]}]'
busy = [len(s) > 4 for s in S]
print(f"{len(S)} samples = {len(S)*DT/1000:.1f} s; busy {100*sum(busy)/len(S):.0f}%")

incl, selfc = collections.Counter(), collections.Counter()
for s in S:
    if len(s) <= 4: continue
    for name in {fn(i) for i in s[4:]}: incl[name] += 1
    selfc[fn(s[-1])] += 1
nb = sum(busy)
print("\nINCLUSIVE, % of busy time (top 14):")
for k, v in incl.most_common(14): print(f"  {100*v/nb:5.1f}%  {k}")
print("\nSELF, % of busy time (top 8):")
for k, v in selfc.most_common(8): print(f"  {100*v/nb:5.1f}%  {k}")

# busy bursts
runs, cur = [], []
for idx, s in enumerate(S):
    if len(s) > 4: cur.append(idx)
    elif cur: runs.append(cur); cur = []
if cur: runs.append(cur)
lens = sorted(len(r) * DT for r in runs)
print(f"\nBusy bursts (uninterrupted, ms): n={len(runs)}  median {statistics.median(lens):.0f}  p90 {lens[int(.9*len(lens))]:.0f}  p99 {lens[int(.99*len(lens))]:.0f}  max {lens[-1]:.0f}")
for thr in (20, 30, 50): print(f"  bursts over {thr} ms: {sum(l > thr for l in lens)}")

def key(r):
    c = collections.Counter()
    for idx in r:
        stk = S[idx]
        # the first frame below the entry points: what kind of work is this?
        for i in stk[4:]:
            n = frames[i]["name"]
            if n in ("ModuleLink._on_ready_read", "ModuleLink._handle", "ModuleLink._answer_step", "CtcOfficeProcess.step", "CtcHost.step_at"): continue
            c[fn(i)] += 1; break
    return c.most_common(1)[0][0]
long_runs = [r for r in runs if len(r) * DT > 30]
cause = collections.Counter(key(r) for r in long_runs)
print(f"\nWhat the {len(long_runs)} bursts over 30 ms were doing (first work frame under the message handler):")
for k, v in cause.most_common(8): print(f"  {v:3d}  {k}")
print("\nThe 6 longest bursts, with their most common deep frames:")
for r in sorted(runs, key=len, reverse=True)[:6]:
    c = collections.Counter()
    for idx in r:
        for i in set(S[idx][4:]): c[fn(i)] += 1
    top = [k for k, _ in c.most_common(9) if not k.startswith(("ModuleLink", "CtcOfficeProcess", "CtcHost"))][:4]
    print(f"  {len(r)*DT:5.0f} ms at t={r[0]*DT/1000:5.1f}s: " + "; ".join(top))
