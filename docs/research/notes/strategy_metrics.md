# 전략 성과 평가·표시 지표 (백테스트 → 모의 → 실전), "잃을 땐 적게, 벌 땐 크게" vs S&P 500 ETF 보유

조사일: 2026-11-25. 수수료·세금 수치는 바뀌었을 수 있으니 출처별 기준일을 함께 적었습니다.

## 1. 지표 정의·공식·해석·함정, 그리고 "작게 잃고 크게 버는" 성격을 가장 잘 보여주는 지표

### Takeaway
"작게 잃고 크게 벌기"를 S&P 500 대비로 가장 직접 보여주는 것은 **하락 포착률(downside capture) < 100%와 상승 포착률(upside capture) ≈ 100% 이상의 조합**, 그리고 **최대 낙폭(MDD)·Ulcer Index·회복 기간**입니다. 거래 단위로는 **손익비(평균 이익/평균 손실)와 기대값(expectancy)**이 보조 지표입니다. Sharpe는 위·아래 변동을 똑같이 벌점으로 주므로 이 목표에 비해 덜 직접적입니다. Sortino, Calmar, Martin ratio가 더 맞습니다.

### Cited Findings
- **Sharpe**: SR = E[R_p − R_b] / σ_p. QuantConnect LEAN은 무위험수익률을 기본 0%로 둡니다 — [QuantConnect Glossary](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/glossary.md)
- **Sortino**: "Unlike the Sharpe ratio, the Sortino ratio only penalizes returns falling below a user-specified target." 공식은 S = (R_p − R_f)/σ_d이고, σ_d는 하방편차입니다 — [QuantConnect Glossary](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/glossary.md). empyrical은 downside_risk를 "downside deviation below a threshold"로 구하고 sqrt(평균제곱)×sqrt(연환산계수)를 씁니다 — [empyrical stats source](https://quantopian.github.io/empyrical/_modules/empyrical/stats.html)
- **Max drawdown**: "The largest peak to trough decline in an algorithm's equity curve." 공식은 1 − (s 이후 최저 자산)/(s까지 최고 자산)입니다 — [QuantConnect Glossary](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/glossary.md). empyrical 구현은 누적수익곡선을 직전 최고점으로 나눈 뒤 최솟값을 취합니다 — [empyrical](https://quantopian.github.io/empyrical/_modules/empyrical/stats.html)
- **Calmar**: 연수익률 / |MDD|입니다. MDD가 음수가 아니면 NaN을 돌려줍니다 — [empyrical](https://quantopian.github.io/empyrical/_modules/empyrical/stats.html)
- **Tail ratio**: |95번째 백분위 수익률| / |5번째 백분위 수익률|입니다. 오른쪽 꼬리(큰 이익)와 왼쪽 꼬리(큰 손실)의 비율입니다 — [empyrical](https://quantopian.github.io/empyrical/_modules/empyrical/stats.html)
- **Ulcer Index (Peter Martin)**: N기간 동안 직전 최고가 대비 하락률 R을 구하고 그 제곱평균제곱근(RMS)을 취합니다. 낙폭이 깊고 오래갈수록 커집니다. Martin은 최소 주 단위 이상으로 자주 샘플링하라고 권했습니다(긴 간격 사이의 하락·회복을 놓치기 때문). 상승 변동은 벌점으로 주지 않습니다 — [Wikipedia: Ulcer index](https://en.wikipedia.org/wiki/Ulcer_index)
- **Martin ratio (UPI)**: Sharpe의 표준편차 자리에 Ulcer Index를 넣은 값입니다. 비용 차감·배당 재투자 후 연수익률을 쓰고, 높을수록 좋습니다 — [Wikipedia: Ulcer index](https://en.wikipedia.org/wiki/Ulcer_index)
- **승률**: 수수료 차감 후 이익 거래의 비율입니다 (n_W/N) — [QuantConnect Glossary](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/glossary.md)
- **손익비(payoff / profit-loss ratio)**: PLR = 평균이익 / |평균손실|. 1보다 크면 평균 이익이 평균 손실보다 큽니다. QuantConnect는 문구에 "win rate/loss rate"라고 적었지만 공식은 평균 이익·손실을 씁니다(문서 자체의 불일치) — [QuantConnect Glossary](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/glossary.md)
- **기대값(expectancy)**: E = 승률×평균이익 + 패율×평균손실(손실은 음수)이며 거래당 기대수익입니다. 양수여야 장기적으로 수익이 납니다 — [QuantConnect Glossary](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/glossary.md)
- **Information ratio**: (R_p − R_b)/추적오차입니다 — [QuantConnect Glossary](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/glossary.md)
- **상승/하락 포착률**: 상승 포착률은 벤치마크가 플러스인 달만, 하락 포착률은 마이너스인 달만 씁니다. 그 달들의 펀드·지수 수익률 기하평균을 비교합니다. 상승 >100은 상승장에서 지수를 이겼다는 뜻이고, 하락 <100은 하락장에서 덜 잃었다는 뜻입니다. 예시로 Mawer Canadian Equity의 3년 수치는 상승 96.34%, 하락 19.74%였습니다(상승장은 거의 따라가고 하락의 약 20%만 맞음). 대부분은 상충관계여서, 상승 포착이 크면 방어력이 약한 경향이 있습니다 — [Morningstar](https://global.morningstar.com/en-ca/personal-finance/what-are-upside-and-downside-capture-ratios)
- **포착률의 함정**: 스타일이 벤치마크와 크게 다르면 비율이 실력이 아니라 스타일 차이를 반영합니다. 단독 판정에 쓰지 말고 다른 위험 지표와 함께 보라고 합니다 — [Morningstar](https://global.morningstar.com/en-ca/personal-finance/what-are-upside-and-downside-capture-ratios); 정의 "fund's upside capture return ÷ benchmark's upside capture return" — [Morningstar glossary](https://awgmain.morningstar.com/webhelp/glossary_definitions/mutual_fund/Upside_Capture_Ratio.htm)
- **용량(capacity)**: 시장충격 때문에 성과가 나빠지기 전까지 운용할 수 있는 최대 금액입니다 — [QuantConnect Glossary](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/glossary.md)

### Inferences
- 비전문가용 핵심 카드(제안): ① **S&P 500 대비 하락 포착률 / 상승 포착률**(한 줄: "지수가 1 빠질 때 0.x 빠지고, 1 오를 때 0.y 오름"), ② **MDD + 최장 낙폭 지속·회복 기간**(지수와 나란히), ③ **CAGR(세후)**, ④ **Calmar 또는 Martin ratio**, ⑤ 거래형 전략이면 **손익비·기대값**을 함께 봅니다. Sharpe·Sortino·Ulcer·tail ratio·회전율은 "자세히" 영역에 둡니다.
- 승률은 단독으로 오해를 부릅니다. 승률이 낮아도 손익비가 크면 "작게 잃고 크게 버는" 전략일 수 있습니다(추세추종이 전형). 반대로 승률이 높고 손익비가 작으면 꼬리위험 신호입니다. 기대값이 이 둘을 합친 값입니다.
- Profit factor(총이익/총손실)는 위 출처에 정의가 없습니다. 통상 쓰는 정의이며 기대값과 같은 정보를 다른 형태로 보여줍니다.
- 롤링 수익률(예: 1년·3년 롤링 초과수익의 분포, 지수를 이긴 구간의 비율)은 "운 좋은 한 구간" 착시를 줄여줍니다. 별도 1차 출처는 확인하지 못했습니다(Gaps 참조).
- MDD는 표본 하나의 최악값이라 기간이 길수록 커지기 쉽습니다. 같은 기간의 지수 MDD와 나란히 보여줘야 공정합니다.

### Gaps
- 낙폭 지속·회복 기간, 회전율, 롤링 수익률은 공식 문서 출처를 따로 확보하지 못했습니다(정의는 표준적이지만 인용 없음).
- Portfolio Visualizer·CFA Institute 원문은 조회하지 못했습니다.

## 2. 과최적화 방지: 표본외·워크포워드·Deflated Sharpe·PBO·시도 횟수·최소 기록 길이

### Takeaway
여러 전략을 시험해 최고를 고르면 Sharpe는 우연만으로 부풀려집니다. **시도 횟수를 기록하고, 그 횟수로 보정한 Deflated Sharpe Ratio(DSR)가 0.95 이상인지**, **PBO(CSCV)**, **손대지 않은 홀드아웃 구간 성과**를 "통과/주의" 배지로 단순하게 보여주는 것이 실용적입니다.

### Cited Findings
- **DSR**: Probabilistic Sharpe Ratio의 기준값을 0 대신 "N번 시도했을 때 잡음만으로 기대되는 최대 Sharpe"로 바꾼 것입니다. 결과는 확률이고, 귀무가설을 기각할 수 있는 최대 신뢰도로 해석합니다. 입력은 유효 독립 시도 수 N(비슷한 전략을 군집해 추정), 왜도, 첨도, 표본 길이 T, 시도들 사이 Sharpe의 분산입니다. Sharpe가 높을수록, 기록이 길수록, 왜도가 양수일수록 DSR이 오르고 꼬리가 두꺼울수록(첨도↑) 내려갑니다. 95% 신뢰 수준 사용 예가 있습니다 — [Wikipedia: Deflated Sharpe ratio](https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio); 원 논문 [Bailey & López de Prado, SSRN 2460551](https://papers.ssrn.com/abstract=2460551)
- **PSR 공식**: P(ŜR > SR*) = Φ( (ŜR − SR*)·√(n−1) / √(1 − γ₃·ŜR + ((γ₄−1)/4)·ŜR²) ). n은 거래일 수, γ₃는 왜도, γ₄는 첨도입니다 — [QuantConnect Glossary](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/glossary.md)
- **최소 기록 길이(MinTRL)**: 관측 Sharpe로 귀무가설을 기각하는 데 필요한 최소 표본 길이입니다. 예시로 95% 신뢰에 일간 수익률 약 3년이 필요하고, Sharpe가 1.15를 넘으면 2년으로 줄어듭니다. 시도가 하나라는 가정이므로 시도가 많으면 더 길어야 합니다 — [Wikipedia: Deflated Sharpe ratio](https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio)
- **PBO**: 백테스트 결과가 실력이 아니라 과최적화일 확률입니다. CSCV(combinatorially symmetric cross-validation)로 추정하며, 논문은 홀드아웃 같은 통상적 방법이 투자 백테스트에서는 "unreliable and inaccurate"하다고 주장합니다 — [Bailey, Borwein, López de Prado, Zhu, SSRN 2326253](https://papers.ssrn.com/abstract=2326253)

### Inferences
- 화면 제안: 전략 카드마다 "시험한 변형 수: N", "DSR: 0.97 ✓ / 0.62 ⚠", "홀드아웃 Sharpe vs 학습구간 Sharpe", "PBO: 18%"를 보여줍니다. 비전문가 문구는 "N개를 시험해서 고른 1등이 운일 확률 ≈ 1−DSR" 정도로 씁니다(근사 설명).
- 시도 횟수를 자동 기록하려면 실험 레지스트리(파라미터·기간·결과를 매 실행 DB에 저장)가 필요합니다. 기록이 없으면 DSR을 계산할 수 없습니다.
- 워크포워드(구간을 굴리며 학습→다음 구간 검증)와 마지막 몇 년 홀드아웃을 "한 번만 열람"하는 규칙을 함께 쓰는 것이 일반적인 실무 관행입니다. 다만 PBO 논문은 단일 홀드아웃만으로는 부족하다고 봅니다.
- 미래 데이터 금지(공시일·발표일 기준, 다음 거래일 체결)는 과최적화와 별개인 look-ahead 방지 장치입니다.

### Gaps
- 워크포워드 분석의 권위 있는 1차 출처(Pardo 등)는 이번 조사에서 확보하지 못했습니다.
- DSR·MinTRL의 정확한 수식 전문은 위키 추출에서 빠졌습니다. 구현할 때는 원 논문(SSRN 2460551, 2465675)을 직접 확인해야 합니다.

## 3. 모의투자 기간과 비교 대상

### Takeaway
통계적으로 "실력 확인"에는 MinTRL 기준 수년이 필요하므로, 모의투자는 **전략 검증이 아니라 실행 검증**(체결·비용·신호 재현)으로 정의하는 게 현실적입니다. 비교는 "같은 기간 백테스트 재실행 결과 vs 모의 결과"의 추적오차로 합니다.

### Cited Findings
- 95% 신뢰로 Sharpe를 확인하려면 일간 데이터 약 2~3년이 필요합니다(Sharpe 1.15 이상이면 약 2년) — [Wikipedia: Deflated Sharpe ratio](https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio)
- 추적오차는 IR 정의의 분모 σ(R_p − R_b)와 같은 개념입니다 — [QuantConnect Glossary](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/glossary.md)

### Inferences
- 제안 기준: 최소 **3개월 또는 리밸런싱·매매 20~30회 이상** 중 긴 쪽을 실행 검증 기간으로 둡니다. 이 수치는 실무 휴리스틱이며 출처는 없습니다. 실력 판단은 백테스트의 DSR·홀드아웃으로 하고, 모의는 다음을 봅니다: (a) 신호 일치율(백테스트가 낸 주문과 모의 주문이 같은지), (b) 일별 수익률 차이의 평균·표준편차(추적오차), (c) 가정 체결가 대비 실제 체결가 차이(슬리피지, bp), (d) 누락·지연 주문 수.
- 월 1회 리밸런싱처럼 저빈도 전략은 몇 달로는 표본이 너무 적습니다. "이 기간으로는 성과 우열을 판정할 수 없음"을 화면에 명시합니다.
- 모의 성과를 백테스트 기대 분포(예: 같은 길이 구간들의 롤링 수익 5~95% 범위) 위에 겹쳐 그리면, 범위 안이면 "정상", 밖이면 "점검"처럼 비전문가도 판단할 수 있습니다.

### Gaps
- 모의투자 최소 기간에 대한 학술·규제 기준은 찾지 못했습니다.
- KIS 모의계좌의 체결 방식(실시간 호가 반영 정도)은 이번 조사 범위에서 확인하지 못했습니다.

## 4. 비용·세금 현실화 (한국 거주자, 미국 상장 ETF)

### Takeaway
해외주식 양도차익은 연간 손익을 통산해 **250만 원 공제 후 22%(지방세 포함)**로 과세되고, 미국 배당은 **15% 원천징수**로 국내 추가 과세가 없습니다(금융소득 2천만 원 이하일 때). 매매가 잦은 전략은 이익을 매년 실현하므로 과세 이연 효과를 잃고, 수수료·환전 스프레드도 쌓여 세후 순위가 S&P 500 장기보유보다 크게 밀릴 수 있습니다. 증권사 요율은 이벤트·규제로 자주 바뀌어 **확인 필요**합니다.

### Cited Findings
- 양도세율 20% + 지방세 2% = 22%. 연간 순이익 250만 원까지 비과세이고 초과분에 과세합니다. 해외주식끼리 연내 손익 통산(예: 이익 900만 − 손실 300만 = 600만, 250만 공제 후 과세). 다음 해 5월 홈택스 신고 또는 증권사 대행이고, 250만 원 이하는 신고 의무가 없습니다. 무신고 가산세 20%, 과소신고 10%, 납부지연 하루 0.022%. 연도별로 나눠 팔아 공제를 매년 쓰는 방법을 소개합니다 (KB Think, 2025-11-26 갱신) — [KB Think](https://kbthink.com/stock/foreign-tax.html)
- 배당: 미국 원천징수 15%, 한국 세율은 14%(지방세 포함 15.4%)이고 외국 세율이 더 높아 미국 배당에는 국내 추가세가 없습니다. 이자+배당이 연 2천만 원을 넘으면 금융소득종합과세(6.6~49.5%) 대상이며, ISA 가입 제한·건보료 증가 가능성이 있습니다 — [KB Think](https://kbthink.com/stock/foreign-tax.html)
- 국세청 안내 페이지는 자동 조회가 막혀 직접 확인하지 못했습니다 — [국세청](https://www.nts.go.kr/nts/na/ntt/selectNttInfo.do?nttSn=1350890)
- 한국투자증권(뱅키스): 2024-08 기사 기준으로 해외주식 첫 거래 고객 3개월 수수료 면제와 미국 매도 SEC Fee(0.00278%) 면제, 이후 9개월 할인(요율 미기재), USD 환전 최대 90% 우대 이벤트가 있었습니다 — [메트로신문 2024-08-28](https://www.metroseoul.co.kr/article/20240828500359)
- 타사 참고: 미래에셋 미국주식 온라인 0.25%·오프라인 0.50%, KB 온라인 달러 기본 우대 50%, 삼성 우대 미적용 시 환전 스프레드 1.00%, 95% 우대 시 0.05%(2024 이벤트 기준). 확인일은 2026-10-30이나 기준일 미표기인 2차 블로그 출처입니다 — [tilnote](https://tilnote.io/pages/6af8864558258d5dd1a11dbf.md)
- 2025년 말 금융위원회의 해외주식 마케팅 제한 조치로 '수수료 0원' 이벤트가 줄었습니다(메리츠 Super365 0원 이벤트 2026-01-05 종료, 미국 수수료 0.07% 유지) — [뉴스토마토/IB토마토 2026-01-30](https://newstomato.com/ReadNews.aspx?no=1289451)

### Inferences
- 백테스트 기본 비용 가정(보수적, 확인 필요): 매매 수수료 **편도 0.25%**(이벤트 없는 통상 온라인 요율 수준), 미국 매도 SEC fee(소액), 원↔달러 환전 시 **스프레드 1% × (1 − 우대율)**. 달러로 계속 보유하며 매매하면 환전 비용은 입출금 때만 듭니다. 화면에서 이 값들을 사용자가 바꿀 수 있게 합니다.
- 세후 비교 예시(가정, 계산 예): S&P 500 ETF를 10년 보유하면 양도세는 매도 시점에 한 번(+매년 250만 공제는 사실상 1회만 활용)입니다. 반면 매년 이익을 실현하는 전략은 매년 22% 과세되고 공제를 매년 쓸 수 있습니다. 소액 계좌(연 실현이익 ≲250만 원)는 회전 전략이 오히려 공제를 더 잘 씁니다. 금액이 커질수록 과세 이연을 잃는 비용이 커집니다. 따라서 **세후 CAGR은 계좌 규모에 따라 순위가 바뀔 수 있으므로** 규모를 입력받아 계산해야 합니다.
- 연간 손익 통산은 해외주식끼리만 확인됐습니다. 연말에 손실 종목을 실현해 이익과 상계하는 tax-loss harvesting 효과를 시뮬레이터에 넣을 수 있습니다.
- 환율 효과: 원화 기준 성과는 USD/KRW 변동을 포함합니다. 벤치마크(S&P 500 ETF)도 같은 원화 기준으로 계산해야 공정한 비교가 됩니다. 양도차익의 환율 기준(취득·양도일 기준환율)은 이번에 1차 확인하지 못했습니다.
- 세후 성과 표시 방식 제안: "세전 / 비용 차감 / 세후" 3단 막대 또는 워터폴로 보여주고, 각 전략을 같은 원화·세후 기준으로 S&P 500 ETF 보유와 비교합니다.

### Gaps
- 한국투자증권의 **현재(2026) 미국주식 기본 수수료율과 환전 우대율**은 공식 페이지 자동 조회가 차단돼 확인하지 못했습니다. 앱이나 [수수료 안내 페이지](https://securities.koreainvestment.com/main/customer/guide/_static/TF04ae010000.jsp?tab=2)에서 사람이 직접 확인해야 합니다.
- 양도차익 계산 시 환율 기준, 수수료의 필요경비 인정 여부, 국내주식과의 통산 여부는 1차 출처로 확인하지 못했습니다(국세청 페이지 접근 실패).
- 2025~2026 세법 개정으로 해외주식 과세 체계(공제액·세율)가 바뀌었는지 1차 출처로 재확인하지 못했습니다. 검색된 2026년자 블로그들은 22%·250만 원을 유지한다고 적고 있으나 2차 출처입니다.
- 미국 ETF 배당 중 15% 원천징수 대상이 아닌 성격의 분배금(자본이득 분배 등) 처리는 다루지 못했습니다.

## 5. 실전 모니터링 필수 요소: 주문·체결 로그, 슬리피지, 킬 스위치·손실 한도

### Takeaway
Knight Capital 사례(45분, 4.6억 달러 손실)는 **주문 직전 사전 점검, 자본 한도 초과 주문 차단, 경고 알림에 대한 대응 절차, 배포 테스트**가 없을 때 생기는 일을 보여줍니다. 개인 시스템도 축소판으로 같은 4가지를 갖춰야 합니다.

### Cited Findings
- 2012-08-01, 개장 후 45분 동안 Knight의 라우터가 212건 고객 주문을 처리하려다 400만 건 이상의 주문을 냈습니다. 3억 9,700만 주 이상이 체결됐고 손실은 4억 6천만 달러를 넘었습니다. 원인은 오래된 미사용 코드가 남아 있는 상태에서 새 코드가 잘못 배포된 것이고, 라우터는 주문이 체결된 것을 인식하지 못했습니다. 개장 전 97통의 자동 경고 메일이 왔지만 아무도 조치하지 않았습니다 — [SEC 보도자료 2013-222](https://www.sec.gov/news/press-release/2013-222)
- SEC가 지적한 결여된 통제: 주문이 시장에 가기 직전 점검(라우터 출력 주문과 입력 주문 비교) 없음, 자본 한도 초과 주문 차단 불가, 체결 계좌가 전체 익스포저 자동 통제에 연결되지 않음, 코드 테스트·배포 절차 미흡, 사고 대응 문서 미비. 벌금은 1,200만 달러였습니다 — [SEC 보도자료 2013-222](https://www.sec.gov/news/press-release/2013-222)

### Inferences
- 개인 자동매매 최소 구성(제안):
  1. **주문 로그**: 신호 시각, 의도 주문(종목·방향·수량·기준가), 제출 시각, 응답, 체결가·수량, 수수료를 모두 DB에 append-only로 남깁니다. 실데이터는 공개 저장소·로그 출력에 남기지 않습니다.
  2. **슬리피지 리포트**: (체결가 − 신호 기준가)/기준가를 bp로 계산해 주문별·월별 평균을 보여줍니다. 백테스트 비용 가정을 넘으면 경고합니다.
  3. **사전 점검(pre-trade check)**: 1회 주문 금액 상한, 일일 주문 건수·금액 상한, 보유 비중 상한, 같은 주문 중복 차단, 기준가 대비 호가 괴리 상한을 둡니다. Knight의 "입력 대비 출력 주문 비교"와 "자본 한도 차단"의 축소판입니다.
  4. **킬 스위치**: 기본값 OFF(주문하지 않음). 일간·누적 손실 한도(예: 계좌 대비 X%)나 슬리피지·주문 수 이상치에 걸리면 자동으로 신규 주문을 중단하고, 사람이 수동으로 다시 켜야 합니다. 한 번 탭으로 끌 수 있는 모바일 스위치를 둡니다.
  5. **알림 대응**: 경고는 확인(ack)이 필요하게 만들어 "97통의 무시된 메일"을 막습니다.
  6. **배포 안전**: 실전 반영 전에 모의 환경에서 같은 코드를 일정 기간 돌리고, 전략 버전을 주문 로그에 기록합니다.
- 화면에는 "오늘 주문 n건 / 한도 m건", "누적 손실 −x% / 한도 −y%", "평균 슬리피지 z bp / 가정 w bp", 킬 스위치 상태를 상단 고정으로 둡니다.

### Gaps
- 개인 투자자용 손실 한도 수치(%)의 권위 있는 기준은 찾지 못했습니다. 위 수치는 사용자가 정할 값입니다.
- KIS API의 주문 제한·오류 코드·체결 통보 방식은 이번 범위에서 조사하지 않았습니다.
