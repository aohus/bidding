# 외부기관(비-나라장터) 입찰공고 API

나라장터(조달청) 외에 자체 전자입찰을 운영하는 공공기관 6곳의 OpenAPI 명세.
수집 코드는 `app/services/external_sources/` 이며 저장 테이블은
`external_bid_notices` / `external_bid_results` / `external_sync_log` 다.

아래 "주의사항"은 **2026-10-12 실제 호출로 검증**한 내용이다. 각 기관이 배포한
명세서와 실제 응답이 어긋나는 지점이 많아, 명세보다 실측을 기준으로 적었다.

나라장터 API 는 [naraapi.md](./naraapi.md) 참조.

---

## 공통 사항

### 인증키

| 키 | 용도 | 비고 |
|---|---|---|
| `NARAJANGTER_SERVICE_KEY` | data.go.kr 6개 소스 전부 + 나라장터 | 디코딩 키(88자) |
| `NARAJANGTER_SERVICE_KEY_V2~V4` | 한도 초과 시 순차 폴백 | |
| `LOCAL_NARAJANGTER_SERVICE_KEY` | 최후 폴백 | 외부기관 서비스에는 활용신청 미완 → 403 |
| `ELECTRIC_INST_SERVICE_KEY` | 전력개발포털 전용 | data.go.kr 아님, 파라미터명 `apiKey` |

**반드시 "디코딩" 키를 쓴다.** `%2B`, `%2F`, `%3D` 가 포함된 "인코딩" 키를 그대로
넣으면 httpx 가 재인코딩해서 **HTTP 403** 이 된다. `config.normalize_service_key()`
가 로드 시 방어적으로 되돌리지만, .env 에는 디코딩 키를 넣는 것이 원칙이다.

**403 의 흔한 원인은 키 오류가 아니라 서비스별 활용신청 누락이다.** data.go.kr 은
서비스마다 따로 활용신청해야 하며, 미신청 서비스는 본문 없는 403 을 반환한다.
`DataGoKrXmlClient` 는 403 을 로테이션 트리거로 처리해 다음 키로 넘어간다.

### 응답 봉투

data.go.kr 6개 소스는 모두 **XML** 이다 (`type=json` 을 보내도 무시된다).
전력개발포털만 JSON 이다.

```xml
<response>
  <header><resultCode>00</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header>
  <body><items><item>…</item></items>
        <numOfRows/><pageNo/><totalCount/></body>
</response>
```

게이트웨이 에러는 다른 봉투를 쓴다:

```xml
<OpenAPI_ServiceResponse>
  <cmmMsgHeader><returnReasonCode>22</returnReasonCode><returnAuthMsg>…</returnAuthMsg></cmmMsgHeader>
</OpenAPI_ServiceResponse>
```

주요 resultCode: `00` 정상 / `03` 데이터없음 / `05` 서비스 연결실패(상류 일시 장애)
/ `11` 필수 파라미터 누락 / `22` 호출 한도 초과 / `30~32` 서비스키 문제

**에러를 빈 결과로 삼키면 안 된다.** 동기화 윈도우가 0건으로 완료 마킹되어
해당 구간이 영구 누락된다. `resultCode != 00` 은 전부 예외로 올린다.

---

## 1. 한국토지주택공사 (LH) — `source=lh`

```
https://apis.data.go.kr/B552555/OpenBidInfoList/getOpenBidInfo
```

**요청**: `serviceKey`, `pageNo`, `numOfRows`,
`tndrbidRegDtStart`/`tndrbidRegDtEnd`(입찰공고일자 YYYYMMDD), `bidNum`(공고번호)

### 주의사항

- **응답 인코딩이 EUC-KR** 이다 (다른 소스는 UTF-8). expat 이 EUC-KR 을 모르므로
  바이트를 직접 디코딩한 뒤 XML 선언을 제거하고 파싱해야 한다 (`base.decode_body`).
- **`<body><item>` 구조로 `<items>` 래퍼가 없다.** 다른 소스와 다르다.
- 일시 형식이 `2026/10/08 15:00` (슬래시 구분).
- 필드가 ~170개로 외부 소스 중 가장 풍부하다. **지역제한과 면허/업종까지 제공하는
  유일한 외부 소스**다 — 추후 기존 지역·업종 필터에 연동할 수 있다.

### 주요 응답 필드

