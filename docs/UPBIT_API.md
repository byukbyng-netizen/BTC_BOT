# 국내 업비트 연동 기준

## 확인된 거래소/마켓

- 서비스: 국내 업비트 Open API
- 거래 유형: 현물
- 사용자가 표현한 페어: BTC/USDT
- 업비트 API 마켓 코드: **USDT-BTC**를 우선 사용
- `BTC-USDT`도 별도 마켓으로 존재하므로 코드에서 임의 변환하지 않고 `/v1/market/all` 응답과 주문 가능 정보로 검증한다.

2026-10-03 기준 공개 마켓 조회에서 `USDT-BTC`, `BTC-USDT`, `KRW-BTC`가 모두 확인되었다. `USDT-BTC`의 최근 가격은 BTC 1개당 USDT 단위로 표시되어 BTC/USDT 용도에 부합한다.

## API Key에 부여할 최소 권한

| 기능 | 권한 | 필요 여부 |
|---|---|---:|
| 시세·마켓·캔들·호가 조회 | 없음 (Public API) | 필수 |
| 잔고 조회 | 자산조회 | 필수 |
| 미체결·주문·체결 내역 조회 | 주문조회 | 필수 |
| 주문 생성 | 주문하기 | 소액 실거래 전환 시 필수 |
| 주문 취소 | 주문하기 | 필수 |
| 입금 조회/실행 | 입금조회/입금하기 | 사용하지 않음 |
| 출금 조회/실행 | 출금조회/출금하기 | **부여하지 않음** |

권장 발급 상태:

- 자산조회: 허용
- 주문조회: 허용
- 주문하기: 초기에는 미허용, 페이퍼 검증 후 허용
- 입금조회/입금하기: 미허용
- 출금조회/출금하기: 미허용
- 가능하면 허용 IP 제한 사용

## 사용할 API 범위

### Public API

- `GET /v1/market/all` — 마켓 코드와 거래 가능 여부 확인
- `GET /v1/ticker` — 현재가
- `GET /v1/candles/minutes/{unit}` — 캔들
- `GET /v1/orderbook` — 호가
- WebSocket — 실시간 ticker, orderbook, trade, candle

### Private API

- `GET /v1/accounts` — 잔고
- `GET /v1/orders/chance?market=USDT-BTC` — 주문 가능 정보·최소 금액·수수료·잔고
- `GET /v1/orders` — 주문 목록
- `GET /v1/order?uuid=...` — 주문 상태·체결
- `POST /v1/orders` — 주문 생성
- `DELETE /v1/order?uuid=...` — 주문 취소

주문 생성 전 반드시 `/v1/orders/chance`를 조회해 호가 단위와 최소 주문 금액을 확인한다. 주문 생성 응답만 믿지 말고 UUID로 주문 상태를 재조회한다.

## 보안 규칙

- API Key/Secret은 채팅, 코드, 프론트엔드, Git에 저장하지 않는다.
- 대시보드 브라우저에는 Secret을 전달하지 않는다.
- 서버 환경변수 또는 OS 시크릿 저장소에서만 읽는다.
- 출금 권한은 사용하지 않는다.
- 대시보드는 기본 `127.0.0.1` 바인딩으로 시작한다.
- 실거래 주문은 페이퍼 모드와 소액 검증 후 별도 활성화한다.

## 공식 근거

- https://docs.upbit.com/kr/docs/api-setup
- https://docs.upbit.com/kr/reference/available-order-information
- https://docs.upbit.com/kr/reference/new-order
