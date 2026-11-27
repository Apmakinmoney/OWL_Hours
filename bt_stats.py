"""Research add-ons for the backtest (needs numpy, arch, scikit-learn, mapie; installed by backtest.yml).

  Real or luck?   Hansen's SPA test and Romano-Wolf StepM (from the arch package) ask whether any Owl model
                  beat SPY by more than you'd expect from testing many models on the same data.
  Forecast cone   MAPIE split-conformal intervals around a nearest-neighbour forecast of how far the needle moves
                  next month from where it is now. Fitted on the earlier 60% of months, calibrated on the rest.
"""
import math


def monthly(curve):
    out, prev = [], 1.0
    for d, eq in curve:
        out.append((d, eq / prev - 1)); prev = eq
    return out


def run(px, rebal, results, clock, blend, phases):
    import numpy as np
    out = {}
    from arch.bootstrap import SPA, StepM
    spy = dict(monthly(next(r for r in results if r["id"] == "spy")["metrics"]["curve"]))
    cands = [r for r in results if r["group"] in ("Owl model", "Macro test")]
    dates = sorted(set(spy).intersection(*[set(d for d, _ in r["metrics"]["curve"]) for r in cands]))
    bench = np.array([-spy[d] for d in dates])
    mats = []
    for r in cands:
        m = dict(monthly(r["metrics"]["curve"])); mats.append([-m[d] for d in dates])
    models = np.array(mats).T
    spa = SPA(bench, models, block_size=3, reps=2000, seed=11); spa.compute()
    pv = spa.pvalues
    out["spa"] = {"pLower": round(float(pv["lower"]), 3), "pConsistent": round(float(pv["consistent"]), 3), "pUpper": round(float(pv["upper"]), 3),
                  "models": len(cands), "months": len(dates)}
    st = StepM(bench, models, size=0.10, block_size=3, reps=2000, seed=11); st.compute()
    sup = [int(str(x).replace("model.", "")) if not isinstance(x, (int, np.integer)) else int(x) for x in st.superior_models]
    out["stepm"] = [cands[j]["id"] for j in sup if 0 <= j < len(cands)]
    # forecast cone
    from sklearn.neighbors import KNeighborsRegressor
    from mapie.regression import SplitConformalRegressor
    X, y = [], []
    for k, i in enumerate(rebal[:-1]):
        _, _, a0, c0 = clock(px, i, blend); _, _, a1, _ = clock(px, rebal[k + 1], blend)
        if a0 is None or a1 is None: continue
        X.append([math.sin(math.radians(a0)), math.cos(math.radians(a0)), c0]); y.append(((a1 - a0 + 540) % 360) - 180)
    n = len(X)
    if n >= 60:
        X, y = np.array(X), np.array(y); cut = int(n * 0.6)
        reg = SplitConformalRegressor(estimator=KNeighborsRegressor(n_neighbors=12), confidence_level=0.8, prefit=False)
        reg.fit(X[:cut], y[:cut]); reg.conformalize(X[cut:], y[cut:])
        last = len(px.dates) - 1
        _, _, an, cn = clock(px, last, blend)
        if an is not None:
            pred, iv = reg.predict_interval(np.array([[math.sin(math.radians(an)), math.cos(math.radians(an)), cn]]))
            lo, hi = float(iv[0][0][0]), float(iv[0][1][0])
            out["cone"] = {"date": px.dates[last], "angle": round(an, 1), "center": round(float(pred[0]), 1), "lo": round(lo, 1), "hi": round(hi, 1),
                           "confidence": 0.8, "trainMonths": cut, "calMonths": n - cut}
    return out
