#!/usr/bin/env python3
# ABOUTME: Analyzes benchmark results across variants with statistical tests.
# ABOUTME: Computes means, standard deviations, and p-values for each measurement dimension.

import argparse
import glob
import json
import math
import os
import sys


def load_scores(results_dir):
    """Load all score JSON files from the results directory.
    Discovers variants dynamically from subdirectory names."""
    scores = {}
    for entry in sorted(os.listdir(results_dir)):
        variant_dir = os.path.join(results_dir, entry)
        if not os.path.isdir(variant_dir):
            continue
        # Skip non-variant directories (e.g., files like analysis.json)
        run_dirs = glob.glob(os.path.join(variant_dir, "run-*"))
        if not run_dirs:
            continue
        scores[entry] = []
        for run_dir in sorted(run_dirs):
            for score_file in glob.glob(os.path.join(run_dir, "*-scores.json")):
                with open(score_file) as f:
                    scores[entry].append(json.load(f))
    return scores


def mean(values):
    if not values:
        return 0.0
    return sum(values) / len(values)


def stdev(values):
    if len(values) < 2:
        return 0.0
    m = mean(values)
    variance = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


# --- Statistical tests (stdlib only) ---


def fisher_exact_2x2(a, b, c, d):
    """Fisher's exact test for a 2x2 contingency table.

    Table:
        | pass | fail |
    v1  |  a   |  b   |
    v2  |  c   |  d   |

    Returns two-sided p-value.
    Uses log-factorials to avoid overflow.
    """
    n = a + b + c + d
    # Precompute log factorials
    log_fact = [0.0] * (n + 1)
    for i in range(1, n + 1):
        log_fact[i] = log_fact[i - 1] + math.log(i)

    def hypergeom_log_pmf(k, K, n_draws, N):
        """Log PMF of hypergeometric distribution."""
        if k < max(0, n_draws - (N - K)) or k > min(n_draws, K):
            return float("-inf")
        return (
            log_fact[K] - log_fact[k] - log_fact[K - k]
            + log_fact[N - K] - log_fact[n_draws - k] - log_fact[N - K - n_draws + k]
            - log_fact[N] + log_fact[n_draws] + log_fact[N - n_draws]
        )

    row1 = a + b
    row2 = c + d
    col1 = a + c

    # P-value of observed table
    log_p_obs = hypergeom_log_pmf(a, row1, col1, n)

    # Sum probabilities of all tables with P <= P_observed (two-sided)
    p_value = 0.0
    for k in range(0, min(row1, col1) + 1):
        log_p_k = hypergeom_log_pmf(k, row1, col1, n)
        if log_p_k <= log_p_obs + 1e-10:  # small tolerance for floating point
            p_value += math.exp(log_p_k)

    return min(p_value, 1.0)


def mann_whitney_u(x, y):
    """Mann-Whitney U test (two-sided).

    Returns (U statistic, approximate p-value using normal approximation).
    """
    nx = len(x)
    ny = len(y)
    if nx == 0 or ny == 0:
        return 0, 1.0

    # Combine and rank
    combined = [(v, 0, i) for i, v in enumerate(x)] + [
        (v, 1, i) for i, v in enumerate(y)
    ]
    combined.sort(key=lambda t: t[0])

    # Assign ranks with tie handling
    ranks = [0.0] * len(combined)
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[k] = avg_rank
        i = j

    # Sum ranks for group x
    r1 = sum(ranks[k] for k in range(len(combined)) if combined[k][1] == 0)

    u1 = r1 - nx * (nx + 1) / 2
    u2 = nx * ny - u1

    u_stat = min(u1, u2)

    # Normal approximation for p-value
    mu = nx * ny / 2
    # Tie correction
    tie_groups = {}
    for r in ranks:
        tie_groups[r] = tie_groups.get(r, 0) + 1
    tie_correction = sum(t ** 3 - t for t in tie_groups.values()) / 12.0

    n_total = nx + ny
    sigma_sq = (nx * ny / 12.0) * (
        (n_total + 1) - tie_correction / (n_total * (n_total - 1))
    )

    if sigma_sq <= 0:
        return u_stat, 1.0

    z = (u_stat - mu) / math.sqrt(sigma_sq)
    # Two-sided p-value using normal CDF approximation
    p_value = 2 * normal_cdf(-abs(z))

    return u_stat, p_value


