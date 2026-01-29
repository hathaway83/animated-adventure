#!/usr/bin/env python3
"""
Org Structure Simulator
-----------------------
Models organizational hierarchy, detects structural risks,
and projects scaling needs at 6-month and 12-month horizons.

Run directly: python3 org_simulator.py
"""

# ─── Sample Config ───────────────────────────────────────────────────────────
# Modify this dict to model your own org. Every role needs a unique role_name,
# a level (IC, Manager, Director, VP, C-Suite), and a manager_role (None for root).

SAMPLE_CONFIG = {
    "business_scope": "Series B SaaS startup scaling from 30 to 80 engineers",
    "goals": [
        "Ship v2 platform in 9 months",
        "Establish SRE practice",
        "Build out data engineering team",
    ],
    "current_headcount": 30,
    "roles": [
        {"role_name": "CTO",              "level": "C-Suite",  "manager_role": None},
        {"role_name": "VP Engineering",    "level": "VP",       "manager_role": "CTO"},
        {"role_name": "VP Product",        "level": "VP",       "manager_role": "CTO"},
        {"role_name": "Dir Platform",      "level": "Director", "manager_role": "VP Engineering"},
        {"role_name": "Dir Product Eng",   "level": "Director", "manager_role": "VP Engineering"},
        {"role_name": "Dir SRE",           "level": "Director", "manager_role": "VP Engineering"},
        {"role_name": "Mgr Backend",       "level": "Manager",  "manager_role": "Dir Platform"},
        {"role_name": "Mgr Frontend",      "level": "Manager",  "manager_role": "Dir Platform"},
        {"role_name": "Mgr API",           "level": "Manager",  "manager_role": "Dir Product Eng"},
        {"role_name": "Mgr Mobile",        "level": "Manager",  "manager_role": "Dir Product Eng"},
        {"role_name": "Mgr SRE",           "level": "Manager",  "manager_role": "Dir SRE"},
        {"role_name": "IC Backend 1",      "level": "IC",       "manager_role": "Mgr Backend"},
        {"role_name": "IC Backend 2",      "level": "IC",       "manager_role": "Mgr Backend"},
        {"role_name": "IC Backend 3",      "level": "IC",       "manager_role": "Mgr Backend"},
        {"role_name": "IC Backend 4",      "level": "IC",       "manager_role": "Mgr Backend"},
        {"role_name": "IC Frontend 1",     "level": "IC",       "manager_role": "Mgr Frontend"},
        {"role_name": "IC Frontend 2",     "level": "IC",       "manager_role": "Mgr Frontend"},
        {"role_name": "IC Frontend 3",     "level": "IC",       "manager_role": "Mgr Frontend"},
        {"role_name": "IC API 1",          "level": "IC",       "manager_role": "Mgr API"},
        {"role_name": "IC API 2",          "level": "IC",       "manager_role": "Mgr API"},
        {"role_name": "IC API 3",          "level": "IC",       "manager_role": "Mgr API"},
        {"role_name": "IC API 4",          "level": "IC",       "manager_role": "Mgr API"},
        {"role_name": "IC API 5",          "level": "IC",       "manager_role": "Mgr API"},
        {"role_name": "IC Mobile 1",       "level": "IC",       "manager_role": "Mgr Mobile"},
        {"role_name": "IC Mobile 2",       "level": "IC",       "manager_role": "Mgr Mobile"},
        {"role_name": "IC Mobile 3",       "level": "IC",       "manager_role": "Mgr Mobile"},
        {"role_name": "IC SRE 1",          "level": "IC",       "manager_role": "Mgr SRE"},
        {"role_name": "IC SRE 2",          "level": "IC",       "manager_role": "Mgr SRE"},
        {"role_name": "IC SRE 3",          "level": "IC",       "manager_role": "Mgr SRE"},
        {"role_name": "IC SRE 4",          "level": "IC",       "manager_role": "Mgr SRE"},
    ],
    "max_span_of_control": 7,
    "expected_growth_6mo": 20,
    "expected_growth_12mo": 50,
    "constraints": [
        "No more than 4 layers between IC and CTO",
        "Every manager must have at least 3 direct reports",
        "SRE team must remain centralized until headcount > 60",
    ],
}

# ─── Level hierarchy used for ordering and depth calculations ────────────────
LEVEL_ORDER = ["C-Suite", "VP", "Director", "Manager", "IC"]


# ─── Hierarchy Building ─────────────────────────────────────────────────────

def build_hierarchy(roles):
    """Return {role_name: [direct_report_names]} and a lookup dict by name."""
    lookup = {r["role_name"]: r for r in roles}
    children = {r["role_name"]: [] for r in roles}
    root = None
    for r in roles:
        mgr = r["manager_role"]
        if mgr is None:
            root = r["role_name"]
        else:
            children[mgr].append(r["role_name"])
    return children, lookup, root