| 필드 | 의미 | 매핑 |
|---|---|---|
| `bidNum` / `bidDegree` | 공고번호 / 차수 | PK |
| `bidnmKor` / `bidnmEng` | 공고명(국문/영문) | title |
| `zoneHqCd` | 지역본부명 (코드 아님) | institution |
| `cstrtnJobGbNm` | 공종구분명 (예: 지급자재) | work_div |
| `tndrCtrctMedCd` | 계약방법 (예: 제한경쟁, 수의공고) | cntrct_mthd |
| `bidProgrsStatus` | 진행상태 (입찰진행중/마감/개찰) | status |
| `tndrbidRegDt` | 입찰공고일자 | rgst_dt |
| `tndrdocAcptBgninDtm` / `tndrdocAcptEndDtm` | 입찰서 접수 시작/마감 | bid_close_dt |
| `openDtm` | 개찰일시 | openg_dt |
| `presmtPrc` | 추정가격 | presmpt_prce |
| `designPrc` / `fdmtlAmt` | 설계가격 / 기초금액 | raw |
| `addtTax` / `prcscoreExclusAmt` | 부가세 / 가격점수 제외금액 | raw |
| `bidKind` | 공고종류 (일반공고/수의공고) | raw |
| `sunjungNm` | 심사방법 (최저가심사/이행능력심사) | raw |
| `gongdongNm` | 공동수급 가능 여부 | raw |
| `zoneRstrct1~4` | **지역제한** | raw |
| `vndrrstrctNm1~4` | 업체제한 | raw |
| `req{1~10}BsncatGrpNm` | **업종그룹명** | raw |
| `req{1~10}Reqlic{1~10}Nm` | **요구면허명** | raw |
| `req{1~10}LicGbNm` / `LicctNm` / `MvgbNm` | 면허구분/면허수/이동구분 | raw |
| `antbsncatRstrctFg` | 업종제한 플래그 | raw |
| `cooperdocAcptEndDtm` | 협력문서 접수마감 | raw |

---

## 2. 한국수자원공사 — `source=kwater`

```
https://apis.data.go.kr/B500001/ebid/tndr3/cntrwkList   # 공사
https://apis.data.go.kr/B500001/ebid/tndr3/servcList    # 용역
https://apis.data.go.kr/B500001/ebid/tndr3/rstList      # 결과
```

**요청**: `serviceKey`, `pageNo`, `numOfRows`, `_type`(xml|json),
`searchDt`(**검색년월 YYYYMM**), `cntrctDivCd`(1:공사 2:용역 3:내자 4:물품)

### 주의사항 (중요)

- **`searchDt` 가 월 단위다.** 날짜 범위 조회가 없다 → 하루짜리 윈도우로도 그 달
  전체가 조회된다. 때문에 이 소스만 `granularity = "month"` 로 월별 윈도우를 쓴다.
- **`cntrctDivCd` 의 동작이 엔드포인트마다 다르다** (실측 매트릭스):

  | 엔드포인트 | `cntrctDivCd` |
  |---|---|
  | `cntrwkList` | **무시됨** — 어떤 값을 줘도 항상 공사만 반환 |
  | `servcList` | **무시됨** — 항상 용역만 반환 |
  | `rstList` | **필수** — 생략하면 `resultCode 00` 에 `totalCount 0` |

  `rstList` 는 **1~4 를 모두 순회**해야 결과가 누락되지 않는다. 생략 시 에러가 아니라
  조용히 빈 결과가 오므로 가장 위험한 함정이다.
- 값 없는 날짜는 `-` 로 온다 (`tndrPblancEnddt`).
- `tndrPlnprc` 가 `0` 인 경우가 있다 (참가신청 단계 = 예정가격 미공개).
- `scsbidAmt` 는 `37,086,150` 처럼 쉼표가 들어온다.

### 응답 필드

**공고** (`cntrwkList` / `servcList`)

| 필드 | 의미 | 매핑 |
|---|---|---|
| `tndrPbanno` | 입찰공고번호 | PK |
| `tndrPblancNm` | 공고명 | title |
| `cntrctDeptNm` | 계약부서명 | institution |
| `cntrctDivNm` | 계약구분명 (공사/용역) | work_div |
| `ctrmthdCdNm` | 계약방법명 (소액전자/일반경쟁/제한경쟁) | cntrct_mthd |
| `tndrPblancDe` | 공고일자 | rgst_dt |
| `tndrPblancEnddt` | 공고마감일자 | bid_close_dt |
| `tndrPlnprc` | 예정가격 | presmpt_prce |
| `tndrStat` | 입찰상태 (참가신청/가격입찰/입찰완료) | status |
| `intnChargerNm` | 담당자명 | raw |
| `tndrPartcptEntrpsCo` / `tndrPrqudoCo` | 참가업체수 / 적격업체수 | raw |

