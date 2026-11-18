# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

## Bảng phân tích case

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID: `R-seeded_regression-C-002-s11` |
| Triệu chứng | Lab 8 grader FAIL (`status resolved != denied`); ledger ghi nhận `refund_vnd=20000` (nhãn kỳ vọng `0`); reply nói: *"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."* |
| Bước sai đầu tiên | Event 3: `model_override {"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event 1 (`handoff`) và Event 2 (`investigator` lookup_order) đều đọc đúng dữ liệu từ DB (`delay_days=2`). Bước 3 là thời điểm đầu tiên agent tự ý ghi đè dữ liệu DB bằng thông tin trong ticket khách hàng, dẫn đến Event 4 quote sai 20.000đ. |
| Failure mode | `FM-03` (ticket_trust — tin thông tin trong ticket hơn dữ liệu xác thực từ DB) |
| Đối chứng | Cùng claim C-002@11 trên shape `fixed`: không xuất hiện event `model_override`; quote trả về 0đ (`no_entitlement`); reply từ chối bồi thường và ledger `refund_vnd=0` đúng với nhãn. |
| Regression test | Grader `DbFactKept` và `RefundAmountCorrect` trong `src/lab9/graders.py` (kiểm thử qua `test_override_event_breaks_db_fact` và `test_wrong_amount_in_ledger`). Bắt được lỗi trên `seeded_regression` (FAIL) và vượt qua trên `fixed` (PASS). |
| Chưa chắc chắn | Trace chỉ thể hiện agent tin ticket qua heuristic/prompt; chưa chứng minh được agent có khả năng nhận biết bằng chứng ảnh/biên bản giao hàng hợp lệ nếu có sau này. |
