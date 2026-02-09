# 나라장터 입찰공고 검색 시스템 개발 계획

## 파일 구조
1. **src/pages/Index.tsx** - 메인 페이지 (검색 폼 + 결과 테이블)
2. **src/components/SearchForm.tsx** - 검색 조건 입력 폼
3. **src/components/BidTable.tsx** - 입찰 공고 결과 테이블
4. **src/components/BidCalculator.tsx** - 투찰 가격 계산 모달
5. **src/lib/api.ts** - API 호출 함수
6. **src/lib/bidCalculations.ts** - 투찰 가격 계산 로직
7. **src/types/bid.ts** - 타입 정의

## 주요 기능
1. 검색 폼: 날짜 범위, 지역, 예산 범위 필터
2. API 연동: 나라장터 API 호출 및 데이터 파싱
3. 결과 테이블: 입찰 공고 정보 표시
4. 투찰 버튼: 최적 가격 계산 및 서류 다운로드

## 구현 순서
1. 타입 정의 (bid.ts)
2. API 함수 (api.ts)
3. 계산 로직 (bidCalculations.ts)
4. 검색 폼 컴포넌트 (SearchForm.tsx)
5. 테이블 컴포넌트 (BidTable.tsx)
6. 계산기 모달 (BidCalculator.tsx)
7. 메인 페이지 통합 (Index.tsx)