**결과** (`rstList`)

| 필드 | 의미 | 매핑 |
|---|---|---|
| `tndrPbanno` | 입찰공고번호 | PK |
| `tndrPblancNm` | 공고명 | title |
| `entrpsNm` | 낙찰업체명 | bidder_nm |
| `scsbidAmt` | 낙찰금액 (쉼표 포함) | bidder_amt |
| `cntrctPrgstsNm` | 진행상태명 (낙찰/낙찰예정) | status_nm |
| `cardPrcsDt` | 처리일자 | openg_dt |
| `cntrctDivNm` / `ctrmthdNm` / `sucbidrDcsnMthNm` | 계약구분/계약방법/낙찰자결정방법 | raw |
| `dept` / `intnChargerNm` | 부서 / 담당자 | raw |
| `tndrPblancDe` | 공고일자 | raw |

---

## 3. 한국지역난방공사 — `source=kdhc`

```
https://apis.data.go.kr/B550373/kdhcbidding2/bidding2
```

명세서: 오픈API 인터페이스 정의서 KDHC 입찰정보 v1.3 (2026-06-09, 도메인 포트 변경)

**요청**: `serviceKey`, `pageNo`, `numOfRows`,
`startDate`/`endDate`(조회 시작/종료일 YYYYMMDD)

### 주의사항

- **응답이 느리다.** 30초 타임아웃으로는 상시 실패하므로 이 소스만 60초를 쓴다.
  타임아웃은 윈도우 미마킹으로 이어져 매 사이클 실패만 반복한다.
- `resultCode 05`(서비스 연결실패)가 간헐적으로 발생한다 — data.go.kr 게이트웨이가
  KDHC 백엔드에 닿지 못한 상류 장애다. 재시도하면 정상이므로 윈도우를 마킹하지
  않고 다음 사이클에 재시도하는 현재 동작이 맞다.
- 입찰마감일시를 제공하지 않는다 (`bidDt` 는 개찰일).
- 데이터 갱신주기 일 1회.

### 응답 필드

| 필드 | 의미 | 매핑 |
|---|---|---|
| `bidAnnoNo` | 입찰공고번호 (예: `305100-26070`) | PK |
| `bidChasu` | 변경차수 | PK |
| `caseNm` | 건명 | title |
| `gdeptNm` | 담당부서 | institution |
| `bidGbn` | 구분 (공사/용역/구매) | work_div |
| `regiDt` | 등록일 | rgst_dt |
| `bidDt` | 개찰일 | openg_dt |
| `status` | 상태 (진행중/낙찰/취소) | status |
| `rnum` | 순번 | raw |

---

## 4. 한국마사회 — `source=kra`

```
https://apis.data.go.kr/B551015/API182/E-noticeInfo        # 공고정보
https://apis.data.go.kr/B551015/API183_1/E-successInfo_1   # 낙찰정보
```

명세서: API182 전자입찰 공고정보 / API183 전자입찰 낙찰정보 (2019-07-05)

**요청 (공고)**: `ServiceKey`, `numOfRows`, `pageNo`,
`notice_date`(YYYYMMDD) / `notice_month`(YYYYMM) / `notice_year`(YYYY)
**요청 (낙찰)**: `open_date`(YYYYMMDD) / `open_month` / `open_year`

### 주의사항

- **날짜 필터가 범위가 아니라 단건이다.** 윈도우를 하루씩 순회해야 한다.
- **명세의 응답 필드명 `bCode` 는 틀렸다. 실제 응답은 `BCode`** (대문자 B).
- 낙찰정보 엔드포인트는 명세의 `API183/E-successInfo` 가 아니라
  **`API183_1/E-successInfo_1`** 이다.
- 공고정보는 업무구분/계약방법/상태를 **코드**로 주고, 낙찰정보는 같은 값을
  **명칭 문자열**(`workNm`, `contMethodNm`, `statusNm`)로 준다.
- 낙찰정보에 **낙찰업체명과 낙찰금액이 없다** — 결과구분명만 제공한다.
- 낙찰정보의 데이터기준일자 필드명이 `snedDate` 다 (sned, 오타가 명세에도 있음).

### 코드표

