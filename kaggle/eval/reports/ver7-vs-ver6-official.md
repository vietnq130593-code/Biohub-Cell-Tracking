# A/B so sánh (official rule) — ver-7 (port 0.947)

- Baseline: `../api/output/latest/eval_report_official_v6.json` (ver-6, 4 video)
- Candidate: `../api/output/latest/eval_report_official_self.json` (ver-7 (port 0.947), 8 video)
- Video paired: **4** | chỉ baseline: — | chỉ candidate: ['44b6_2a2eff9f', '44b6_341df25f', '6bba_085bf656', '6bba_09961292']
- Bootstrap paired: n=10000, seed=314159

## Micro pooled (trên video CHUNG)

| metric | baseline | candidate | Δ |
|---|---|---|---|
| adjEJ (weighted) | 0.9201 | 0.9201 | +0.0000 |
| EJ raw | 0.9200 | 0.9200 | -0.0000 |
| divJ | 0.0000 | 0.0000 | 0.0000 |
| proxy = adj + 0.1×divJ | 0.9201 | 0.9201 | +0.0000 |
| div tp/fp/fn | 0/0/5 | 0/0/5 | +0/+0/+0 |
| cạnh tp/fp/fn | 2186/83/107 | 2185/82/108 | -1/-1/+1 |

**ΔadjEJ bootstrap CI95: [-0.0001, +0.0001]** (mean +0.0000) — ngưỡng thực tiễn ±0.0015

## Guards

- ✅ **G1** div_fn không tăng mạnh: Δdiv_fn=+0 (baseline fn=5/5 events)
- ✅ **G2** div_fp có kiểm soát: Δdiv_fp=+0 (baseline fp=0)
- ✅ **G3** node budget ±10% (stem CHUNG): Δnodes=-99 (-0.1% trên 4 video chung)
- ✅ **G4** không video nào sụt > 0.010: per-video ΔadjEJ xấu nhất = -0.0003
- ✅ **G5** t_true khớp giữa 2 report: paired integrity

## Absolute gates (VER7-PLAN Phase B — áp trên TOÀN BỘ video của candidate)

- ❌ **adj:0.9420**: candidate = 0.9345
- ❌ **proxy:0.9450**: candidate = 0.9345

## Per-video (paired)

| stem | adjEJ base | adjEJ cand | ΔadjEJ | divJ base | divJ cand |
|---|---|---|---|---|---|
| `44b6_12dfb391` | 0.9045 | 0.9045 | +0.0000 | 0.0000 | 0.0000 |
| `44b6_267148e4` | 0.8508 | 0.8506 | -0.0003 | 0.0000 | 0.0000 |
| `6bba_062c8d37` | 0.9972 | 0.9972 | +0.0000 | 0.0000 | 0.0000 |
| `6bba_07e24132` | 0.8197 | 0.8200 | +0.0002 | 0.0000 | 0.0000 |

## VERDICT

### **INCONCLUSIVE** — guards ĐẠT, gate KHÔNG ĐẠT

→ **CHƯA đủ điều kiện submit** — xem guards/gate ở trên trước khi quyết định.
