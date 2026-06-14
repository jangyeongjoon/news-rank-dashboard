# 국내 뉴스 기업/키워드 랭킹 MVP

이 프로토타입은 Google News RSS에서 최근 1일 국내 경제/기업/산업 뉴스 제목을 수집하고, 기업/조직명과 키워드 빈도를 집계해 HTML 대시보드를 생성합니다.

## 실행

```bash
python3 work/news_rank_dashboard.py --output-dir outputs
```

생성 파일:

- `outputs/news_rank_dashboard.html`
- `outputs/news_rank_data.json`

## 현재 범위

- 뉴스 제목 기반 수집
- 기업/조직명 사전 기반 카운트
- 간단한 키워드 토큰 빈도 집계
- 브라우저에서 바로 열 수 있는 정적 HTML 생성

## 다음 개선

- 본문 수집 및 중복 기사 묶기
- 기업명 사전 CSV/DB 분리
- 전일 대비 급상승률 계산
- 하루 1회 자동 실행 스케줄러 연결