| 필드 | 코드 |
|---|---|
| `workType` 업무구분 | `01` 시설공사 · `02` 기술용역 · `03` 일반용역 · `05` 매각 |
| `contMethod` 계약체결방법 | `1` 일반경쟁 · `2` 지명경쟁 · `3` 제한경쟁 · `4` 수의계약 |
| `status` 공고상태 | `00` 작성중 · `10` 품의중 · `18` 품의반송 · `19` 품의완료 · `20` 공고중 · `30` 심사중 · `97` 완료(재입찰) · `98` 완료(유찰) · `99` 완료(낙찰) |

미등록 코드는 원본 코드를 그대로 보존한다 (조용히 None 으로 떨구면 신규 코드
데이터가 사라진다).

### 응답 필드

**공고 (API182)**

| 필드 | 의미 | 매핑 |
|---|---|---|
| `BCode` | 공고번호 | PK |
| `bidName` | 입찰공고명 | title |
| `noticeAuth` / `demandAuth` | 공고기관명 / 수요기관명 | institution / raw |
| `workType` | 업무구분 (코드) | work_div |
| `contMethod` | 계약체결방법 (코드) | cntrct_mthd |
| `status` | 공고상태 (코드) | status |
| `noticeDate` + `noticeTime` | 공고일자 + 시각 | rgst_dt |
| `bidEndDate` + `bidEndTime` | 입찰마감일자 + 시각 | bid_close_dt |
| `openDate` + `openTime` | 입찰개시일자 + 시각 | openg_dt |
| `registEndDate` + `registEndTime` | 참가자격등록 마감 | raw |
| `openPlace` | 개찰장소 | raw |
| `contGubun` | 계약체결형태명 | raw |
| `renotifyCnt` | G2B 전송여부 (0 미전송 / 1 전송) | raw |
| `sendDate` | 데이터 기준일자 (ISO8601) | raw |

**낙찰 (API183_1)**

| 필드 | 의미 | 매핑 |
|---|---|---|
| `BCode` | 입찰공고번호 | PK |
| `bidName` | 입찰공고명 | title |
| `statusNm` | 입찰결과구분명 (완료(낙찰)) | status_nm |
| `openDate` + `openTime` | 입찰개시일자 + 시각 | openg_dt |
| `workNm` | 업무구분명 (문자열) | raw |
| `contMethodNm` / `contGubun` | 계약체결방법 / 형태 | raw |
| `noticeAuth` / `demandAuth` | 공고기관 / 수요기관 | raw |
| `snedDate` | 데이터기준일자 | raw |

---

## 5. 한국가스공사 — `source=kogas`

```
https://apis.data.go.kr/B551210/bidInfoList2/getBidInfoList2
```

**요청**: `serviceKey`, `numOfRows`, `pageNo`,
`DOCDATE_START`/`DOCDATE_END`(공고일자 YYYYMMDD), `NOTICE_NAME`(입찰건명),
`NOTICE_CODE`(입찰번호)

### 주의사항

- **응답 필드명이 전부 대문자+언더스코어**다.
- **공고와 낙찰결과가 같은 행에 온다** (`SUCCESS_*`). 낙찰업체가 있는 행만
  `external_bid_results` 에도 적재한다.
- **추정가격/예산 필드가 없다.** 금액 정보를 제공하지 않는다.
- 진행상태 필드가 없다 — `CANCEL_YN`/`SUCCESS_CORP_NAME` 으로 도출한다
  (취소 / 낙찰 / 미정).
- 값 없는 필드는 `<TAG/>` 빈 엘리먼트로 온다.
- 일시 형식이 `2026-10-16 10:00` (분까지).

### 응답 필드

| 필드 | 의미 | 매핑 |
|---|---|---|
| `NOTICE_CODE` | 입찰번호 | PK |
| `NOTICE_NAME` | 입찰건명 | title |
| `WORK_TYPE_NAME` | 업무구분명 (공사/용역) | work_div |
| `CONT_METHOD_NAME` | 계약방법명 | cntrct_mthd |
| `NOTICE_DT` | 공고일자 | rgst_dt |
| `END_DT` | 입찰마감일시 | bid_close_dt |
| `OPEN_DT` | 개찰일시 | openg_dt |
| `CANCEL_YN` | 취소여부 | status 도출 |
| `SUCCESS_CORP_NAME` / `SUCCESS_CORP_CODE` | 낙찰업체명 / 코드 | bidder_nm |
| `SUCCESS_AMT` | 낙찰금액 | bidder_amt |
| `SUCCESS_RATE` / `SUCCESS_DT` | 낙찰률 / 낙찰일 | raw / openg_dt |
| `BID_TYPE_NAME` | 입찰방식명 (전자입찰) | raw |

