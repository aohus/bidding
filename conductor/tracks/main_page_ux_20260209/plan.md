# Implementation Plan - 메인 페이지 UX/UI 개선

## Phase 1: 상태 관리 및 데이터 캐싱 [checkpoint: ece4d3a]
- [x] Task: `LocalStorage` 기반 상태 관리 구현 87b2a10
    - [x] 검색 조건 및 결과를 저장할 커스텀 훅 또는 상태 저장 로직 작성
    - [x] 페이지 로드 시 캐시된 데이터 복원 기능 구현
- [x] Task: 초기 진입 시 자동 검색 로직 구현 8e281be
    - [x] 기본값(개찰일시, 오늘 날짜) 설정 및 첫 렌더링 시 API 호출 트리거
- [x] Task: Conductor - User Manual Verification 'Phase 1: 상태 관리 및 캐싱' (Protocol in workflow.md)

## Phase 2: 검색 필터 UI 컴포넌트 고도화
- [x] Task: `DateRangePicker` 통합 322c5bd
    - [x] 시작일/종료일 개별 입력을 하나의 기간 선택 컴포넌트로 교체 (`shadcn/ui` 활용)
- [x] Task: `TagInput` UI 컴포넌트 구현 e3e026c
    - [x] 참가제한지역명 및 업종명 필드에 태그 입력 방식 적용 (콤마/엔터 구분)
- [ ] Task: Conductor - User Manual Verification 'Phase 2: UI 컴포넌트 개선' (Protocol in workflow.md)

## Phase 3: 다중 검색 로직 및 API 연동
- [ ] Task: 다중 조건 병렬 호출 로직 구현
    - [ ] 입력된 여러 태그에 대해 API를 각각 호출하고 결과를 합산하는 로직 작성
    - [ ] 합산된 결과에서 중복 데이터(공고번호 기준) 제거 처리
- [ ] Task: 저장된 검색 조건 불러오기 UI 구현
    - [ ] 검색 조건을 선택할 수 있는 모달 창 및 API 연동 구현
- [ ] Task: Conductor - User Manual Verification 'Phase 3: 다중 검색 및 관리' (Protocol in workflow.md)
