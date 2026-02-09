## backend

[narajanter.py]

1.  AVALUE_URL 대신 아래 URL로 변경하기 원함. 아래 URL은 응답 값이 다르므로 `BidAValueItem` 알맞게 수정하여 기존 동작이 제대로 작동하도록 수정. `BidValueItem`에는 **bssamt를 꼭 추가해야함**. 그리고 유의미하게 보여줄 다른 필드 있다면 추가해서 FE에서 보여줘도 좋음.

- 변경 URL

```
공사_URL = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoCnstwkBsisAmount"
용역_URL = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcBsisAmount"
```

- 공사\_URL, 용역\_URL의 응답 정보

```
mapping = {
    "bidNtceNo": "입찰공고번호",
    "envCnsrvcst": "환경보전비",
    "mrfnHealthInsrprm": "국민건강보험료",
    "odsnLngtrmrcprInsrprm": "노인장기요양보험료",
    "bidNtceNm": "입찰공고명",
    "bssamt": "기초금액",
    "sftyMngcst": "산업안전보건관리비",
    "lbrcstBssRate": "노무비기준율",
    "rmrk1": "비고1",
    "rmrk2": "비고2",
    "inptDt": "입력일시",
    "rsrvtnPrceRngBgnRate": "예비가격범위시작률",
    "rsrvtnPrceRngEndRate": "예비가격범위종료율",
    "etcGnrlexpnsBssRate": "기타경비기준율",
    "rtrfundNon": "퇴직공제부금비",
    "npnInsrprm": "국민연금보험료",
    "usefulAmt": "가용금액",
    "resultCode": "결과코드",
    "bidNtceOrd": "입찰공고차수",
    "bssamtOpenDt": "기초금액공개일시",
    "evlBssAmt": "평가기준금액",
    "gnrlMngcstBssRate": "일반관리비기준율",
    "scontrctPayprcePayGrntyFee": "하도급대금지급보증수수료",
    "dfcltydgrCfcnt": "난이도계수",
    "prftBssRate": "이윤기준율",
    "bidClsfcNo": "입찰분류번호",
    "sftyChckMngcst": "안전관리비",
    "bidPrceCalclAValYn": "입찰가격산식A여부",
    "bssAmtPurcnstcst": "기초금액순공사비",
    "qltyMngcst": "품질관리비",
    "qltyMngcstAObjYn": "품질관리비A적용대상여부",
}
```

## frontend

1. frontend [BidCalculator.tsx]에서 `budgetPrice` 대신 `bssamt` 보내도록. 그래서 `bssamt`(기초금액) 기준으로 예상 금액 계산하도록 수정.

2. backend에서 추가한 `BidAValueItem`에 맞게 수정하고, UI, UX 수정.
