#!/usr/bin/env python3
"""
Daily Korean news company/keyword ranking prototype.

Fetches Google News RSS titles for the last day, counts configured
organizations and keywords, then writes a standalone HTML dashboard.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo


KST = ZoneInfo("Asia/Seoul")

DEFAULT_QUERIES = [
    "국내 경제 뉴스 when:1d",
    "국내 기업 뉴스 when:1d",
    "한국 산업 뉴스 when:1d",
    "한국 증권 뉴스 기업 when:1d",
    "삼성전자 SK하이닉스 현대차 LG 네이버 카카오 when:1d",
]

ORGANIZATIONS = [
    "삼성전자",
    "SK하이닉스",
    "현대차",
    "기아",
    "LG전자",
    "LG에너지솔루션",
    "삼성SDI",
    "포스코",
    "POSCO",
    "네이버",
    "NAVER",
    "카카오",
    "한화",
    "두산",
    "HD현대",
    "셀트리온",
    "삼성바이오로직스",
    "현대모비스",
    "KB금융",
    "신한금융",
    "하나금융",
    "우리금융",
    "쿠팡",
    "롯데",
    "신세계",
    "CJ",
    "KT",
    "SK텔레콤",
    "LG유플러스",
    "대한항공",
    "아시아나",
    "에코프로",
    "한국전력",
    "한전",
    "현대건설",
    "삼성물산",
    "한미반도체",
    "HMM",
    "LS",
    "OCI",
    "고려아연",
    "스페이스X",
    "SpaceX",
    "테슬라",
    "미래에셋증권",
    "미래에셋",
    "한국은행",
    "제네시스",
    "맥도날드",
    "MSCI",
    "한국산업인력공단",
    "한경협",
    "경과원",
]

NORMALIZE = {
    "SpaceX": "스페이스X",
    "NAVER": "네이버",
    "POSCO": "포스코",
    "한전": "한국전력",
    "미래에셋": "미래에셋증권",
}

STOPWORDS = set(
    """
    오늘 국내 기업 경제 뉴스 기자 관련 발표 올해 지난 대한 이번 있는 없는 위해 이후 통해 시장
    정부 산업 투자 한국 주요 글로벌 것으로 비롯 대해 가운데 가장 거래 종합 단독 속보 포토
    영상 오늘의 when 이병훈 중앙대 교수 이사장에 기자가 따르면 밝혔다 말했다
    """.split()
)


@dataclass(frozen=True)
class NewsItem:
    title: str
    published: str
    source_link: str


def rss_url(query: str) -> str:
    params = urllib.parse.urlencode({"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"})
    return f"https://news.google.com/rss/search?{params}"


def clean_title(title: str) -> str:
    title = html.unescape(title)
    title = re.sub(r"<[^>]+>", " ", title)
    title = re.sub(r"\s+-\s+[^-]+$", "", title)
    return re.sub(r"\s+", " ", title).strip()


def parse_pub_date(value: str) -> str:
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).astimezone(KST).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, IndexError):
        return value


def fetch_items(queries: list[str]) -> list[NewsItem]:
    items: list[NewsItem] = []
    seen: set[str] = set()
    for query in queries:
        with urllib.request.urlopen(rss_url(query), timeout=20) as response:
            root = ET.fromstring(response.read())
        for item in root.findall(".//item"):
            title = clean_title(item.findtext("title") or "")
            if not title:
                continue
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(
                NewsItem(
                    title=title,
                    published=parse_pub_date(item.findtext("pubDate") or ""),
                    source_link=item.findtext("link") or "",
                )
            )
    return items


def count_organizations(items: list[NewsItem]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in items:
        for org in ORGANIZATIONS:
            if org in item.title:
                counts[NORMALIZE.get(org, org)] += 1
    return counts


def tokenize_keywords(title: str) -> list[str]:
    title = re.sub(r"[\[\]().,!?“”\"'‘’:;·…/\\|-]", " ", title)
    tokens = re.findall(r"[가-힣A-Za-z0-9%]{2,}", title)
    blocked = set(ORGANIZATIONS) | set(NORMALIZE) | set(NORMALIZE.values())
    keywords = []
    for token in tokens:
        normalized = NORMALIZE.get(token, token)
        if normalized in blocked or token in blocked:
            continue
        if normalized in STOPWORDS or token in STOPWORDS:
            continue
        if re.fullmatch(r"\d+|\d+년|\d+월|\d+일|\d+주|\d+조|\d+억|\d+분기|\d+시|\d+%", token):
            continue
        if token in {"0주", "1분기", "2년", "14일", "19일", "50년"}:
            continue
        keywords.append(normalized)
    return keywords


def count_keywords(items: list[NewsItem]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in items:
        counts.update(tokenize_keywords(item.title))
    return counts


def top_rows(counter: Counter[str], limit: int) -> list[dict[str, object]]:
    return [{"name": name, "count": count} for name, count in counter.most_common(limit)]


def render_bar_rows(rows: list[dict[str, object]]) -> str:
    max_count = max((int(row["count"]) for row in rows), default=1)
    rendered = []
    for index, row in enumerate(rows, start=1):
        count = int(row["count"])
        width = max(4, round(count / max_count * 100))
        rendered.append(
            f"""
            <div class="rank-row">
              <div class="rank-index">{index}</div>
              <div class="rank-main">
                <div class="rank-label">
                  <span>{html.escape(str(row["name"]))}</span>
                  <strong>{count}</strong>
                </div>
                <div class="bar-track"><div class="bar-fill" style="width:{width}%"></div></div>
              </div>
            </div>
            """
        )
    return "\n".join(rendered)


def render_titles(items: list[NewsItem], limit: int = 12) -> str:
    rows = []
    for item in items[:limit]:
        rows.append(
            f"""
            <a class="headline" href="{html.escape(item.source_link)}">
              <span>{html.escape(item.title)}</span>
              <time>{html.escape(item.published)}</time>
            </a>
            """
        )
    return "\n".join(rows)


def render_html(data: dict[str, object]) -> str:
    org_rows = render_bar_rows(data["organizations"])  # type: ignore[arg-type]
    keyword_rows = render_bar_rows(data["keywords"])  # type: ignore[arg-type]
    headlines = render_titles([NewsItem(**item) for item in data["items"]])  # type: ignore[arg-type]
    generated_at = html.escape(str(data["generated_at"]))
    item_count = int(data["item_count"])
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>오늘의 국내 뉴스 랭킹</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --ink: #20242c;
      --muted: #667085;
      --line: #d9dee7;
      --panel: #ffffff;
      --blue: #2d6cdf;
      --green: #17845b;
      --amber: #bc6c25;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }}
    header {{
      padding: 28px clamp(18px, 4vw, 48px) 18px;
      border-bottom: 1px solid var(--line);
      background: #fff;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: clamp(26px, 4vw, 40px);
      letter-spacing: 0;
    }}
    .meta {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 14px;
    }}
    main {{
      padding: 24px clamp(18px, 4vw, 48px) 42px;
      display: grid;
      gap: 20px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }}
    .metric, section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .metric {{
      padding: 16px;
      min-height: 96px;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 10px;
    }}
    .metric strong {{
      display: block;
      font-size: 26px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 20px;
    }}
    section {{
      padding: 18px;
    }}
    h2 {{
      font-size: 18px;
      margin: 0 0 16px;
    }}
    .rank-row {{
      display: grid;
      grid-template-columns: 28px minmax(0, 1fr);
      gap: 10px;
      align-items: center;
      padding: 9px 0;
      border-top: 1px solid #eef1f5;
    }}
    .rank-row:first-of-type {{ border-top: 0; }}
    .rank-index {{
      width: 24px;
      height: 24px;
      border-radius: 999px;
      display: grid;
      place-items: center;
      font-size: 12px;
      background: #edf3ff;
      color: #1c4fb5;
    }}
    .rank-label {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
      font-size: 14px;
      margin-bottom: 7px;
    }}
    .rank-label span {{
      overflow-wrap: anywhere;
      font-weight: 650;
    }}
    .rank-label strong {{
      color: var(--muted);
      font-size: 13px;
    }}
    .bar-track {{
      height: 9px;
      background: #edf0f5;
      border-radius: 999px;
      overflow: hidden;
    }}
    .bar-fill {{
      height: 100%;
      background: linear-gradient(90deg, var(--blue), var(--green));
      border-radius: 999px;
    }}
    .headlines {{
      display: grid;
      gap: 9px;
    }}
    .headline {{
      display: grid;
      gap: 5px;
      color: inherit;
      text-decoration: none;
      padding: 11px 0;
      border-top: 1px solid #eef1f5;
    }}
    .headline:first-child {{ border-top: 0; }}
    .headline span {{
      line-height: 1.45;
      overflow-wrap: anywhere;
    }}
    .headline time {{
      font-size: 12px;
      color: var(--muted);
    }}
    .note {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }}
    @media (max-width: 860px) {{
      .summary, .grid {{ grid-template-columns: 1fr; }}
      header {{ padding-top: 22px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>오늘의 국내 뉴스 랭킹</h1>
    <div class="meta">
      <span>기준시각 {generated_at}</span>
      <span>수집 제목 {item_count}개</span>
      <span>Google News RSS, 최근 1일</span>
    </div>
  </header>
  <main>
    <div class="summary">
      <div class="metric"><span>최다 언급 기업/조직</span><strong>{html.escape(str(data["top_organization"]))}</strong></div>
      <div class="metric"><span>최다 언급 키워드</span><strong>{html.escape(str(data["top_keyword"]))}</strong></div>
      <div class="metric"><span>분석 방식</span><strong>제목 빈도</strong></div>
    </div>
    <div class="grid">
      <section>
        <h2>기업/조직 TOP 10</h2>
        {org_rows}
      </section>
      <section>
        <h2>키워드 TOP 15</h2>
        {keyword_rows}
      </section>
    </div>
    <section>
      <h2>대표 뉴스 제목</h2>
      <div class="headlines">{headlines}</div>
    </section>
    <p class="note">초기 MVP는 제목 기반 집계입니다. 운영 버전에서는 중복 기사 묶기, 본문 분석, 기업명 사전 관리, 전일 대비 급상승률을 추가하는 흐름이 좋습니다.</p>
  </main>
</body>
</html>
"""


