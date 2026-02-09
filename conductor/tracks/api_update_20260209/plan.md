# Implementation Plan - API Update & Bid Calc Refactor

## Phase 1: Backend Implementation
- [x] Task: `BidAValueItem` Pydantic 모델 업데이트 5f4bc14
    - [x] 새로운 API 매핑 테이블에 맞춰 스키마 정의 (`bssamt` 필수 포함)
- [x] Task: `narajangter.py` 서비스 로직 수정 0c950da
    - [x] `AVALUE_URL` 상수 제거 및 공사/용역 URL 상수 정의
    - [x] 입찰 공고 유형에 따라 적절한 URL을 호출하도록 로직 분기 처리
    - [x] API 응답 파싱 및 에러 핸들링
- [ ] Task: API 응답 테스트 확인
    - [ ] 실제 나라장터 API 호출 테스트 및 데이터 검증
- [ ] Task: Conductor - User Manual Verification 'Backend Implementation' (Protocol in workflow.md)

## Phase 2: Frontend Implementation
- [ ] Task: 타입 정의 업데이트
    - [ ] 백엔드 변경 사항에 맞춰 `types/bid.ts` 내 인터페이스 수정
- [ ] Task: 입찰가 계산 로직 수정 (`bidCalculations.ts`)
    - [ ] `budgetPrice` 의존성 제거 및 `bssamt` 기반 계산 로직 구현
- [ ] Task: `BidCalculator.tsx` UI 업데이트
    - [ ] 계산 입력 필드 및 결과 표시 UI 수정
    - [ ] 추가된 세부 정보(보험료 등) 표시 영역 추가
- [ ] Task: Conductor - User Manual Verification 'Frontend Implementation' (Protocol in workflow.md)

## Phase 3: Integration & QA
- [ ] Task: 통합 테스트
    - [ ] 공고 검색 -> 상세 조회 -> 입찰가 계산 전체 흐름 테스트
- [ ] Task: Conductor - User Manual Verification 'Integration & QA' (Protocol in workflow.md)
