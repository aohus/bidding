"""첨부파일 매핑 유틸 (API 응답 -> BidAttachment, 레거시 공고 URL 폴백)."""
from __future__ import annotations

from typing import Iterable, List, Optional
from urllib.parse import urlparse

from app.schemas.bid import (
    BidAttachment,
    BidAttachmentItem,
    BidEorderAttachmentItem,
)

DEFAULT_FILE_NAME = "첨부파일"
LEGACY_NTCE_SPEC_COUNT = 10
LEGACY_SPT_DSCRPT_COUNT = 5


def is_safe_url(url: Optional[str]) -> bool:
    """http(s) 스킴과 호스트가 있는 URL 만 허용 (javascript:, file: 등 차단)."""
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def parse_sno(value: Optional[str]) -> Optional[int]:
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def _file_name(name: Optional[str], url: str) -> str:
    if name and name.strip():
        return name.strip()
    tail = urlparse(url).path.rsplit("/", 1)[-1]
    return tail or DEFAULT_FILE_NAME


def _build(
    source: str,
    doc_div: Optional[str],
    name: Optional[str],
    url: Optional[str],
    sno: Optional[int],
) -> Optional[BidAttachment]:
    if not is_safe_url(url):
        return None
    clean_url = url.strip()
    return BidAttachment(
        source=source,
        docDivNm=doc_div or None,
        fileNm=_file_name(name, clean_url),
        fileUrl=clean_url,
        sno=sno,
    )


def map_ntce_attachments(items: Iterable[BidAttachmentItem]) -> List[BidAttachment]:
    mapped = (
        _build("ntce", i.atchDocDivNm, i.atchFileNm, i.atchFileUrl, parse_sno(i.atchSno))
        for i in items
    )
    return [m for m in mapped if m]


def map_eorder_attachments(
    items: Iterable[BidEorderAttachmentItem],
) -> List[BidAttachment]:
    mapped = (
        _build(
            "eorder",
            i.eorderDocDivNm,
            i.eorderAtchFileNm,
            i.eorderAtchFileUrl,
            parse_sno(i.atchSno),
        )
        for i in items
    )
    return [m for m in mapped if m]


def legacy_attachments(data: Optional[dict]) -> List[BidAttachment]:
    """저장된 공고 data 의 구 URL 필드(ntceSpecDocUrl* 등)에서 첨부 목록 생성."""
    if not data:
        return []
    out: List[BidAttachment] = []
    for i in range(1, LEGACY_NTCE_SPEC_COUNT + 1):
        out.append(
            _build("legacy", "공고문서", data.get(f"ntceSpecFileNm{i}"),
                   data.get(f"ntceSpecDocUrl{i}"), i)
        )
    for i in range(1, LEGACY_SPT_DSCRPT_COUNT + 1):
        out.append(
            _build("legacy", "지원설명문서", data.get(f"sptDscrptFileNm{i}"),
                   data.get(f"sptDscrptDocUrl{i}"), i)
        )
    out.append(_build("legacy", "표준공고문서", None, data.get("stdNtceDocUrl"), None))
    return [a for a in out if a]


def dedupe(items: Iterable[BidAttachment]) -> List[BidAttachment]:
    seen: set[tuple[str, str]] = set()
    result: List[BidAttachment] = []
    for item in items:
        key = (item.source, item.fileUrl)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