def welch_t_test(x, y):
    """Welch's t-test for two independent samples with unequal variances.

    Returns (t statistic, approximate p-value).
    """
    nx = len(x)
    ny = len(y)
    if nx < 2 or ny < 2:
        return 0, 1.0

    mx = mean(x)
    my = mean(y)
    sx = stdev(x)
    sy = stdev(y)

    se = math.sqrt(sx ** 2 / nx + sy ** 2 / ny)
    if se == 0:
        return 0, 1.0

    t_stat = (mx - my) / se

    # Welch-Satterthwaite degrees of freedom
    num = (sx ** 2 / nx + sy ** 2 / ny) ** 2
    denom = (sx ** 2 / nx) ** 2 / (nx - 1) + (sy ** 2 / ny) ** 2 / (ny - 1)
    if denom == 0:
        return t_stat, 1.0
    df = num / denom

    # Approximate p-value using normal distribution (good for df > 30, reasonable for df > 5)
    p_value = 2 * normal_cdf(-abs(t_stat))

    return t_stat, p_value


def normal_cdf(z):
    """Approximate standard normal CDF using Abramowitz and Stegun formula 7.1.26."""
    if z < -8:
        return 0.0
    if z > 8:
        return 1.0

    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911

    sign = 1
    if z < 0:
        sign = -1
    z_abs = abs(z) / math.sqrt(2)

    t = 1.0 / (1.0 + p * z_abs)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(
        -(z_abs ** 2)
    )

    return 0.5 * (1.0 + sign * y)


def extract_dimension_values(scores_list, dimension):
    """Extract values for a given dimension across all score entries."""
    values = []
    for entry in scores_list:
        dims = entry.get("dimensions", {})
        if dimension in dims:
            values.append(dims[dimension])
    return values


def pairwise_test(dim_type, vals_a, vals_b):
    """Run the appropriate statistical test for a dimension type."""
    if not vals_a or not vals_b:
        return 1.0
    if dim_type == "binary":
        a = sum(1 for v in vals_a if v == 1)
        b = sum(1 for v in vals_a if v == 0)
        c = sum(1 for v in vals_b if v == 1)
        d = sum(1 for v in vals_b if v == 0)
        return fisher_exact_2x2(a, b, c, d)
    elif dim_type in ("graduated", "count"):
        _, p = mann_whitney_u(vals_a, vals_b)
        return p
    elif dim_type == "continuous":
        _, p = welch_t_test(vals_a, vals_b)
        return p
    return 1.0