def build_dashboard(output_dir: Path, queries: list[str]) -> dict[str, object]:
    items = fetch_items(queries)
    org_counts = count_organizations(items)
    keyword_counts = count_keywords(items)
    org_rows = top_rows(org_counts, 10)
    keyword_rows = top_rows(keyword_counts, 15)
    data: dict[str, object] = {
        "generated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "item_count": len(items),
        "queries": queries,
        "organizations": org_rows,
        "keywords": keyword_rows,
        "top_organization": org_rows[0]["name"] if org_rows else "없음",
        "top_keyword": keyword_rows[0]["name"] if keyword_rows else "없음",
        "items": [item.__dict__ for item in items],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "news_rank_data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "news_rank_dashboard.html").write_text(render_html(data), encoding="utf-8")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Korean daily news ranking dashboard.")
    parser.add_argument("--output-dir", default="outputs", help="Directory for generated HTML/JSON files.")
    parser.add_argument("--query", action="append", help="Additional Google News RSS query.")
    args = parser.parse_args()

    queries = DEFAULT_QUERIES + (args.query or [])
    data = build_dashboard(Path(args.output_dir), queries)
    print(f"generated_at={data['generated_at']}")
    print(f"item_count={data['item_count']}")
    print(f"html={Path(args.output_dir) / 'news_rank_dashboard.html'}")
    print(f"json={Path(args.output_dir) / 'news_rank_data.json'}")


if __name__ == "__main__":
    main()
