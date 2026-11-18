# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt (κ=0.757 ≥ 0.6, P=0.857 ≥ 0.8, R=0.800 ≥ 0.7) | Dùng làm gate |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không đạt (κ=0.375 < 0.6, R=0.300 < 0.7) | Loại (không dùng làm gate) |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & Hành động sửa rubric |
|---|---|---|---|---|---|---|
| 1 | H-008 | PASS | FAIL | Người đúng | Reply xưng hô suồng sã: "Em đã hoàn tiền cho anh rồi nha, anh check giúp em". Cần thêm vào rubric tiêu chí cấm xưng hô thân mật cá nhân (em/anh/check/nha), yêu cầu xưng LogiX và Quý khách. |
| 2 | H-017 | PASS | FAIL | Người đúng | Reply dùng khẩu ngữ: "Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha". Sửa rubric tone để cấm các hạt từ cảm thán suồng sã ("bạn ơi", "rồi nha"). |
| 3 | H-029 | PASS | FAIL | Người đúng | Reply cộc lốc, gắt gỏng: "Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm." Judge bị đánh lừa bởi từ "Dạ" đầu câu. Sửa prompt judge: phát hiện câu từ gây khó chịu/đuổi khách. |
| 4 | H-042 | FAIL | PASS | Người đúng | Reply chuẩn mực: "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ". Judge bắt bẻ nhầm (FP). Cần làm rõ trong rubric câu ngắn gọn đủ ý vẫn đạt tone tốt. |
| 5 | H-051 | FAIL | PASS | Người đúng | Reply: "Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ". Judge phạt vì dùng từ tiếng Anh "refund". Rubric cần chấp nhận từ mượn phổ thông nếu phong cách tổng thể vẫn lịch sự. |
| 6 | HL-016 | PASS | FAIL | Người đúng | Judge helpfulness bị lừa bởi văn mẫu xin lỗi dài dòng nhưng không hề cung cấp thông tin giải quyết (mã đơn, hướng dẫn tiếp theo). Sửa rubric helpfulness: bắt buộc có giải pháp hành động cụ thể, không chỉ xin lỗi. |

## Kết luận
- **Tiêu chí bị loại**: `helpful` bị loại hoàn toàn khỏi CI gate vì Recall chỉ đạt 0.300 (sàn yêu cầu ≥ 0.7) và Cohen's Kappa chỉ đạt 0.375 (sàn yêu cầu ≥ 0.6). Ma trận nhầm lẫn: `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}`. Judge bỏ sót tới 21/30 trường hợp vi phạm thực tế (FN = 21), khiến tỷ lệ phát hiện lỗi cực kỳ kém; nó dễ bị qua mặt bởi các câu văn mẫu xin lỗi dài dòng rỗng tuếch.
- **Tiêu chí được chấp nhận**: `tone_ok` đạt chuẩn hiệu chuẩn (P=0.857, R=0.800, κ=0.757) và có thể sử dụng làm metric theo dõi hoặc gate có điều kiện.
- **Rủi ro còn lại**: Dữ liệu kiểm tra hiện tại chỉ là dữ liệu replay đã công khai (`judge_tone_public.csv`). Khi đưa vào thực tế cần bổ sung tập nhãn con người độc lập (held-out data) để chống overfitting vào rubric cũ.
