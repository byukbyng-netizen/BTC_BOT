# BTC Bot Dashboard

국내 업비트 현물 `USDT-BTC` 봇을 모니터링하고 안전한 파라미터를 설정하기 위한 로컬 대시보드입니다.

## 실행

```bash
cd /Users/johan/Project/BTC-BOT
python3 server.py
```

브라우저에서 http://127.0.0.1:8765 를 엽니다.

실시간 공개 시세는 API 키 없이 동작합니다. 잔고·주문·사전점검에는 다음 환경변수가 필요합니다.

```bash
export UPBIT_ACCESS_KEY='발급받은_액세스키'
export UPBIT_SECRET_KEY='발급받은_시크릿키'
```

Secret은 코드·웹페이지·Git에 넣지 마세요. 출금 권한은 부여하지 않아야 합니다.

## 제공 기능

- REST 현재가 연동 (`USDT-BTC`)
- 선택적 WebSocket 실시간 ticker (`websocket-client` 설치 시)
- 마켓 목록·거래 가능 여부 검증
- 잔고 조회 API (`GET /api/account`)
- 미체결 주문 조회 API (`GET /api/orders`)
- 비거래 사전점검 (`GET /api/preflight`)
- 15분봉 캔들 SQLite 저장 (`data/market.sqlite3`)
- EMA/ATR 신호와 페이퍼 주문 엔진
- 페이퍼 사이클 실행 (`POST /api/paper/cycle`)
- 페이퍼 자산·손익·포지션 대시보드 표시
- 15분 자동 페이퍼 사이클 (`PAPER_INTERVAL_SECONDS`, 기본 900초)
- 계산 근거(EMA/ATR/손절·익절가) 표시
- 이벤트 로그 SQLite 영속화 및 스크롤
- 선택적 Webhook 알림 (`BTC_BOT_ALERT_WEBHOOK_URL`)
- 과거 캔들 백테스트 모듈
- 성과 리포트 API (`GET /api/performance`, `GET /api/report`) — 총수익률·실현/미실현 손익·승률·거래 횟수·최대낙폭·수수료
- 거래 내역 API (`GET /api/trades`)
- 페이퍼 포트폴리오 전용 가상 현금·코인·평가액·진입/현재/손절/익절 패널 (업비트 잔고와 분리)
- 거래 timestamp·거래금액·수수료·개별/누적손익·EMA/ATR SQLite 영속 저장
- Equity curve/drawdown 차트 및 `GET /api/equity`
- 전체/1일/7일/30일 및 시작일·종료일 성과 필터
- EMA/ATR 캔들, 매수·매도 마커, hover 정보, 연결 상태·마지막 성공 시각·오류 표시
- 모바일 반응형 레이아웃, 키보드 focus, 표 caption, canvas fallback
- 설정 저장과 범위 검증
- 페이퍼 시작 / 일시정지 / 정지
- 실거래 시작 시 별도 확인값 요구

## API 계약

- `GET /api/status`: 실시간 상태와 설정
- `GET /api/config`: 설정 조회
- `POST /api/config`: 설정 JSON 저장
- `POST /api/control`: `{ "action": "start|pause|stop" }`
- `GET /api/account`: 인증 잔고 조회
- `GET /api/orders`: `USDT-BTC` 미체결 주문 조회
- `GET /api/preflight`: 마켓·인증·주문 가능 정보 점검
- `POST /api/paper/cycle`: 15분봉 수집→EMA/ATR 평가→가상 체결
- `GET /api/events`: 영속 이벤트 로그
- `GET /api/performance?start=&end=`: 페이퍼 기간 성과 리포트
- `GET /api/report?start=&end=`: `/api/performance` 별칭
- `GET /api/trades`: 최근 페이퍼 체결 내역
- `GET /api/equity`: 페이퍼 equity/drawdown 시계열
- `POST /api/backtest`: 수집한 15분봉으로 전략/페이퍼 엔진을 재생하고 동일한 성과 지표 반환

## 실거래 안전 게이트

설정에서 `paper_trading=false`로 바꿔도 바로 실거래가 시작되지 않습니다. 다음 확인값을 서버 환경에 별도로 지정해야 합니다.

```bash
export BTC_BOT_LIVE_CONFIRM='I_UNDERSTAND_LIVE_TRADING'
# 선택적 Slack/Discord 호환 webhook
export BTC_BOT_ALERT_WEBHOOK_URL='https://...'
```

이 값은 웹페이지 입력값으로 받지 않으며, 현재 구현은 주문 생성 자동화를 활성화하지 않습니다. 먼저 사전점검·소액 검증·주문 상태 재조회 단계를 통과해야 합니다.

## WebSocket

```bash
python3 -m pip install websocket-client certifi
```

`upbit_ws.py`는 `wss://api.upbit.com/websocket/v1`에 ticker 구독을 연결하는 선택적 어댑터입니다. 실시간 데이터 장애 시 REST 폴링을 기준 상태로 사용해야 합니다.
