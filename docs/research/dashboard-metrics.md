# 시장 소식보다 '내 전략 성적표'를 앞에 세우자

해외 퀀트 도구(Portfolio Visualizer, QuantConnect, Composer, TradingView, Bloomberg PORT)는 거의 모두 같은 뼈대를 씁니다. **벤치마크(SPY·그냥 산 사람) 대비 자산 곡선, 낙폭 차트, 연수익률·변동성·MDD·샤프 같은 짧은 KPI 줄, 기간별 수익률, 매매·보유 기록**입니다. 국내 로보어드바이저의 공식 성적표(코스콤 RA 테스트베드)는 이보다 더 단순해서 **누적수익률과 샤프를 같은 기간 지수와 나란히** 보여줍니다. 우리 시안은 시장 화면(오늘·트렌드·지표 상세·데이터 상태)이 이미 촘촘합니다. 반면 목표인 "잃을 땐 조금, 벌 땐 많이"를 직접 재는 지표, 즉 **상승/하락 포착률, 낙폭 회복 기간, 세후 원화 기준 비교, 시도 횟수 보정(DSR)**은 실험실 카드에 없습니다. 모의투자 화면도 성과 비교에 머물러 있고, '실행이 백테스트대로 되는가'를 보지 않습니다. 시장 지표 중 "적게 잃기"에 근거가 가장 강한 것은 **S&P 500이 10개월(약 200일) 이동평균 위에 있는지 보는 추세 신호등** 하나입니다. HY 스프레드는 근거는 좋지만 FRED에서 3년치만 받을 수 있고 재배포가 제한됩니다. 그래서 우선순위는 세 가지입니다. 첫째, 실험실·모의 화면에 위 지표와 과최적화 배지를 넣습니다. 둘째, 시장 화면에 추세 신호등과 '내 전략 한 줄'을 넣습니다. 셋째, 검증되지 않은 '한 달 전망' 꼬리표 같은 예측 표시를 빼거나 범위 표현으로 바꿉니다.

## 일곱 개 플랫폼이 공유하는 다섯 칸짜리 성적표

### 플랫폼별 화면 구성 요약

