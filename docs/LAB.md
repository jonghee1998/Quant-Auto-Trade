# 실험실 사용법

전략(규칙·예측 모델)을 같은 틀에서 백테스트하고 기준선(S&P 500 ETF 보유)과 비교한다. 코드: `quant/lab/`.

## 전략 만들기
`weights(as_of, history) -> {종목: 비중}` 하나만 구현한다. `history`에는 `as_of`까지의 가격만 들어 있고, 정한 비중은 **다음 거래일 종가**에 체결된다. 비중 합은 1 이하이며 나머지는 원화 현금이다. 예시: `quant/lab/strategy.py`의 `BuyAndHold`, `TrendFilter`.

## 실행
```python
from quant.lab.run import evaluate
from quant.lab.registry import Registry
m = evaluate(prices, fx, MyStrategy(...), hypothesis="왜 될 것 같은지", params={...},
             period="dev", registry=Registry("data/experiments.jsonl"),
             data_version="...", code_version="<git sha>")
```
- `prices`: 날짜×종목 달러 수정종가, `fx`: 원/달러(앞으로만 채움, 빈 시작 구간은 오류).
- 비용: 수수료·환전 스프레드(편도), 해외 양도세(연 공제 후 22%, 그해 마지막 거래일 납부). 끝까지 보유분은 `after_tax_if_liquidated`로 비교.
- 결과에는 기준선 지표(`bench_*`, `excess_cagr`, `monthly_win_rate`)와 시도 번호(`trial_no`)가 함께 나온다.

## 규칙
1. 가설·조절값 범위·통과 기준을 실행 **전에** 계획 Issue에 적는다.
2. `dev`·`valid`만 자유롭게 돌린다. `holdout`은 `final=True`로 전략당 한 번(코드·DB 제약으로 막힘).
3. 모든 실행은 기록된다. 결과를 볼 때 시도 횟수를 같이 본다.
4. 통과하면 모의투자 3개월 → 사람 승인 → 소액 실전.

## 역할
가설 카드·결과 분석: Fable(안 되면 Opus) · 구현: Sonnet/Opus · 미래 데이터 누수 검수: Codex.
