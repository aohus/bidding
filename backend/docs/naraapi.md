url: http://apis.data.go.kr/1230000/ad/BidPublicInfoService

나라장터검색조건에 의한 입찰공고공사조회 API
endpoint: getBidPblancListInfoCnstwkPPSSrch

#### 요청 변수

```
* numOfRows
* pageNo
* ServiceKey
type
* inqryDiv: 조회구분
	1:공고게시일시, 2:개찰일시
	- 공고게시일시 : 공고일자(pblancDate)
	- 개찰일시 : 개찰일시(opengDt)

inqryBgnDt: YYYYMMDDHHMM
inqryEndDt : YYYYMMDDHHMM
bidNtceNm : 입찰공고명
ntceInsttCd : 공고기관코드
ntceInsttNm : 공고기관명
dminsttCd: 수요기관코드
dminsttCd: 수요기관명
prtcptLmtRgnCd: 참가제한지역코드
	11 : 서울특별시
	26 : 부산광역시
	27 : 대구광역시
	28 : 인천광역시
	29 : 광주광역시
	30 : 대전광역시
	31 : 울산광역시
	36 : 세종특별자치시
	41 : 경기도
	42 : 강원도
	43 : 충청북도
	44 : 충청남도
	45 : 전라북도
	46 : 전라남도
	47 : 경상북도
	48 : 경상남도
	50 : 제주도
	51 : 강원특별자치도
	52 : 전북특별자치도
	99 : 기타
	00: 전국
prtcptLmtRgnNm: 참가제한지역명
indstrytyCd: 업종코드 (4)
indstrytyNm: 업종명
presmptPrceBgn: 추정가격시작
presmptPrceEnd: 추정가격종료
dtilPrdctClsfcNo: 세부품명번호
masYn: 다수공금경쟁자여부
prcrmntReqNo: 조달요청번호
bidClseExcpYn: 입찰마감제외여부
intrntnlDivCd: 국제입찰구분코드
	국내: 1, 국제: 2
```

#### 응답 변수