def get_depth(role_name, children, _cache=None):
    """Longest path from this node to a leaf (0 for ICs)."""
    if _cache is None:
        _cache = {}
    if role_name in _cache:
        return _cache[role_name]
    kids = children.get(role_name, [])
    if not kids:
        _cache[role_name] = 0
        return 0
    d = 1 + max(get_depth(k, children, _cache) for k in kids)
    _cache[role_name] = d
    return d


# ─── Span of Control ────────────────────────────────────────────────────────

def calc_spans(children):
    """Return {manager_name: span_count} for every node with reports."""
    return {name: len(reports) for name, reports in children.items() if reports}


def find_violations(spans, max_span):
    """Managers whose span exceeds the configured maximum."""
    return {name: s for name, s in spans.items() if s > max_span}


# ─── Single Points of Failure ───────────────────────────────────────────────
# A role is a SPOF if it is the only manager in its level under its parent,
# AND it has a large number of transitive reports relative to org size.

def count_transitive_reports(role_name, children):
    """Total number of people under this node (not counting the node itself)."""
    direct = children.get(role_name, [])
    total = len(direct)
    for d in direct:
        total += count_transitive_reports(d, children)
    return total


def detect_spofs(children, lookup, threshold_pct=0.25):
    """
    Flag roles where one person controls >= threshold_pct of the entire org.
    These are structural single-points-of-failure: if they leave,
    a disproportionate share of the org is disrupted.
    """
    org_size = len(lookup)
    threshold = max(3, int(org_size * threshold_pct))
    spofs = []
    for name in lookup:
        tr = count_transitive_reports(name, children)
        if tr >= threshold and lookup[name]["level"] not in ("C-Suite",):
            spofs.append((name, tr))
    return sorted(spofs, key=lambda x: -x[1])


# ─── Layer Analysis ──────────────────────────────────────────────────────────

def count_by_level(lookup):
    """Return {level: count}."""
    counts = {}
    for r in lookup.values():
        counts[r["level"]] = counts.get(r["level"], 0) + 1
    return counts


def max_hierarchy_depth(root, children):
    """Number of layers from root to deepest IC (inclusive)."""
    return get_depth(root, children) + 1


# ─── Printing Utilities ─────────────────────────────────────────────────────

def print_divider(title):
    width = 72
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def print_org_chart(role_name, children, lookup, indent=0):
    """Recursively print a text-based org chart with level labels."""
    level = lookup[role_name]["level"]
    prefix = "    " * indent + ("├── " if indent else "")
    print(f"{prefix}{role_name}  [{level}]")
    for child in children.get(role_name, []):
        print_org_chart(child, children, lookup, indent + 1)


def print_span_table(spans, max_span):
    """Tabular view of every manager's span, flagging violations."""
    header = f"{'Manager':<25} {'Span':>5}  {'Status'}"
    print(header)
    print("-" * len(header))
    for name in sorted(spans, key=lambda n: -spans[n]):
        s = spans[name]
        flag = " !! OVER LIMIT" if s > max_span else ""
        print(f"{name:<25} {s:>5}{flag}")


# ─── Growth Projection ──────────────────────────────────────────────────────
# The model distributes new headcount proportionally across existing teams,
# then checks which managers would exceed span limits and need splits.

