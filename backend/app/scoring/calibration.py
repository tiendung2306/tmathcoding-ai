import math
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

from .policy import Policy, point_value


def calibrate(items, pairs, policy: Policy, previous=None):
    previous = previous or {}
    graded = [item for item in items if item["grade"] in policy.bands]
    problem_index = {item["problem_id"]: index for index, item in enumerate(graded)}
    observations = [pair for pair in pairs if pair["problem_id"] in problem_index]
    users = sorted({pair["profile_id"] for pair in observations})
    user_index = {value: index for index, value in enumerate(users)}
    u = np.asarray([user_index[pair["profile_id"]] for pair in observations], dtype=np.int32)
    i = np.asarray([problem_index[pair["problem_id"]] for pair in observations], dtype=np.int32)
    y = np.asarray([int(pair["has_ac"]) for pair in observations], dtype=np.float64)
    scale = 400 / math.log(10)
    origin = 1300.0
    means = np.asarray([(policy.bands[item["grade"]].initial - origin) / scale for item in graded])
    nu, ni = len(users), len(graded)
    initial = np.concatenate((np.zeros(nu), means))
    bounds = [(None, None)] * nu + [((policy.bands[item["grade"]].minimum - origin) / scale,
                                    (policy.bands[item["grade"]].maximum - origin) / scale) for item in graded]
    user_variance, item_variance = (500 / scale) ** 2, (200 / scale) ** 2

    def objective(x):
        z = x[u] - x[nu + i]
        residual = expit(z) - y
        value = np.sum(np.logaddexp(0, z) - y * z)
        value += np.sum(x[:nu] ** 2) / (2 * user_variance)
        value += np.sum((x[nu:] - means) ** 2) / (2 * item_variance)
        gradient = np.concatenate((np.bincount(u, weights=residual, minlength=nu) + x[:nu] / user_variance,
            np.bincount(i, weights=-residual, minlength=ni) + (x[nu:] - means) / item_variance))
        return float(value), gradient

    result = minimize(objective, initial, jac=True, bounds=bounds, method="L-BFGS-B",
                      options={"maxiter": 500, "ftol": 1e-10, "gtol": 1e-5}) if ni else None
    if result is not None and (not result.success or not np.all(np.isfinite(result.x))):
        raise ValueError(f"Bộ tối ưu chưa hội tụ: {result.message}")
    values = result.x[nu:] * scale + origin if result is not None else []
    attempts = np.bincount(i, minlength=ni)
    solved = np.bincount(i, weights=y, minlength=ni)
    output = []
    for index, item in enumerate(graded):
        band = policy.bands[item["grade"]]
        n, ac = int(attempts[index]), int(solved[index])
        supported = n >= policy.min_attempted and min(ac, n - ac) >= policy.min_each_outcome
        old = previous.get(item["problem_id"])
        compatible = old and old["grade"] == item["grade"] and old["points"] is not None
        value = point_value(float(values[index]), band) if supported else point_value(
            old["points"] if compatible else band.initial, band)
        output.append({"problem_id": item["problem_id"], "points": value,
                       "difficulty": float(values[index]), "attempted": n, "solved": ac,
                       "method": "MODEL" if supported else "RETAINED" if compatible else "PROVISIONAL"})
    return output, {"model": "bounded-rasch-map-v1", "observations": len(observations),
                    "students": nu, "iterations": int(result.nit) if result is not None else 0,
                    "objective": float(result.fun) if result is not None else 0,
                    "model_items": sum(item["method"] == "MODEL" for item in output)}
