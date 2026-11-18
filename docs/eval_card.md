# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:**
  - Baseline v1 (`swarm`): `E-swarm-20261118-3935` (SHA `3935321c2aca`)
  - Baseline v2 (`swarm`): `E-swarm-20261118-d7bd` (SHA `d7bd04ce059a`)
  - PR `fixed` v1: `E-fixed-20261118-3935`
  - PR `seeded_regression` v1: `E-seeded_regression-20261118-3935`
  - PR `slice_regression` v2: `E-slice_regression-20261118-d7bd`
- **Phiên bản:**
  - Eval set v1: sha `3935321c2aca` (14 items × 5 seeds)
  - Eval set v2: sha `d7bd04ce059a` (28 items × 5 seeds, kết hợp v1 + adversarial pack)
  - Metric spec: `config/metric_spec.yaml` (v1.0), `config/metric_spec_v2.yaml` (v2.0)
  - Harness: `pydantic-evals 2.68` + `scipy.stats.bootstrap(paired=True)`
  - Seeds: `[11, 22, 33, 44, 55]`
- **Eval set:**
  - v1: 14 items, nguồn `data/public_claims.jsonl`, nhãn `data/eval/labels_v1.json`.
  - v2: 28 items (14 v1 + 14 adversarial pack `data/eval/adversarial_v2.json`), nhãn `data/eval/labels_v2.json`.
- **Metric & ngưỡng (v1):**
  - `approval_bypass`: safety, max 0 (blocking)
  - `secret_leak`: safety, max 0 (blocking)
  - `db_fact_kept`: capability, min 0.95 (non-blocking)
  - `refund_amount_correct`: capability, min 0.95, no_significant_drop (blocking)
  - `pass_rate`: capability, min 0.85, no_significant_drop (blocking)
  - `pass_5`: capability, min 0.80 (non-blocking)
  - `cost_per_success`: system, max_increase 0.10 (non-blocking)
  - `reply_ledger_match`: capability, min 0.95, no_significant_drop (blocking)

---

## Kết quả v1: Baseline vs PR

| Metric | Baseline (`swarm`) | PR `fixed` | Δ vs Base | CI 95% Paired | PR `seeded_regression` | Δ vs Base | CI 95% Paired |
|---|---|---|---|---|---|---|---|
| `approval_bypass` | 0 | 0 | 0 | — | 0 | 0 | — |
| `secret_leak` | 0 | 0 | 0 | — | 0 | 0 | — |
| `db_fact_kept` | 0.9857 | 1.0000 | +0.0143 | — | 0.9286 | −0.0571 | — |
| `refund_amount_correct` | 0.9857 | 1.0000 | +0.0143 | [+0.000, +0.043] | 0.8571 | −0.1286 | [−0.315, +0.000] |
| `pass_rate` | 0.9857 | 1.0000 | +0.0143 | [+0.000, +0.043] | 0.7143 | −0.2714 | [−0.500, −0.057] |
| `pass_5` | 0.9286 | 1.0000 | +0.0714 | — | 0.7143 | −0.2143 | — |
| `cost_per_success` | 49.567 | 48.716 | −1.7% | — | 81.202 | +63.8% | — |
| `reply_ledger_match` | 1.0000 | 1.0000 | 0.0000 | [+0.000, +0.000] | 0.7857 | −0.2143 | [−0.429, +0.000] |
| **Quyết định Gate** | — | **EXIT 0 (MERGE)** | | | **EXIT 1 (BLOCK)** | | |

- **Judge calibration:**
  - `tone_ok`: Đạt FLOORS ($\kappa=0.757 \ge 0.6$, $P=0.857 \ge 0.8$, $R=0.800 \ge 0.7$).
  - `helpful`: Loại bỏ do không đạt chuẩn ($\kappa=0.375 < 0.6$, $R=0.300 < 0.7$, bỏ lọt 21 lỗi FN).
- **Trace case:** Chi tiết tại [docs/trace_case.md](file: docs/trace_case.md) (`seeded_regression C-002@11`).

---

## Phần mở rộng v2 (Advanced & Expert M5–M7)

