"""수집 대상(공개 시장 데이터). 실제 보유 종목이 아니다."""

US_ETFS = ["SOXX", "EWJ", "MCHI", "EWT", "VGK", "INDA", "EWY", "EWZ", "SPY", "VOO", "IVV", "QQQ", "IWM", "DIA", "TLT", "IEF", "SHY", "GLD", "VNQ", "EFA", "EEM",
           "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLB", "XLRE", "XLC",
           "SSO"]  # SSO: S&P 2배(실험실 2차 L01·L02, 계획 #59)
US_HISTORY = ["VFINX"]  # 긴 과거 확인용(S&P 지수 펀드, 1980~) — 실험실 4차 R4_GL(계획 #73). 화면에는 안 씀
US_NEWS_TICKERS = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"]
FRED_SERIES = ["VIXCLS", "VXVCLS", "T10Y3M", "NFCI", "DEXKOUS", "DGS10", "DGS2", "T10Y2Y", "DFF", "BAMLH0A0HYM2", "CPIAUCSL", "UNRATE",
               # 실험실 외생변수(예측용): 뉴스 기반 지수(20년치), 달러·유가·물가기대·신용·고용·경기
               "USEPUINDXD",   # 경제정책 불확실성 지수(신문 기사 기반, 일별)
               "WLEMUINDXD",   # 주식시장 변동성 추적지수(신문 기사 기반, 일별)
               "DTWEXBGS", "DCOILWTICO", "T5YIE", "DFII10", "BAMLC0A0CM",
               "BAA10Y",       # 회사채(BAA) − 10년 국채: 1986년부터(하이일드 스프레드는 FRED에 최근 3년만 남음)
               "ICSA", "STLFSI4", "SAHMREALTIME", "UMCSENT", "INDPRO",
               "DTB3",               # 미국 3개월 국채(일간) — 4차 환헤지 합성
               "IR3TIB01KRM156N"]    # 한국 3개월 금리(OECD, 월간) — 4차 환헤지 합성·원화 현금
KR_NEWS_QUERIES = ["코스피", "코스닥", "환율", "미국 증시"]
US_NEWS_QUERIES = ["stock market", "Wall Street", "Federal Reserve", "Treasury yields", "earnings"]  # 여러 언론사가 다룬 미국 뉴스(핫한 정도 판단용)
US_STOCK_NAMES = {"AAPL": "애플", "MSFT": "마이크로소프트", "NVDA": "엔비디아", "AMZN": "아마존", "GOOGL": "알파벳",
                  "META": "메타", "TSLA": "테슬라", "JPM": "JP모건", "XOM": "엑슨모빌", "UNH": "유나이티드헬스"}
US_STOCKS = list(US_STOCK_NAMES)

# 화면 이름(공개 시장 데이터 이름표)
SECTORS = {"XLK": "기술", "XLC": "통신", "XLY": "임의소비", "XLF": "금융", "XLI": "산업", "XLV": "헬스케어", "XLP": "필수소비",
           "XLE": "에너지", "XLB": "소재", "XLU": "유틸리티", "XLRE": "부동산", "GLD": "금", "TLT": "장기 국채", "SOXX": "반도체"}
COUNTRIES = {"SPY": "미국", "EWJ": "일본", "MCHI": "중국", "EWT": "대만", "VGK": "유럽", "INDA": "인도", "EWY": "한국", "EWZ": "브라질"}