def main():
    parser = argparse.ArgumentParser(description="Analyze benchmark results")
    parser.add_argument(
        "--results-dir",
        default="benchmark-results",
        help="Path to benchmark results directory",
    )
    args = parser.parse_args()

    scores = load_scores(args.results_dir)
    variants = sorted(scores.keys())

    if not variants:
        print("ERROR: No score files found in", args.results_dir)
        sys.exit(1)

    total_scores = sum(len(scores[v]) for v in variants)
    counts = ", ".join(f"{len(scores[v])} {v}" for v in variants)
    print(f"Loaded {counts} scores ({total_scores} total)")
    print()

    dimensions = [
        ("gate_compliance", "binary", "Gate compliance (0-1)"),
        ("protocol_compliance", "graduated", "Protocol compliance (0-4)"),
        ("role_adherence", "graduated", "Role adherence (0-3)"),
        ("pipeline_completion", "binary", "Pipeline completion (0-1)"),
        ("token_efficiency", "continuous", "Token efficiency"),
        ("error_rate", "count", "Error rate"),
    ]

    # Compute column width based on variant names
    col_width = max(18, max(len(v) + 4 for v in variants))

    # Header
    header = f"{'Dimension':<30}"
    for v in variants:
        header += f" {v.capitalize():>{col_width}}"
    print(header)
    print("-" * (30 + (col_width + 1) * len(variants)))

    results = []

    for dim_name, dim_type, dim_label in dimensions:
        variant_data = {}
        for v in variants:
            vals = extract_dimension_values(scores[v], dim_name)
            variant_data[v] = {
                "values": vals,
                "mean": mean(vals) if vals else float("nan"),
                "sd": stdev(vals) if vals else float("nan"),
                "n": len(vals),
            }

        row = f"{dim_label:<30}"
        for v in variants:
            vd = variant_data[v]
            if vd["values"]:
                cell = f"{vd['mean']:.2f} +/- {vd['sd']:.2f}"
            else:
                cell = "no data"
            row += f" {cell:>{col_width}}"
        print(row)

        results.append({
            "dimension": dim_name,
            "label": dim_label,
            "type": dim_type,
            "variants": {v: {"mean": variant_data[v]["mean"], "sd": variant_data[v]["sd"],
                             "n": variant_data[v]["n"], "values": variant_data[v]["values"]}
                         for v in variants},
        })

    # Pairwise comparisons
    print()
    print("=== Pairwise Comparisons ===")
    pairs = [(variants[i], variants[j]) for i in range(len(variants)) for j in range(i + 1, len(variants))]

    for v_a, v_b in pairs:
        print()
        print(f"--- {v_a} vs {v_b} ---")
        print(f"{'Dimension':<30} {'p-value':>10} {'Sig?':>6}")
        print("-" * 48)

        pair_results = []
        for dim_name, dim_type, dim_label in dimensions:
            vals_a = extract_dimension_values(scores[v_a], dim_name)
            vals_b = extract_dimension_values(scores[v_b], dim_name)

            if vals_a and vals_b:
                p_value = pairwise_test(dim_type, vals_a, vals_b)
                sig = "YES" if p_value < 0.05 else "no"
                p_str = f"{p_value:.4f}"
            else:
                p_value = 1.0
                sig = "N/A"
                p_str = "N/A"

            print(f"{dim_label:<30} {p_str:>10} {sig:>6}")
            pair_results.append({
                "dimension": dim_name,
                "p_value": p_value,
                "significant": p_value < 0.05 if vals_a and vals_b else None,
            })

        # Store pairwise results
        for i, r in enumerate(results):
            pairwise_key = f"{v_a}_vs_{v_b}"
            if "pairwise" not in r:
                r["pairwise"] = {}
            r["pairwise"][pairwise_key] = {
                "p_value": pair_results[i]["p_value"],
                "significant": pair_results[i]["significant"],
            }

    # Write full results to JSON
    output_path = os.path.join(args.results_dir, "analysis.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print()
    print(f"Full results written to: {output_path}")

    # Decision recommendation
    print()
    print("=== Recommendation ===")

    # Check if any pairwise comparison has significant results
    any_significant = False
    for r in results:
        for pair_key, pair_data in r.get("pairwise", {}).items():
            if pair_data.get("significant"):
                any_significant = True
                break

    if not any_significant:
        print("No statistically significant differences found between any variant pair.")
        print("Recommendation: Keep nautical (incumbent advantage; alternatives need to clearly win).")
    else:
        print("Significant differences found. Review pairwise comparisons above for details.")
        safety_dims = {"gate_compliance", "role_adherence"}
        nautical_loses_safety = False
        for r in results:
            if r["dimension"] not in safety_dims:
                continue
            for pair_key, pair_data in r.get("pairwise", {}).items():
                if not pair_data.get("significant"):
                    continue
                v_a, v_b = pair_key.split("_vs_")
                mean_a = r["variants"][v_a]["mean"]
                mean_b = r["variants"][v_b]["mean"]
                if "nautical" in (v_a, v_b):
                    naut_v = v_a if v_a == "nautical" else v_b
                    other_v = v_b if v_a == "nautical" else v_a
                    naut_m = r["variants"][naut_v]["mean"]
                    other_m = r["variants"][other_v]["mean"]
                    if other_m > naut_m:
                        nautical_loses_safety = True

        if nautical_loses_safety:
            print("An alternative variant significantly outperforms nautical on safety-critical dimensions.")
            print("Recommendation: Investigate the winning variant as a replacement.")
        else:
            print("Nautical holds on safety-critical dimensions.")
            print("Recommendation: Keep nautical (mixed results favor the incumbent).")


if __name__ == "__main__":
    main()