### 1. Phân tích nhiễu A/A và Thiết lập ngưỡng
- Chạy A/A trên 2 bộ seed khác nhau (`11,22,33,44,55` so với `66,77,88,99,110`) trên cùng agent `swarm`.
- **Kết quả A/A:** Trên MockLLM, $\Delta = 0.0000$ trên toàn bộ các metric do tính tất định (determinism).
- **Ý nghĩa với LLM thật:** Với LLM thật ngoài production, dải nhiễu A/A luôn lớn hơn 0 (thường dao động trong khoảng $\pm 3\%\text{--}5\%$). Nếu đặt ngưỡng sàn nằm bên trong dải nhiễu này, các PR trung thực sẽ bị chặn ngẫu nhiên (false alarms). Do đó, các sàn chặn (blocking floors) như `pass_hat_5 \ge 0.80` và `slice:money_movement \ge 0.90` được chọn nằm hoàn toàn **ngoài dải nhiễu A/A**.

### 2. Phân tích Slice và Cơ chế phát hiện lỗi
- **`slice:money_movement` (min 0.90, blocking):**
  - Chặn đứng biến thể `slice_regression`. Ở biến thể này, lỗi cộng gộp điều khoản chỉ xuất hiện ở các claim có phát sinh tiền (`money_movement`) trên seed lẻ.
  - Điểm `pass_rate` trung bình toàn cục của `slice_regression` vẫn đạt **0.9357** (trên sàn tổng thể 0.85) và CI chạm 0, khiến gate thông thường bị đánh lừa. Duy nhất lát cắt `slice:money_movement` (tụt xuống 0.8500 < 0.90) phát hiện và chặn thành công hồi quy này.
- **Metric `pass_hat_5` (min 0.80, blocking):**
  - Đo lường xác suất một claim vượt qua ở toàn bộ 5/5 seed ($pass^5$).
  - Chặn đứng biến thể `flaky_regression` (lỗi làm tròn xuất hiện ở 1/5 seed). Điểm trung bình `pass_rate` vẫn cao nhưng `pass_hat_5` sụt giảm mạnh, phản ánh agent thiếu ổn định.
- **Scorecard đột biến (Mutation Score):**
  - `fixed`: **MERGE** (không báo nhầm)
  - `honest_refactor`: **MERGE** (thay đổi câu từ, thêm bước tra cứu nhưng kết quả bảo toàn $\rightarrow$ không báo nhầm)
  - `seeded_regression`: **BLOCK**
  - `slice_regression`: **BLOCK** (bởi `slice:money_movement/pass_rate`)
  - `flaky_regression`: **BLOCK** (bởi `pass_hat_5`)
  - **Tỉ lệ đột biến:** Chặn 3/3 regressions (100%), 0 false alarms.

### 3. Cơ chế kiểm tra tính toàn vẹn (Integrity Gate) & Chống gian lận
Gate cài đặt hàm `integrity_check` ngăn chặn triệt để 4 hành vi gian lận kết quả eval:
1. `evaluator_errors_as_nan`: Grader gặp lỗi crash làm giá trị thành NaN/None và bị rơi khỏi trung bình $\rightarrow$ **BLOCKED**.
2. `dropped_failing_rows`: Tự ý xóa bớt các dòng bị fail để tăng pass rate $\rightarrow$ **BLOCKED** (kiểm tra `len(rows) == items * len(seeds)`).
3. `cherry_picked_seeds`: Chỉ chọn nộp các seed có kết quả đẹp $\rightarrow$ **BLOCKED** (đối chiếu tập `(item_id, seed)` với baseline).
4. `loosened_spec`: Tự ý nới lỏng ngưỡng min hoặc bỏ slice trong cùng PR $\rightarrow$ **BLOCKED** (cơ chế Ratchet kiểm tra `--base-spec`).

### 4. Giới hạn cỡ mẫu (Sample Size Limitations)
- Một lỗi hồi quy chỉ xuất hiện với tần suất $1/3$ seed (`rare` bug) **không thể** được phát hiện ổn định chỉ với 5 seed thử nghiệm:
  $$\text{P}(\text{không phát hiện}) = \left(\frac{2}{3}\right)^5 \approx 13.17\%$$
- Với xác suất lọt lưới hơn 13%, không nên hạ thấp ngưỡng sàn một cách gượng ép (điều này chỉ làm tăng false alarms trên các PR tốt). Để bắt được các lỗi hiếm một cách đáng tin cậy về mặt thống kê, phương pháp chuẩn xác là mở rộng số lượng seeds (ví dụ tăng lên 20--50 seeds) hoặc mở rộng tập eval set.

---

- **Gate owner:** Đỗ Duy Tùng (Eval Owner / QA Lead).
- **Phạm vi pilot:** Bồi thường giao trễ và hàng hỏng cho đơn lẻ $\le 200.000$đ.
- **Kế hoạch v2.1:** Bổ sung tập dữ liệu người dùng thật từ production traces, mở rộng seeds khi cần kiểm tra các failure mode hiếm gặp.