---

## 6. 전력개발포털 — `source=kepco`

```
https://bigdata.kepco.co.kr/openapi/v1/electContract.do
```

한전 및 발전 계열사의 전자입찰 계약정보를 한 엔드포인트로 제공한다.
**한국서부발전(COM02)과 한국중부발전(COM05)이 여기 포함되므로 각 사의 개별 API
대신 이 소스로 통합한다** (서부발전 전용 API `www.iwest.co.kr:8082` 는
2026-10-12 기준 HTTP 404 로 폐기됨).

**요청**: `apiKey`(**필수**, 40자, `ELECTRIC_INST_SERVICE_KEY`),
`noticeBeginDate`/`noticeEndDate`(**필수**, YYYYMMDD, **최대 90일**),
`returnType`(json|xml, 미지정 시 json), `companyId`, `no`(공고번호),
`name`(입찰건명), `bidAttendReqCloseDatetime`, `progressState`

### 주의사항

- data.go.kr 이 **아니다**. 파라미터명이 `serviceKey` 가 아니라 `apiKey` 이고
  전용 키를 쓴다. 키 로테이션 풀에 들어가지 않는다.
- **JSON 응답이고 resultCode 봉투가 없다** — 최상위에 `{"data": [...]}` 뿐이다.
  `data` 키가 없으면 에러로 간주해야 한다 (빈 결과로 삼키면 영구 누락).
- **페이지네이션이 없다.** 윈도우 폭이 응답 크기를 직접 결정한다
  (실측: 12일 전 계열사 = 399건 / 2.3MB). 90일 상한을 넘기면 즉시 실패시킨다.
- **`companyId` 를 생략하면 전 계열사를 한 번에 반환한다** (실측: COM01/02/04/05/
  06/08/09/10/11/12). 14회 호출을 1회로 줄일 수 있다.
- **`presumedPrice`(추정가격)와 `presumedAmount`(추정금액)가 배타적으로 채워진다.**
  자재구매(Product) 행은 `presumedPrice` 만, 공사용역(ConstructionService) 행은
  `presumedAmount` 만 있다. 폴백하지 않으면 공사용역 공고 금액이 전부 유실된다.
  (엄밀히는 추정금액 = 추정가격 + 부가세 등으로 다른 값이다.)
- **`itemType` 에 명세에 없는 `Product` 가 온다** (실측 76건 중 32건). 명세는
  Construction/Service 2종만 적혀 있다. 누락하면 영문이 그대로 저장된다.
- 명세의 응답 필드 `bidNullification` 은 실제로 **`bidNullIfication`** (대문자 I).
- 개찰일시 필드가 없다 (개찰방법 `openMethod` 만 제공).

### 코드표

| 필드 | 코드 |
|---|---|
| `companyId` 회사구분 | `COM01` 한국전력공사 · `COM02` 한국서부발전 · `COM03` 한국전력국제원자력대학원대학교 · `COM04` 한국남부발전 · `COM05` 한국중부발전 · `COM06` 한국남동발전 · `COM08` 한국동서발전 · `COM09` 한국전력기술 · `COM10` 한전KPS · `COM11` 한국전력거래소 · `COM12` 한국원자력연료 · `COM14` 한국발전교육원 · `COM16` 한국해상풍력 · `COM19` KAPES |
| `purchaseType` 구분 | `Product` 자재구매 · `ConstructionService` 공사용역 |
| `itemType` 도급구분 | `Construction` 공사 · `Service` 용역 · `Product` 자재구매(명세 외, 실측) |
| `competitionType` 계약방법 | `Open` 일반경쟁 · `Destination` 지명경쟁 · `Limited` 제한경쟁 · `Private` 수의 |
| `bidType` 낙찰방법 | `LimitedLowestPrice` 제한적최저가 · `LowestPrice` 최저가 · `QualifiedEval` 적격심사 · `CollectivelyBid` 일괄입찰 · `Nego` 협상 · `TotalEvalSuccess` 종합심사낙찰제 |
| `progressState` 공고상태 | `PreAttendProgress` 공고진행 · `AttendProgress` 입찰진행 · `Close` 마감 · `Fail` 유찰 · `OpenTimed` 개찰 · `Final` 공고종료 |
| `emergencyNoticeYn` 공고구분 | `1` 긴급 · `2` 보통 |
| `fieldIntroYn` 현장설명여부 | `1` 있음 · `0` 없음 |
| `jointSupplyDemandYn` 공동수급여부 | `1` 가능 · `0` 불가 |

