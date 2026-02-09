# Implementation Report: 메인 페이지 UX/UI 개선

## Summary
메인 페이지의 사용자 경험을 대폭 개선했습니다. LocalStorage를 활용한 상태 유지, 초기 진입 시 자동 검색, 통합된 기간 선택기(DateRangePicker), 그리고 여러 지역 및 업종을 동시에 검색할 수 있는 태그 입력 UI와 병렬 API 호출 로직을 구현했습니다.

## Architecture Update
- **Frontend:** `useSearchState` 커스텀 훅을 통해 로컬 스토리지와 동기화된 상태 관리 체계 구축.
- **API:** `backendApi.searchBids`에서 다중 태그 입력 시 병렬로 `fetch`를 수행하고 결과를 클라이언트 사이드에서 병합 및 중복 제거(Deduplication) 처리.

## Technical Decisions
- **Client-side Merging:** 백엔드 API가 다중 검색 필터를 지원하지 않으므로, 프론트엔드에서 각 필터 조합별로 요청을 보내고 결과를 합치는 방식을 채택하여 빠른 기능 구현과 데이터 일관성 확보.
- **LocalStorage Persistence:** 새로고침 시에도 사용자가 보던 검색 결과와 필터가 유지되도록 설계.

## Issues & Future Work
- **Calendar Layout:** 일부 브라우저 환경에서 달력의 요일 행 레이아웃이 어긋나는 이슈가 보고됨. 향후 UI 라이브러리 업데이트 또는 CSS Grid를 사용한 전면 재설계 필요.