| 플랫폼 | 화면 구성 | 이 앱에 가져올 점 |
|---|---|---|
| Portfolio Visualizer | 한 페이지 긴 리포트입니다. 순서는 Highlights → 성장 곡선(로그·물가조정) → 성과 요약 → 연간·월간 수익률 → Up vs Down Market → 위험·수익 지표 표 → 낙폭 차트·구간 표(포트폴리오와 SPY 따로) → 역사적 스트레스 구간 → 자산별 기여 → 롤링 1~10년 수익률입니다 ([PV](https://www.portfoliovisualizer.com/backtest-portfolio)) | 상승/하락 포착률, 낙폭 구간 표(시작·끝·회복 기간), 위기 구간 표 |
| QuantConnect | 상단 KPI 띠(Equity·Fees·Net Profit·PSR 등)가 있고, 그 아래 자산·낙폭·벤치마크·노출·회전율 차트가 있습니다. 탭은 Overview·Orders·Trades·Logs·Code입니다 ([QC Results](https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/results)). 리포트에는 월간 히트맵, 상위 5개 낙폭, 롤링 베타·샤프, Crisis Events가 들어갑니다 ([QC Report](https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/report)). **실전 화면은 백테스트와 같은 배치에 Holdings·Errors 탭을 더한 형태입니다** ([QC Live](https://www.quantconnect.com/docs/v2/cloud-platform/live-trading/results)) | 실험실→모의→실전을 같은 배치로 통일. Code 탭으로 결과와 코드 버전을 묶는 방식 |
| Composer | **기본 벤치마크가 SPY**입니다. 지표는 누적·연환산·최근 1·3개월 수익률, 샤프, 표준편차, MDD, 칼마, 알파·베타·R²이고 일별 보유 내역도 보여줍니다. 수수료·슬리피지(기본 1bp)를 기본으로 포함하며, 백테스트를 "과거에 이렇게 됐어야 했다"로 설명합니다 ([Composer](https://help.composer.trade/article/215-7-how-do-backtests-work-in-composer)) | 비용 포함을 기본값으로. '샤프 3 초과는 의심' 경고, 보유 내역 |
| TradingView Strategy Tester | Buy & Hold 대비 PnL 곡선, 손익비·기대값, 승률, 평균 보유 봉 수, 낙폭·런업을 보여줍니다 ([TradingView](https://www.tradingview.com/support/solutions/43000681733-overview-tab/)) | 스윙 전략의 거래 단위 지표 |
| Bloomberg PORT | 탭이 PM의 질문 순서를 따릅니다. 오늘(Intraday) → 기간 성과 → 기여(Attribution) → 보유 특성 → 추적오차 → VaR → 시나리오 → 매매 시뮬레이션 순입니다 ([PORT 브로슈어](https://ftl.hsu.edu.hk/wp-content/uploads/2019/10/port_portfolio_and_risk_analytics-brochure.pdf)) | "오늘 → 기간 → 왜 → 무엇을 보유 → 위험" 순서만 가져오고, 팩터 모델은 생략 |
| Koyfin·Finviz·StockCharts·TradingView 히트맵 | 지수·자산 타일과 기간 선택이 있습니다. 섹터 히트맵은 크기=시총, 색=등락률입니다 ([TradingView](https://www.tradingview.com/support/solutions/43000766446)). 관심목록이 차트를 바꾸는 연결 위젯이 있고 ([Koyfin](https://www.koyfin.com/help/mydashboards-myd)), 섹터 ETF를 SPY 대비로 보는 RRG도 있습니다. StockCharts는 RRG가 매매 시스템이 아니라고 명시합니다 ([StockCharts](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-types/relative-rotation-graphs-rrg-charts.md)) | 트렌드 탭을 단순화하는 근거 |
| 국내(코스콤 RA 테스트베드·인텔리퀀트·토스증권) | RA 테스트베드 보도는 **평균 누적수익률과 샤프로 순위를 매기고, 코스피 총수익지수와 채권지수를 함께 제시**했습니다 ([데일리안](https://www.dailian.co.kr/news/view/1441566/)). 인텔리퀀트는 누적수익률·CAGR·'실제 수익률' 그래프를 씁니다 ([iQ레터](https://maily.so/iqletter/posts/8mo543wkz9p)). **토스증권 홈은 시장 지수보다 내 계좌를 먼저 보여주고** 호가창·보조지표를 덜어냈습니다 ([brunch](https://brunch.co.kr/@uibowl/410)) | 홈 첫 줄은 '내 전략 상태', 시장은 작은 띠로 |

### 공통 필수 요소와 니치 요소

플랫폼 문서를 교차 비교하면 공통 필수는 다섯 칸입니다. **벤치마크 대비 자산 곡선, 낙폭(underwater) 차트, CAGR·변동성·MDD·샤프 KPI, 연·월 수익률, 매매·보유 기록**입니다. 퀀트 도구에서 흔하지만 필수는 아닌 것은 소르티노, 칼마, 알파·베타, 추적오차·IR, 롤링 지표, 위기 구간 표입니다. VaR, 팩터 기여 분석, 운용 용량(capacity), 최적화기, RRG, Finviz Matrix는 기관용이거나 니치입니다(위 표의 출처를 종합). 눈에 띄는 점이 있습니다. "잃을 땐 조금"을 가장 직접 재는 **상승/하락 포착률은 조사한 플랫폼 중 Portfolio Visualizer에서만 확인**됐습니다. 대중 플랫폼의 기본 지표 묶음이 이 목표에 맞춰져 있지 않다는 뜻입니다. 우리 앱은 이 지표를 앞에 내세워 차별화할 수 있습니다. 비용 표시도 마찬가지입니다. QuantConnect는 Total Fees와 회전율 차트를, Composer는 비용 토글을 1급 요소로 둡니다. 우리 앱의 공통 세금·수수료 카드는 방향이 맞습니다.

국내 플랫폼(젠포트·퀀터스·핀트·파운트)의 실제 화면 구성은 다음 세 가지를 텍스트 출처로 확인하지 못했습니다. 모의/실전 배지, 리밸런싱 로그 형식, 세금 표시 방식입니다. 국내 비교 근거는 코스콤 보도와 백테스트 리포트 가이드 수준에 머뭅니다.

## 우리 시안은 시장 정보는 넘치고 '목표 판정'은 비어 있다

시안의 시장 탭은 Koyfin·StockCharts의 공통 요소를 이미 대부분 갖췄습니다. 지수 타일, 기간별 변화, 관심목록, 상위·하위 순위, 지표 상세, 데이터 상태입니다. 빈 곳은 투자 탭입니다. 실험실 카드에는 연수익률과 최악 손실만 있고, 이것만으로는 후보 기준인 '손익비 > S&P'와 '최악 손실이 S&P의 절반대'를 일관되게 판정할 수 없습니다. 또 하나의 위험이 있습니다. 관심 종목의 '한 달 전망 꼬리표'와 '데이터가 고른 좋은 3·나쁜 3'은 검증되지 않은 예측을 시장 화면에서 사실처럼 보이게 만들 수 있습니다. Composer와 SEC 마케팅 규칙의 원칙은 백테스트·예측을 '가상 성과'로 표시하고 가정과 한계를 함께 밝히라는 것입니다 ([Troutman Pepper](https://www.troutman.com/insights/the-secs-new-marketing-rule-practically-speaking-hypothetical-performance.html)). 개인 앱은 이 규칙의 적용 대상은 아니지만 체크리스트로 쓸 만합니다.

### 화면별 추가할 것 / 뺄 것 / 바꿀 것

우선순위: **P1** = 다음 스텝에서 바로, **P2** = 모의투자 시작 전, **P3** = 여유 있을 때.

| 화면 | 구분 | 내용 | 우선순위 | 근거 |
|---|---|---|---|---|
| 시장 › 오늘 | 추가 | 맨 위 **'내 전략 한 줄'** 띠: 모의 전략의 시작 대비 수익, 같은 기간 S&P, 현재 낙폭 | P1 | 토스 홈은 내 자산이 먼저 ([brunch](https://brunch.co.kr/@uibowl/410)) |
| 시장 › 오늘 | 추가 | **추세 신호등**: S&P 500이 10개월선 위/아래인지, 월말 기준, 다음 거래일 반영 | P1 | 시장 지표 중 근거가 가장 강함(다음 절) |
| 시장 › 오늘 | 추가 | 금융 여건 한 칸: NFCI 상태(타이트/느슨, 발표 지연 표시) | P2 | FRED NFCI ([FRED](https://fred.stlouisfed.org/series/NFCI)) |
| 시장 › 오늘 | 바꿀 것 | 코스피는 '한국 현황' 작은 줄로 내리고, 원달러는 유지(원화 기준 성과에 직접 영향) | P3 | 한국은 현황만이라는 앱 범위 |
| 시장 › 오늘 | 유지 | '평소 수준/큰 움직임' 꼬리표, 한 달·1년 변화 | — | 구간 라벨이 비전문가 해석을 도움(알고랩·Composer 패턴) |
| 시장 › 트렌드 | 뺄 것 | 관심 종목의 **'한 달 전망' 꼬리표**(검증 전). 남긴다면 "과거 비슷한 상황 N번 중 M번 상승 + 80% 범위"로 바꿈 | P1 | Betterment는 중앙선+80% 범위+'보장 아님' 표시 ([Betterment](https://www.betterment.com/legal/goal-projection)) |
| 시장 › 트렌드 | 바꿀 것 | '좋은 3·나쁜 3'에 **어느 전략이 골랐는지, 그 전략의 단계(실험실/모의), 시도 횟수**를 표시. '검증 전' 배지는 유지 | P1 | 과최적화 배지(4절) |
| 시장 › 트렌드 | 바꿀 것 | 어디×무엇×기간 3중 필터 → 기본값 1개(미국 섹터 ETF, 3개월, SPY 대비) + '더 보기'. 섹터 ETF 상대강도 막대(SPY=0 기준선) | P2 | RRG·히트맵은 SPY 대비 섹터 ETF가 표준 예 ([StockCharts](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-types/relative-rotation-graphs-rrg-charts.md)) |
| 시장 › 트렌드 | 추가 | 관심 종목 **급등락 알림** | P3 | 토스의 핵심 초보 기능 ([토스피드](https://toss.im/tossfeed/article/new-year-resolution)) |
| 종목·ETF 상세 | 추가 | 최대낙폭 옆에 **회복 기간**, S&P 대비 **상승/하락 포착률** | P2 | PV 낙폭 표 ([PV](https://www.portfoliovisualizer.com/backtest-portfolio)) |
| 종목·ETF 상세 | 바꿀 것 | ETF는 PER·분기 매출 대신 ETF 고유 항목(보수·규모·상위 보유)을 우선. 재무는 **공시일 기준**임을 표시 | P2 | 미래 데이터 금지 규칙 |
| 지표 상세(VIX) | 바꿀 것 | '이 구간일 때 S&P 다음 1개월'에 **표본 수와 빈도 표현**("과거 24번 중 15번 상승")을 붙이고, 겹치는 구간 주의 문구 | P1 | 아이콘·빈도 표현이 가장 중립적 결정을 이끔 ([NSF PAR](https://par.nsf.gov/servlets/purl/10237358)) |
| 지표 상세 | 바꿀 것 | 관련 지표의 **하이일드 스프레드는 원값 공개 대신 '상태'**(최근 대비 상승/안정)만, 10년 평균은 표시 불가(3년치만 있음) | P1 | FRED 라이선스 ([FRED](https://fred.stlouisfed.org/series/BAMLH0A0HYM2)) |
| 데이터 상태 | 추가 | 소스별 **발표 지연**(NFCI 약 5일 등)과 **라이선스 메모** | P2 | FRED 메타데이터 |
| 용어 풀이 | 바꿀 것 | 각 용어에 '좋은 범위' 한 줄(예: 칼마 1~2 양호) | P2 | [알고랩](https://algolab.co.kr/blog/backtest-report-guide) |
| 투자 › 실험실 | 추가 | **후보 기준 체크리스트**(4절 표), 상승/하락 포착률, 회복 기간, 세후 원화 CAGR, 회전율·비용, **시도 횟수·DSR·홀드아웃** | P1 | 4절 |
| 투자 › 실험실 | 추가 | 자산 곡선 vs S&P(로그 선택), 낙폭 차트, 연도별 막대, 위기 구간 표(2008·2020·2022) | P1 | 공통 필수 5칸 |
| 투자 › 실험실 | 추가 | 실험 레지스트리(매 실행의 파라미터·기간·결과 저장) | P1 | DSR 계산의 전제 |
| 투자 › 모의투자 | 추가 | **실행 검증 패널**: 신호 일치율, 슬리피지 bp, 누락·지연 주문, 백테스트 재실행과의 추적오차, 기대 범위 띠 | P2 | 5절 |
| 투자 › 모의투자 | 추가 | "이 기간으로는 성과 우열을 판정할 수 없음" 고정 문구 | P2 | MinTRL 2~3년 |
| 투자 › 실제 투자 | 추가 | 상단 고정 **킬 스위치·한도 게이지**, 주문 로그, 경고 확인(ack), 전략 버전 | P2(실전 전 필수) | Knight Capital([SEC](https://www.sec.gov/news/press-release/2013-222)) |
| 세금·수수료 카드 | 바꿀 것 | 수수료 0.05% 임시값 → **보수적 기본값(편도 0.25%) + 사용자 수정**, 계좌 규모 입력에 따라 세후 순위 재계산 | P1 | 4절 비용 |

## 시장 지표는 추세 신호등 하나만 근거가 강하다

"적게 잃기"에 쓸 시장 지표를 근거 강도 순으로 정리하면 결론은 분명합니다. 추세 필터가 가장 강하고, 나머지는 맥락용입니다. 1926년부터의 Faber식 월간 주식/채권 전환은 **연 1.4회 정도 전환**했고, 60/40을 **롤링 5년 구간의 78%에서 이겼습니다**. 하지만 전환 시점에 이미 **평균 -10.9%**를 맞은 뒤였고, 5개월 이내의 급반등에 취약했습니다 ([Mutual Fund Observer](https://www.mutualfundobserver.com/?p=4056)). 1880~2016년 67개 시장의 추세추종은 매 10년 플러스였고, 60/40의 10대 낙폭 중 8번에서 좋은 성과를 냈습니다. 그러나 자체 낙폭도 최대 25%였습니다 ([Alpha Architect](https://alphaarchitect.com/time-series-momentum-aka-trend-following-the-historical-evidence/)). 반론도 진지하게 봐야 합니다. Zakamulin은 이동평균 타이밍 성과에 **상당한 데이터 마이닝 편향**이 있다고 지적했고 ([MFO](https://www.mutualfundobserver.com/?p=4056)), Alpha Architect의 표본외 검증에서는 단순 TAA의 1927~1977년 성과가 고정 배분과 다르지 않았습니다 ([Alpha Architect](https://alphaarchitect.com/2014/09/are-uber-simple-asset-allocation-systems-robust/)). 그래서 신호등은 "하락장 전체를 피한다"가 아니라 **"긴 하락장의 깊은 부분을 줄이되 첫 10%는 맞는다"**로 설명해야 합니다.

| 지표 | 역할 | 근거 강도 | 무료 데이터 | 주의점 | 권장 |
|---|---|---|---|---|---|
| S&P 500 vs 10개월(≈200일) 이평 | 주 신호등 | **강**(1세기 자료, 단 편향 지적 있음) | 가격에서 직접 계산(Tiingo 등) | 첫 하락 구간은 못 피함, V자 반등에서 휩쏘, 월말 판정 후 다음 거래일 체결 | 오늘 화면 P1 |
| HY OAS (FRED BAMLH0A0HYM2) | 신용 스트레스 | **중상**: 예측력은 거의 EBP에서 나오고, EBP 50bp 상승 시 12개월 경기침체 확률 약 15%p 상승 ([Fed](https://www.federalreserve.gov/econresdata/notes/feds-notes/2016/recession-risk-and-the-excess-bond-premium-20160408.html)) | FRED, 단 **2026년 4월부터 3년치만**, "internal use only", 재배포는 ICE 승인 필요 ([FRED](https://fred.stlouisfed.org/series/BAMLH0A0HYM2)) | 공개 저장소·앱에 원값 재배포 금지 → 파생 상태만 표시, 자체 비공개 아카이브. 2000·2008·2020 백테스트 불가 | 상태 표시만, 라이선스 확인 필요 |
| NFCI (Chicago Fed) | 금융 여건 종합 | 중 | FRED 주간, **1971년부터**, 금요일 기준 다음 수요일 발표(약 5일 지연) ([FRED](https://fred.stlouisfed.org/series/NFCI)) | 지연 반영 필수(발표일 기준) | HY OAS의 장기 백테스트 대체재, P2 |
| VIX 수준 + VIX/VIX3M | '지금 스트레스' | 중하: 2010년 이후 백워데이션은 20% 미만이고, Cboe는 추가 하락의 신뢰할 경고가 아니라고 봄 ([Cboe](https://www.cboe.com/insights/posts/inside-volatility-trading-is-vix-backwardation-necessarily-a-sign-of-a-future-down-market)) | FRED ID(VIXCLS·VXVCLS)와 라이선스는 **미확인** | 매도 신호보다 '새 위험 줄이기' 용도 | 유지(현 시안) |
| 장단기 금리차 10Y-3M (T10Y3M) | 경기 맥락 | 경기침체 예측용, 타이밍용은 약함 | FRED 일간, 1982년부터 ([FRED](https://fred.stlouisfed.org/series/T10Y3M)) | 2022년 역전 뒤 경기침체가 오지 않음 ([NBC](https://www.nbcnews.com/business/economy/indicator-foretold-almost-every-recession-doesnt-seem-working-anymore-rcna163522)), 선행 기간 1~2년 | 지표 상세의 관련 지표로만 |
| 시장 폭(S&P 구성종목 중 200일선 위 비율) | 확인/괴리 | 실무 관행, 낙폭 감소 연구는 **찾지 못함**. ZBT는 40년간 8회 신호 ([StockCharts](https://articles.stockcharts.com/article/articles-arthurhill-2019-01-perspective---40-years-of-the-zweig-breadth-thrust---weight-of-the-evidence/)) | 공식 무료 API 없음 → 약 500종목 일봉으로 직접 계산 | 30% 이하는 '약함'으로 인용되나 임계값은 관행 | P3 |
| 섹터·방어/경기 비율(XLP/XLY 등) | 트렌드 맥락 | 검증 자료 미확보 | 가격에서 계산 | RRG 방법론은 독점 → 단순 상대강도로 대체 | 트렌드 탭 P2 |
| CNN Fear & Greed | 역발상 심리 | 공개 검증 없음, 공식 API 없음 ([CFI](https://corporatefinanceinstitute.com/resources/capital_markets/fear-and-greed-index/)) | 없음 | 구성요소(VIX·스프레드 등)와 중복 | **넣지 않음** |
| 원달러 | 원화 환산 효과 | — | 공공데이터·FRED | 전략과 S&P를 같은 원화 기준으로 비교해야 공정 | 유지 |

시장 폭·HY 스프레드에 쓰는 "70% 과열 / 5~6% 스트레스" 같은 고정 임계값은 출처 없는 관행입니다. 그래서 화면에서는 **'최근 6~12개월 대비 변화'** 같은 상대 표현을 권합니다. 추세와 신용 확인을 결합하는 설계도 흔하지만, 그 조합을 직접 검증한 연구는 이번 조사에서 확보하지 못했습니다.

## 전략 성적표는 '포착률·낙폭·세후' 세 줄과 과최적화 배지로 충분하다

샤프는 위로 튀는 변동도 벌점으로 칩니다. 그래서 "벌 땐 많이"와 충돌합니다. 목표를 S&P 대비로 가장 직접 보여주는 것은 **하락 포착률 < 100%와 상승 포착률 ≈ 100% 이상의 조합**입니다. 하락 포착률은 벤치마크가 마이너스인 달만 골라 기하평균을 비교합니다. Morningstar 예시의 펀드는 상승 96%, 하락 20%로 "오를 땐 거의 따라가고 내릴 땐 5분의 1만 맞는" 모습이었습니다. 다만 스타일이 지수와 크게 다르면 이 비율은 실력이 아니라 스타일 차이를 반영하므로 단독 판정에 쓰지 말라는 경고가 붙습니다 ([Morningstar](https://global.morningstar.com/en-ca/personal-finance/what-are-upside-and-downside-capture-ratios)). 그 위에 **MDD와 회복 기간**, **세후 원화 CAGR**을 얹으면 비전문가용 세 줄 성적표가 됩니다.

### 추천 지표 세트와 쉬운 한국어

| 지표 | 정의 | 쉬운 한국어 표현 | 위치 | 주의 |
|---|---|---|---|---|
| 하락/상승 포착률 | S&P 하락(상승) 달만의 기하평균 수익 비율 ([Morningstar](https://global.morningstar.com/en-ca/personal-finance/what-are-upside-and-downside-capture-ratios)) | "S&P가 10 빠질 때 평균 4 빠지고, 10 오를 때 9 올랐어요" | 카드 1줄째 | 스타일 차이 반영, 다른 지표와 함께 |
| MDD + 회복 기간 | 고점 대비 최대 하락 ([QC Glossary](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/glossary.md)), 원래 고점 회복까지 걸린 기간 | "1,000만 원이 가장 많이 줄었을 때 720만 원. 다시 1,000만 원까지 14개월" (같은 기간 S&P와 나란히) | 카드 2줄째 | 기간이 길수록 커짐 → 반드시 같은 기간 S&P와 비교. 회복 기간 6개월 초과면 심리 부담 큼 ([알고랩](https://algolab.co.kr/blog/backtest-report-guide)) |
| 세후 CAGR(원화) | 비용·세금 차감 후 연복리 | "세금·수수료 떼고 1년에 평균 X%" | 카드 3줄째 | 계좌 규모에 따라 순위가 바뀜(아래) |
| 칼마 | CAGR/|MDD| ([empyrical](https://quantopian.github.io/empyrical/_modules/empyrical/stats.html)) | "최악 손실 1만큼 견딘 대가로 1년에 몇을 벌었나" | 자세히 | 1~2 양호, 2 이상 우수 ([알고랩](https://algolab.co.kr/blog/backtest-report-guide)) |
| 소르티노 | 하방편차만 벌점 ([QC Glossary](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/glossary.md)) | "나쁜 출렁임 대비 수익" | 자세히 | 목표 수익률 설정에 따라 값이 달라짐 |
| 얼서 지수·마틴 비율 | 고점 대비 하락률의 RMS, 그것으로 나눈 수익 ([Wikipedia](https://en.wikipedia.org/wiki/Ulcer_index)) | "얼마나 깊고 오래 물려 있었나" | 자세히 | 주 단위 이상으로 자주 샘플링 |
| 손익비 | 평균이익/|평균손실| ([QC Glossary](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/glossary.md)) | "이길 땐 평균 +X, 질 땐 평균 −Y" | 스윙 전략 카드 | **승률과 항상 짝지어** 표시. 1.5 이상 양호 ([알고랩](https://algolab.co.kr/blog/backtest-report-guide)) |
| 기대값 | 승률×평균이익 + 패율×평균손실 ([QC Glossary](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/glossary.md)) | "한 번 거래할 때 평균 +0.8%" | 스윙 전략 카드 | 비용 차감 후 값으로 |
| 샤프 | 초과수익/변동성 | "출렁임 1당 수익" | 자세히 | **3 초과면 과최적화 의심** ([Composer](https://help.composer.trade/article/215-7-how-do-backtests-work-in-composer), [알고랩](https://algolab.co.kr/blog/backtest-report-guide)) |
| 회전율·비용 손실 | 연간 매매 비중, 비용으로 깎인 수익 | "1년에 포트폴리오를 X번 갈아탔고, 수수료로 Y% 깎였어요" | 카드 하단 | QC·Composer는 1급 요소로 취급 |
| 시도 횟수 + DSR | 시도 N회로 보정한 샤프의 유의 확률 ([Wikipedia](https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio), [SSRN 2460551](https://papers.ssrn.com/abstract=2460551)) | "변형 37개를 시험해서 고른 1등. 운이 아닐 가능성 97% ✓" | 카드 배지 | 0.95 이상 통과. 실험 레지스트리 없으면 계산 불가. 구현 전 원 논문 수식 확인 |
| PBO / 홀드아웃 | 과최적화 확률(CSCV) ([SSRN 2326253](https://papers.ssrn.com/abstract=2326253)), 손대지 않은 마지막 구간 성과 | "안 본 기간에서도 비슷했나" | 자세히 | 논문은 단일 홀드아웃만으로는 부족하다고 봄 |
| 롤링 12개월 초과수익 | 12개월 창마다 S&P 대비 | "12개월 구간 중 S&P를 이긴 비율 64%" | 자세히 | '운 좋은 한 구간' 착시를 줄임(1차 출처 미확보) |

### 후보 기준을 지표로 번역하기

현재 기준 "손익비 > S&P"는 그대로 계산할 수 없습니다. S&P를 그냥 산 사람에게는 '거래'가 없기 때문입니다. 두 가지 번역을 제안합니다. 월간 기준으로 "이익 난 달 평균 / 손실 난 달 평균"을 둘 다 구해 비교하거나, **상승 포착률/하락 포착률 > 1**로 바꾸는 것입니다. 두 번째가 목표 문장과 더 가깝습니다.

| 현재 기준 | 제안 지표 | 판정 |
|---|---|---|
| 세후 수익 ≥ S&P | 세후 원화 CAGR(같은 계좌 규모 가정) | 전략 ≥ S&P 그냥 보유 |
| 손익비 > S&P | 상승 포착률 / 하락 포착률 (또는 월간 손익비 비교) | > 1 (그리고 하락 포착률 < 100) |
| 최악 손실이 S&P의 절반대 | 같은 기간 MDD 비율 + 회복 기간 | 전략 MDD / S&P MDD ≤ 약 0.6 |
| (신규) 운이 아님 | 시도 횟수 기록 + DSR | DSR ≥ 0.95, 홀드아웃에서 부호 유지 |
| (신규) 비용 현실 | 보수적 비용 가정 포함 | 비용 2배 가정에서도 위 기준 유지 |

### 세금·수수료: 계좌 규모가 순위를 바꾼다

해외주식 양도차익은 해외주식끼리 연간 손익을 통산해 **250만 원 공제 후 22%(지방세 포함)**로 과세됩니다. 미국 배당은 **15% 원천징수**로 끝나고 국내 추가세가 없습니다. 단, 이자+배당이 연 2천만 원을 넘으면 종합과세 대상입니다 ([KB Think, 2025-11 갱신](https://kbthink.com/stock/foreign-tax.html)). 여기서 함의가 하나 나옵니다. S&P를 10년 보유하면 공제를 사실상 한 번만 쓰지만, 매년 이익을 실현하는 전략은 공제를 매년 씁니다. **소액 계좌에서는 회전 전략이 세금상 유리할 수 있고, 금액이 커지면 과세 이연을 잃는 비용이 커집니다.** 따라서 세후 비교는 계좌 규모를 입력으로 받아야 합니다(이 결론은 위 세율에서 도출한 추론입니다).

수수료는 시안의 0.05%가 낙관적일 수 있습니다. 확인된 범위는 다음과 같습니다. 미래에셋 미국주식 온라인 0.25%(2차 블로그 출처, [tilnote](https://tilnote.io/pages/6af8864558258d5dd1a11dbf.md)), 메리츠 0원 이벤트 2026-01 종료 후 0.07%([뉴스토마토](https://newstomato.com/ReadNews.aspx?no=1289451)), 2025년 말 금융위 조치 이후 '0원' 이벤트 감소입니다. 환전은 삼성 기준 우대 없을 때 스프레드 1%, 95% 우대 시 0.05%였습니다(2024 이벤트). 시안의 환전 0.1%는 약 90% 우대에 해당합니다. 권장 기본값은 **편도 0.25%, 환전 1%×(1−우대율)이며 사용자가 수정**할 수 있게 하는 것입니다. 표시는 "세전 → 비용 차감 → 세후" 3단 막대로 합니다.

## 모의투자는 '실력 검증'이 아니라 '실행 검증'이다

샤프를 95% 신뢰로 확인하려면 일간 기록 **약 2~3년**이 필요합니다(샤프 1.15 이상이면 약 2년). 이것도 시도가 1개라는 가정이고, 여러 전략을 시험했다면 더 길어야 합니다 ([Wikipedia: DSR](https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio)). 3개월 모의투자로 전략의 우열을 판정하는 것은 통계적으로 불가능합니다. 월 1회 리밸런싱이면 표본이 3개뿐입니다. 그래서 모의투자의 목적을 바꾸자고 제안합니다. **실력은 실험실의 DSR·홀드아웃으로 판정하고, 모의투자는 '백테스트가 말한 대로 실제로 실행되는가'만 검증**하는 것입니다.

모의투자 화면의 실행 검증 패널은 네 가지를 보여줍니다. (a) **신호 일치율**: 같은 기간 백테스트를 다시 돌렸을 때 나온 주문과 모의 주문이 같은 비율입니다. (b) **추적오차**: 백테스트 재실행과 모의의 일별 수익 차이의 평균·표준편차입니다([QC Glossary](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/glossary.md)의 IR 분모와 같은 개념). (c) **슬리피지(bp)**: 가정 체결가 대비 실제 체결가 차이입니다. (d) **누락·지연 주문 수**입니다. 졸업 기준은 "3개월 또는 리밸런싱·매매 20~30회 중 긴 쪽 + 네 항목 모두 정상"을 권합니다. 이 수치는 출처 없는 실무 휴리스틱이므로 앱 설정값으로 둡니다. 성과 곡선은 버리지 않습니다. 같은 길이 구간들의 백테스트 롤링 수익 5~95% 범위를 띠로 그리고 모의 곡선을 겹쳐서, **띠 안이면 '정상', 밖이면 '점검'**으로 판단하게 합니다. 화면에는 "이 기간으로는 성과 우열을 판정할 수 없음"을 고정 문구로 둡니다. KIS 모의계좌의 체결 방식(실시간 호가 반영 정도)은 확인하지 못했습니다. 따라서 슬리피지 측정이 모의계좌에서 얼마나 의미 있는지도 실전 소액 운용 전까지 미확정입니다.

### 실전 모니터링은 Knight Capital이 없던 네 가지 통제를 갖춰야 한다

2012년 Knight Capital은 고객 주문 212건을 처리하다 **45분 동안 400만 건 넘는 주문**을 내 **4억 6천만 달러 이상**을 잃었습니다. 개장 전 자동 경고 메일 97통은 아무도 조치하지 않았습니다. SEC가 지적한 결여 통제는 네 가지였습니다. 주문 직전 점검(입력 주문과 출력 주문 비교), 자본 한도 초과 주문 차단, 코드 테스트·배포 절차, 사고 대응 문서입니다 ([SEC 2013-222](https://www.sec.gov/news/press-release/2013-222)). 개인 앱의 실제 투자 화면은 이 축소판을 갖춰야 합니다.

| 요소 | 화면 표시 | 동작 |
|---|---|---|
| 킬 스위치 | 상단 고정, 한 번 탭으로 끔, **기본 꺼짐** | 손실 한도·이상치에 걸리면 자동 중단, 다시 켜는 것은 사람만 |
| 한도 게이지 | "오늘 주문 n/m건", "누적 손실 −x% / 한도 −y%" | 1회 금액·일일 건수·비중 상한, 중복 주문 차단, 기준가 대비 괴리 상한 |
| 주문 로그 | 신호 시각·의도 주문·제출·응답·체결가·수수료·**전략 버전** | DB append-only. 공개 저장소·Actions 로그에는 남기지 않음 |
| 슬리피지 리포트 | "평균 z bp / 가정 w bp" | 가정 초과 시 경고 |
| 경고 확인 | 확인(ack) 전까지 빨간 배지 | '무시된 97통'을 막음 |
| 배포 안전 | 실전 코드 버전 = 모의에서 검증된 버전 | 버전이 다르면 켜기 버튼 비활성 |

손실 한도의 구체적 %에 대한 권위 있는 기준은 찾지 못했습니다. 사용자가 정할 값으로 두되, 기본값은 보수적으로 둡니다.

## 쉬운 말은 쓰되 위험 단어는 남긴다

비전문가 표현 원칙은 조사한 사례에서 여섯 가지로 정리됩니다. 첫째, **전문용어를 일상어로 바꾸되 위험 개념은 원래 용어를 남깁니다.** 토스증권은 '매수'를 '구매하기'로 바꿨지만, '미수거래'를 '외상'으로 불렀다가 위험을 가린다는 비판을 받고 되돌렸습니다 ([brunch](https://brunch.co.kr/@uibowl/410)). "실전 주문", "손실", "자동매매 켜짐"은 그대로 씁니다. 둘째, **숫자 옆에 구간 라벨**을 붙입니다(칼마 '양호', 샤프 3 초과 '과최적화 의심'). 셋째, **위험은 금액·행동 문장으로** 씁니다. Wealthfront는 낙폭 수치 대신 위험이 크면 "you might have trouble staying in the market"이라고 설명합니다 ([Wealthfront](https://www.wealthfront.com/blog/ask-wealthfront-risk-score-explainer)). 우리 앱에서는 "1,000만 원이 720만 원까지 줄었던 적이 있어요"가 됩니다. 넷째, **확률은 빈도로** 씁니다. 300명 실험에서 아이콘 배열이 텍스트나 원·삼각형 그래픽보다 위험 중립에 가까운 결정을 이끌었습니다 ([NSF PAR](https://par.nsf.gov/servlets/purl/10237358)). 그래서 "다음 달 오를 확률 62%"보다 "과거 비슷한 상황 24번 중 15번 상승"이 낫습니다. 다섯째, **예측은 중앙선 + 80% 범위 + '보장 아님'**으로 보여주고, 가정(수수료 반영, 세금 미반영, 명목 기준)을 아래에 적습니다 ([Betterment](https://www.betterment.com/legal/goal-projection)). 여섯째, **백테스트에는 '과거 시뮬레이션(실제 체결 아님)' 라벨과 비용·기간·리밸런싱 주기 가정**을 붙입니다. 이는 SEC 가상 성과 규칙의 원칙을 체크리스트로 쓴 것입니다 ([Troutman Pepper](https://www.troutman.com/insights/the-secs-new-marketing-rule-practically-speaking-hypothetical-performance.html)). 토스의 '잡초 뽑기'(기능 없는 단어 삭제)와 '자극적 문구 지양' 원칙([토스피드](https://toss.im/tossfeed/article/uxwriter-interview))은 '오늘 한 줄' 문구에 그대로 적용됩니다. "급락!" 대신 "큰 움직임(1년 중 상위 5%)"으로 씁니다.

색상은 한국 관례(상승 빨강·하락 파랑)를 따를지 정해야 합니다. 이 관례는 업계 상식이지만 1차 출처를 확보하지 못했습니다. 미국 시장 중심 앱이므로 어느 쪽이든 **범례를 항상 표시**하는 것이 안전합니다.

## 확인되지 않은 항목

다음은 이번 조사에서 1차 출처로 확인하지 못해 구현 전 사람이 직접 확인해야 합니다.

| 항목 | 상태 |
|---|---|
| 한국투자증권 2026년 현재 미국주식 기본 수수료율·환전 우대율 | 미확인(공식 페이지 자동 조회 차단). [수수료 안내 페이지](https://securities.koreainvestment.com/main/customer/guide/_static/TF04ae010000.jsp?tab=2)에서 확인 필요 |
| 2025~2026 세법 개정으로 해외주식 공제액·세율 변경 여부 | 22%·250만 원 유지는 2차 출처 기준. 국세청 페이지 접근 실패 |
| 양도차익 환율 기준, 수수료의 필요경비 인정, 국내주식과의 통산 | 미확인 |
| 미국 ETF 자본이득 분배금의 과세 처리 | 미조사 |
| VIX·VIX3M의 FRED ID와 라이선스, Moody's BAA10Y 장기 이력 | 미확인 |
| HY OAS 파생 상태를 공개 앱에 표시해도 되는지 | ICE 라이선스 확인 필요 |
| KIS 모의계좌 체결 방식, API 주문 제한·오류 코드 | 미조사 |
| 국내 플랫폼(젠포트·퀀터스·핀트·파운트)의 모의/실전 배지·리밸런싱 로그 화면 | 미확인 |
| 모의투자 최소 기간, 개인 손실 한도 %의 권위 있는 기준 | 찾지 못함(휴리스틱으로 표시) |
| DSR·MinTRL 정확한 수식 | 원 논문(SSRN 2460551, 2465675)으로 구현 전 확인 |

## 결론

이번 비교가 보여준 핵심은 이것입니다. 시장을 얼마나 잘 보여주느냐보다 **"내 전략이 목표를 지키고 있는가"를 판정하는 장치**가 이 앱의 차별점입니다. 대중 플랫폼은 샤프·CAGR 중심이고, "잃을 땐 조금"을 재는 하락 포착률은 Portfolio Visualizer 정도만 기본으로 보여줍니다. 우리 앱이 상승/하락 포착률, 회복 기간, 세후 원화 비교, DSR을 실험실 카드의 첫 줄에 두면 목표 문장 자체가 화면이 됩니다. 시장 탭은 반대로 덜어내는 쪽입니다. 추세 신호등 하나를 더하고, 검증 안 된 전망 꼬리표와 4차원 필터는 줄입니다.

두 번째 함의는 단계 설계입니다. 통계적으로 3개월은 실력을 보여줄 수 없습니다. 따라서 **실험실 = 실력 판정(DSR·홀드아웃), 모의 = 실행 판정(신호 일치·슬리피지), 실전 = 통제 판정(킬 스위치·한도·로그)**으로 각 단계가 서로 다른 질문에 답하게 나누는 것이 정직하고 실용적입니다. QuantConnect처럼 세 단계를 같은 화면 배치로 두면, 사용자는 단계가 바뀌어도 같은 자리에서 같은 질문의 답을 찾게 됩니다.