### 응답 필드

| 필드 | 의미 | 매핑 |
|---|---|---|
| `no` | 공고번호 | PK |
| `name` | 입찰건명 | title |
| `placeName` | 발주기관 | institution (없으면 companyId 로 보완) |
| `itemType` / `purchaseType` | 도급구분 / 구분 | work_div |
| `competitionType` | 계약방법 | cntrct_mthd |
| `progressState` | 공고상태 | status |
| `noticeDate` | 공고일시 | rgst_dt |
| `endDatetime` | 입찰종료일시 | bid_close_dt |
| `presumedPrice` / `presumedAmount` | 추정가격 / 추정금액 | presmpt_prce |
| `companyId` | 회사구분 | raw |
| `beginDatetime` | 투찰시작일시 | raw |
| `createDatetime` | 등록년월시분초 | raw |
| `bidAttendReqBeginDatetime` / `bidAttendReqCloseDatetime` | 입찰신청 시작/마감일시 | raw |
| `estimatedPriceBasicAmount` | 예비가격기초금액 | raw |
| `approximateAmount` / `subcontractBudgetAmount` | 사정금액 / 도급금액 | raw |
| `bidType` / `bidTypeDetail` | 낙찰방법 / 낙찰자결정방법설명 | raw |
| `vendorAwardType` | 입찰방법 | raw |
| `etc` / `bidAttendRestrict` | 입찰참가자격 / 참가자격 | raw |
| `bidAttendDocument` | 입찰참가 신청서류 | raw |
| `bidBondBelong` | 입찰 보증금귀속 | raw |
| `bidNullIfication` | 입찰무효사항 (명세 오타 주의) | raw |
| `contractBeginEndDate` | 계약착수일 | raw |
| `deliveryLocation` / `deliveryDueDate` | 납품장소 / 납기일 | raw |
| `mailBidDistribution` | 계약조건 공시장소 | raw |
| `moreInformation` | 추가정보제공처 | raw |
| `contractReqDepartmentName` | 계약의뢰부서 | raw |
| `creatorName` | 계약담당자 | raw |
| `emergencyNoticeYn` | 공고구분 (긴급/보통) | raw |
| `fieldIntroYn` / `fieldIntroBeginDatetime` | 현장설명 여부 / 날짜 | raw |
| `pqEvalYn` | PQ 심사구분 | raw |
| `jointSupplyDemandYn` / `jointSupplyDemandVendorCnt` | 공동수급 여부 / 업체수 | raw |
| `openMethod` | 개찰방법 | raw |
| `bidLocation` | 방문입찰장소 | raw |
| `filenlink1~5` / `filename1~5` | 첨부파일 링크 / 파일명 | raw |

---

## 수집하지 않는 소스

| 기관 | 이유 |
|---|---|
| 한국서부발전 자체 API | `http://www.iwest.co.kr:8082/openapi-data/service/Bid/BidList` 가 HTTP 404 (2022년 기술문서의 URL, 폐기됨). `kepco` 의 `COM02` 로 대체. |
| 한국중부발전 자체 API | `https://apis.data.go.kr/B552521/cbid/getData` — 필수 파라미터 명세 미확보 (`resultCode 11`). `kepco` 의 `COM05` 로 대체. |

---

## 동기화 윈도우

소스별 조회 해상도가 달라 `granularity` 로 구분한다
(`app/services/external_sources/registry.py`).

| granularity | 소스 | 윈도우 |
|---|---|---|
| `day` | lh, kdhc, kra, kogas, kepco | `YYYYMMDD0000` ~ `YYYYMMDD2359` |
| `month` | kwater | `YYYYMM010000` ~ `YYYYMM<말일>2359` |

최근 N일(또는 당월)은 항상 재수집하고, 그 이전은 `external_sync_log` 에 기록이
없는 윈도우만 백필한다. **수집이 실패한 윈도우는 마킹하지 않는다.**

윈도우당 API 호출 수 (실측):

| 소스 | 호출 수 |
|---|---|
| lh / kdhc / kogas / kepco | 1 (+ 페이지당 1) |
| kra | 2 × 일수 (공고 + 낙찰) |
| kwater | 6 × 월수 (공사 1 + 용역 1 + 결과 4) |