```
* resultCode: 결과코드
* resultMsg: 결과메세지
* numOfRows: 한 페이지 결과 수
* pageNo: 페이지 번호
* totalCount: 전체 결과 수
* bidNtceNo: 입찰공고번호
	입찰공고 관리번호 형식
	조달청: 년도4+월2+순번5,
	차세대: R+년도2+단계2+순번8
		단계:
			BK(입찰),
			TA(계약),
			DD:(발주계획),
			BD(사전규격),
			BK(통합입찰)
* bidNtceOrd: 입찰공고차수
	- 재공고·재입찰 시 증가
reNtceYn: 재공고여부
* rgstTyNm: 등록유형명
	- 조달청/나라장터 자체 공고 구분
* bidNtceNm: 입찰공고명
	- 공사·사업명 요약
* dminsttCd: 수요기관코드
* dminsttNm: 수요기관명
* bidMethdNm: 입찰방식명
	- 찰/직찰/우편 등
* cntrctCnclsMthdNm: 계약체결방법명
	- 일반경쟁/제한경쟁/지명경쟁/수의계약
* bidQlfctRgstDt: 입찰참가자격등록마감일시
	- 참가자격 등록 마감
* cmmnSpldmdAgrmntClseDt: 공동수급협정마감일시
	- 공동수급협정 등록 마감
* bidBeginDt: 입찰개시일시
* bidClseDt: 입찰마감일시
* opengDt: 개찰일시
ntceSpecDocUrl1~10: 공고규격서URL1~10
ntceSpecFileNm1~10: 공고규격파일명1~10
pqApplDocRcptDt: PQ신청서접수일시
arsltApplDocRcptDt: 실적신청서접수일시
jntcontrctDutyRgnNm1~3: 공동도급의무지역명1~3
rgnDutyJntcontrctRt: 지역의무공동도급비율
	- 공동도급 합산 하한(%)
bdgtAmt: 예산금액
	- 공고의 예산금액(원화,원)
presmptPrce: 추정가격
	- 부가세 제외 추정액
aplBssCntnts: 적용기준내용
mainCnsttyCnstwkPrearngAmt: 주공종공사예정금액
	- 적격심사 주공종 추정액
opengPlce: 개찰장소
dcmtgOprtnDt: 설명회실시일시
dcmtgOprtnPlce: 설명회실시장소
* rgstDt: 등록일시
ntceKindNm: 공고종류명
	- 등록/변경/취소/재공고 구분
intrbidYn: 국제입찰여부
	- 국제입찰 대상 여부
bidNtceDt: 입찰공고일시
refNo: 참조번호
	- 자체 전자조달 공고번호 또는 나라장터 참조번호
ntceInsttCd: 공고기관코드
ntceInsttNm: 공고기관명
cmmnSpldmdAgrmntRcptdocMethd: 공동수급협정서접수방식
cmmnSpldmdCorpRgnLmtYn: 공동수급업체지역제한여부
rbidPermsnYn: 재입찰허용여부
pqApplDocRcptMthdNm: PQ신청서접수방법명
arsltApplDocRcptMthdNm: 실적신청서접수방법명
dtlsBidYn: 내역입찰여부
bidPrtcptLmtYn: 입찰참가제한여부
prearngPrceDcsnMthdNm: 예정가격결정방법명
totPrdprcNum: 총예가건수
drwtPrdprcNum: 추첨예가건수
govsplyAmt: 관급금액
indstrytyEvlRt: 업종평가비율
mainCnsttyNm: 주공종명
incntvRgnNm1: 가산지역명1
incntvRgnNm2: 가산지역명2
incntvRgnNm3: 가산지역명3
incntvRgnNm4: 가산지역명4
contrctrcnstrtnGovsplyMtrlAmt: 도급자설치관급자재금액
govcnstrtnGovsplyMtrlAmt: 관급자설치관급자재금액
bidNtceDtlUrl: 입찰공고상세URL
bidNtceUrl: 입찰공고URL
bidPrtcptFeePaymntYn: 입찰참가수수료납부여부
bidPrtcptFee: 입찰참가수수료
bidGrntymnyPaymntYn: 입찰보증금납부여부
crdtrNm: 채권자명
cmmnSpldmdCnum: 공동수급업체수
untyNtceNo: 통합공고번호
sptDscrptDocUrl1~5: 현장설명서URL1~5
subsiCnsttyNm1~9: 부대공종명1~9
subsiCnsttyIndstrytyEvlRt1~9: 부공종업종평가비율1~9
cmmnSpldmdMethdCd: 공동수급방식코드
	공500001 : 공동이행
	공500002 : 분담이행
	공500003 : 주계약자관리방식
	공500004 : 단독계약
	공500005 : 혼합방식
	공500006 : 공동이행 또는 분담이행
	공500007 : 혼합_단독
	공500008 : 혼합_공동
	공500012 : 해당없음
cmmnSpldmdMethdNm: 공동수급방식명
stdNtceDocUrl: 표준공고서URL
brffcBidprcPermsnYn: 지사투찰허용여부
cnsttyAccotShreRateList: 공종별지분율목록
+ cnstrtnAbltyEvlAmtList: 시공능력평가금액목록
	[제한그룹번호^면허지역통합코드명^면허지역통합코드^시공능력평가금액],
	[제한그룹번호^면허지역통합코드명^면허지역통합코드^시공능력평가금액]
dsgntCmptYn: 지명경쟁여부
arsltCmptYn: 실적경쟁여부
pqEvalYn: PQ심사여부
ntceDscrptYn: 공고설명여부
rsrvtnPrceReMkngMthdNm: 가격재작성방법명
mainCnsttyPresmptPrce: 주공종추정가격
orderPlanUntyNo: 발주계획통합번호
sucsfbidLwltRate: 낙찰하한율
bfSpecRgstNo: 사전규격등록번호
sucsfbidMthdCd: 낙찰방법코드
	한글 1자리 + 숫자 6자리(낙030021)
sucsfbidMthdNm: 낙찰방법명
	낙찰자를 결정하는 방법-낙찰방법 세부기준
chgDt: 변경일시
	YYYY-MM-DD HH:MM:SS
dminsttOfclEmailAdrs: 수요기관담당자이메일주소
indstrytyLmtYn: 업종제한여부
cnstrtsiteRgnNm: 공사현장지역명

rgnDutyJntcontrctYn: 지역의무공동도급여부
	- 지역업체 참여가 일정 지분율 이상일 경우에만 입창이 가능한 공고 여부
	  Y:해당 N:공고서에의함
chgNtceRsn: 변경공고사유
rbidOpengDt: 재입찰개찰일시
ciblAplYn: 건설산업법적용대상여부
mtltyAdvcPsblYn: 상호시장진출허용여부
mtltyAdvcPsblYnCnstwkNm: 건설산업법적용대상공사명

VAT: 부가가치세
indutyVAT: 주공종부가가치세
indstrytyMfrcFldEvlYn: 주력분야평가여부
bidWgrnteeRcptClseDt: 입찰보증서접수마감일시
rgnLmtBidLocplcJdgmBssCd: 지역제한입찰소재지판단기준코드
rgnLmtBidLocplcJdgmBssNm: 지역제한입찰소재지판단기준명
```
