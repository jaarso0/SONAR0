import json
import sys
from pathlib import Path

def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(int(len(ordered) * p), len(ordered) - 1)]

turns = [json.loads(line) for line in
         Path(sys.argv[1] if len(sys.argv) > 1 else "logs/turns.jsonl").read_text().splitlines()]

print(f"{len(turns)} turns\n")
for field in ["t_eou_ms", "t_stt_final_ms", "t_llm_ttft_ms", "t_tts_ttfb_ms", "t_total_ms"]:
    values = [t[field] for t in turns if field in t]
    print(f"{field:18} p50 {percentile(values, .5):6.0f}   "
          f"p95 {percentile(values, .95):6.0f}   max {max(values, default=0):6.0f}")

print(f"\ntotal cost   ₹{sum(t.get('cost_inr', 0) for t in turns):.2f}")
print(f"per turn     ₹{sum(t.get('cost_inr', 0) for t in turns) / max(len(turns), 1):.3f}")