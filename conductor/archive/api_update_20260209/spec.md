# Specification: 나라장터 API URL 변경 및 입찰가 계산 로직 수정

## 1. Overview
기존 `AVALUE_URL`을 공사 및 용역 유형에 따라 분리된 새로운 API Endpoint로 변경합니다. 이를 통해 `bssamt`(기초금액) 및 기타 세부 정보를 확보하고, 프론트엔드의 입찰가 계산 로직을 `budgetPrice`가 아닌 `bssamt` 기준으로 수정합니다.

## 2. Backend Requirements
### 2.1 API Endpoint Update
- `app/services/narajangter.py` 내 `AVALUE_URL` 제거 및 아래 두 가지 URL로 대체
    - **공사:** `http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkBsisAmount`
    - **용역:** `http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcBsisAmount`

### 2.2 Data Model Update (`BidAValueItem`)
- 새로운 API 응답 스키마에 맞춰 `BidAValueItem` 모델 수정
- **필수 추가 필드:** `bssamt` (기초금액)
- **추가 매핑 필드:**
    - `envCnsrvcst` (환경보전비), `mrfnHealthInsrprm` (국민건강보험료), `odsnLngtrmrcprInsrprm` (노인장기요양보험료)
    - `sftyMngcst` (산업안전보건관리비), `lbrcstBssRate` (노무비기준율)
    - `evlBssAmt` (평가기준금액), `resultCode` (결과코드) 등 제공된 매핑 테이블 참조

## 3. Frontend Requirements
### 3.1 Bid Calculation Logic
- `BidCalculator.tsx` 및 `bidCalculations.ts` 수정
- 기존 `budgetPrice`(예정가격) 대신 백엔드에서 받은 `bssamt`(기초금액)을 사용하여 예상 금액을 계산하도록 변경

### 3.2 UI/UX Update
- `BidCalculator` 컴포넌트 UI 수정
- 새로 추가된 `BidAValueItem`의 정보 중 유의미한 데이터(예: 각종 보험료, 안전관리비 등)를 사용자에게 표시

## 4. Acceptance Criteria
- [ ] 백엔드가 공사/용역 구분에 따라 올바른 기초금액 상세 API를 호출해야 한다.
- [ ] `BidAValueItem`에 `bssamt`가 포함되어야 하며, 데이터베이스 또는 응답 모델에 정상적으로 반영되어야 한다.
- [ ] 프론트엔드 계산기가 `bssamt`를 기준으로 올바른 최적 입찰가를 산출해야 한다.
- [ ] 새로운 API 필드들이 UI에 적절히 표시되어야 한다.