def project_growth(children, lookup, max_span, new_hires):
    """
    Simulate adding new_hires ICs distributed proportionally by current team
    size. Returns warnings and suggested new roles.
    """
    spans = calc_spans(children)
    # Only managers of ICs absorb new hires (line managers)
    line_mgrs = [
        m for m, kids in children.items()
        if kids and all(lookup[k]["level"] == "IC" for k in kids)
    ]
    if not line_mgrs:
        return [], []

    # Distribute proportionally by current team size
    total_ics = sum(spans.get(m, 0) for m in line_mgrs)
    distribution = {}
    for m in line_mgrs:
        share = spans.get(m, 0) / total_ics if total_ics else 1 / len(line_mgrs)
        distribution[m] = round(share * new_hires)

    warnings = []
    suggestions = []
    for mgr, added in distribution.items():
        future_span = spans.get(mgr, 0) + added
        if future_span > max_span:
            over = future_span - max_span
            # Recommend splitting into N teams to keep spans reasonable
            new_teams_needed = (future_span // max_span)
            warnings.append(
                f"{mgr}: span grows to {future_span} (+{added} ICs) — exceeds limit of {max_span}"
            )
            suggestions.append(
                f"Split {mgr}'s team into {new_teams_needed + 1} squads → "
                f"add {new_teams_needed} new Manager(s) under {lookup[mgr]['manager_role']}"
            )
        elif future_span > max_span - 2:
            warnings.append(
                f"{mgr}: span grows to {future_span} (+{added} ICs) — approaching limit"
            )

    return warnings, suggestions


# ─── Scenario Analysis ───────────────────────────────────────────────────────
# Centralized: all ICs roll up through functional pillars (Platform, Product, SRE).
# Decentralized: ICs are grouped into cross-functional pods with embedded managers.

def _deep_copy_config(config):
    """Simple deep copy without importing copy module."""
    import json
    return json.loads(json.dumps(config))


def centralized_model(config):
    """
    In a centralized model every function (backend, frontend, SRE, etc.)
    has its own chain of command. This maximizes functional expertise
    but can slow cross-team coordination.
    """
    print_divider("SCENARIO: Centralized Model (functional pillars)")
    print("Structure: each discipline owns its full stack of reports.")
    print("Trade-off: deep expertise vs. cross-team coordination overhead.\n")
    # The sample config is already centralized, so we analyse as-is
    run_analysis(config)


def decentralized_model(config):
    """
    In a decentralized (pod) model, cross-functional squads each get
    their own manager. Reduces coordination cost but dilutes expertise depth.
    """
    print_divider("SCENARIO: Decentralized Model (cross-functional pods)")
    print("Structure: ICs are reshuffled into product-aligned pods.")
    print("Trade-off: faster delivery vs. shallower functional expertise.\n")

    cfg = _deep_copy_config(config)

    # Gather all ICs and redistribute into equally-sized pods
    ics = [r for r in cfg["roles"] if r["level"] == "IC"]
    managers = [r for r in cfg["roles"] if r["level"] == "Manager"]
    non_ic_non_mgr = [r for r in cfg["roles"] if r["level"] not in ("IC", "Manager")]

    max_span = cfg["max_span_of_control"]
    num_pods = max(1, len(ics) // max_span + (1 if len(ics) % max_span else 0))

    # Create pod managers under the first Director we find
    directors = [r for r in cfg["roles"] if r["level"] == "Director"]
    parent_dir = directors[0]["role_name"] if directors else None

    new_roles = list(non_ic_non_mgr)
    for i in range(num_pods):
        pod_mgr_name = f"Pod Lead {i + 1}"
        new_roles.append({
            "role_name": pod_mgr_name,
            "level": "Manager",
            "manager_role": parent_dir,
        })
        # Assign a slice of ICs to this pod
        start = i * max_span
        end = start + max_span
        for ic in ics[start:end]:
            new_roles.append({
                "role_name": ic["role_name"],
                "level": "IC",
                "manager_role": pod_mgr_name,
            })

    cfg["roles"] = new_roles
    run_analysis(cfg)


# ─── Main Analysis Runner ───────────────────────────────────────────────────

def run_analysis(config):
    children, lookup, root = build_hierarchy(config["roles"])
    max_span = config["max_span_of_control"]

    # Org chart
    print_divider("Org Chart")
    print_org_chart(root, children, lookup)

    # Span of control table
    spans = calc_spans(children)
    print_divider("Span of Control")
    print_span_table(spans, max_span)

    violations = find_violations(spans, max_span)
    if violations:
        print(f"\n⚠  {len(violations)} manager(s) exceed max span of {max_span}.")
    else:
        print(f"\n✓  All managers within max span of {max_span}.")

    # SPOFs
    spofs = detect_spofs(children, lookup)
    print_divider("Single Points of Failure")
    if spofs:
        for name, tr in spofs:
            print(f"  {name} — controls {tr}/{len(lookup)} roles ({100*tr//len(lookup)}% of org)")
    else:
        print("  No structural SPOFs detected.")

    # Layer analysis
    levels = count_by_level(lookup)
    depth = max_hierarchy_depth(root, children)
    print_divider("Layer Analysis")
    for lvl in LEVEL_ORDER:
        if lvl in levels:
            print(f"  {lvl:<12} {levels[lvl]:>3} people")
    print(f"\n  Total depth (root → leaf): {depth} layers")

    # Constraints check
    print_divider("Constraint Check")
    for c in config.get("constraints", []):
        print(f"  • {c}")
    if depth > 5:
        print("  ⚠  Depth exceeds 5 layers — consider flattening.")

    # Growth projections
    for label, key in [("6-month", "expected_growth_6mo"), ("12-month", "expected_growth_12mo")]:
        growth = config.get(key, 0)
        if not growth:
            continue
        print_divider(f"Scaling Projection: +{growth} hires ({label})")
        warnings, suggestions = project_growth(children, lookup, max_span, growth)
        if warnings:
            print("  Warnings:")
            for w in warnings:
                print(f"    ⚠  {w}")
        if suggestions:
            print("\n  Suggested additions:")
            for s in suggestions:
                print(f"    → {s}")
        if not warnings and not suggestions:
            print("  ✓  Current structure can absorb growth within span limits.")


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main():
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║               O R G   S T R U C T U R E   S I M U L A T O R       ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")

    cfg = SAMPLE_CONFIG
    print(f"\nScope : {cfg['business_scope']}")
    print(f"Goals : {', '.join(cfg['goals'])}")
    print(f"Head  : {cfg['current_headcount']} today → "
          f"+{cfg['expected_growth_6mo']} (6mo) → +{cfg['expected_growth_12mo']} (12mo)")

    # Baseline analysis
    print_divider("BASELINE ANALYSIS")
    run_analysis(cfg)

    # Scenario comparisons
    centralized_model(cfg)
    decentralized_model(cfg)

    print("\n" + "=" * 72)
    print("  Simulation complete. Edit SAMPLE_CONFIG to model your own org.")
    print("=" * 72)


if __name__ == "__main__":
    main()
