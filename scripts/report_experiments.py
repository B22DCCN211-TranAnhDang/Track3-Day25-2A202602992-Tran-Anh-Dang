"""Reproduce report-only ablations without modifying the submitted client/config."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from gameday_lab.client import ResilientClient
from gameday_lab.factory import build_client
from gameday_lab.sim.config import load_config
from gameday_lab.sim.engine import run_scenario


class UnfilteredClient(ResilientClient):
    def ladder(self, task):
        return list(self.order)


def main():
    results = {}
    def run(label, scenario, client_changes=None, cache_changes=None, unfiltered=False):
        cfg = load_config('configs/gameday.yaml', 'configs/scenarios_cache.yaml' if scenario.startswith('C1') else 'configs/scenarios.yaml')
        cfg.client.update(copy.deepcopy(client_changes or {}))
        cfg.cache.update(cache_changes or {})
        client = (UnfilteredClient(cfg.provider_infos(), cfg.fallback_order, cfg.client, seed=1)
                  if unfiltered else build_client('cached' if scenario.startswith('C1') else 'resilient', cfg))
        results[label] = run_scenario(cfg, scenario, client, 25).metrics()
    for budget in [True, False]:
        cfg = load_config('configs/gameday.yaml', 'configs/scenarios.yaml')
        changes = {'breaker': {**cfg.client['breaker'], 'min_calls': 1000000000}, 'max_attempts_per_provider': 5}
        if not budget:
            changes.update(retry_budget_ratio=100, retry_budget_max_tokens=1e9, retry_budget_min_per_s=1e6)
        for sc in ['G2_overload_storm', 'G3_brownout']:
            run(f'{sc}_budget_{budget}', sc, changes)
    for sc in ['G6_provider_outage', 'G4_slow_region']:
        run(sc+'_timeout30', sc, {'attempt_timeout_s': 30})
    run('G6_unfiltered', 'G6_provider_outage', unfiltered=True)
    for threshold in [.8, .9, .97]:
        run(f'C1_threshold_{threshold}', 'C1_faq_outage', cache_changes={'similarity_threshold': threshold})
    for ttl in [30, 60, 300]:
        run(f'C1_ttl_{ttl}', 'C1_faq_outage', cache_changes={'ttl_s': ttl})
    run('C1_no_stale', 'C1_faq_outage', cache_changes={'max_stale_s': 0})
    Path('reports/experiments.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    keys = ['availability', 'latency_p95_s', 'amplification', 'retry_ratio', 'recovery_s', 'give_up_reasons', 'incompatible_routes', 'faq_availability', 'cache_hit_ratio', 'wrong_answers_by_reason', 'outdated_answers', 'cost_per_good_turn']
    for label, metrics in results.items():
        print(label, {k: metrics[k] for k in keys if k in metrics})


if __name__ == '__main__':
    main()
