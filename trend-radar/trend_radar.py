# trend_radar.py — v0.2.0: 큐레이션 요약 + SQLite 아카이빙 (매일 DB에 누적)
import sys
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import os
import time
import sqlite3
from urllib.parse import urlsplit, urlunsplit
from dotenv import load_dotenv
from groq import Groq

# Windows 로컬 콘솔(cp949)이 모델 응답에 섞인 외국어 문자를 못 그려서
# UnicodeEncodeError로 죽는 것을 방지 (GitHub Actions는 이미 UTF-8이라 영향 없음)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# === 환경 변수 로딩 ===
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("⚠️ GROQ_API_KEY가 .env 파일에 없습니다.")
    exit()

client = Groq(api_key=GROQ_API_KEY)
MODEL = "llama-3.3-70b-versatile"


# === RSS 피드 목록 ===
FEEDS = {
    "AI/테크 (해외)":   "https://news.ycombinator.com/rss",
    "AI/테크 (한국)":   "https://feeds.feedburner.com/geeknews-feed",
    "개발자 (한국)":    "https://yozm.wishket.com/magazine/feed/",
    "디자인 (해외)":    "https://abduzeedo.com/rss.xml",
    "디자인 (한국)":    "https://rss.blog.naver.com/designpress2016.xml",
    "패션 (해외)":      "https://hypebeast.com/feed",
    "패션 (한국)":      "https://hypebeast.kr/feed",
    "음악":            "https://pitchfork.com/rss/news/",
}


def clean_summary(raw):
    """RSS의 description에서 HTML 태그 제거"""
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", "", raw)
    text = " ".join(text.split())
    if len(text) > 300:
        text = text[:300].rsplit(" ", 1)[0] + "…"
    return text


# 한자 / 일본어(가나) / 태국어 문자 탐지 — 한글·이모지는 허용
BANNED_SCRIPTS = re.compile(r"[一-鿿぀-ゟ゠-ヿ฀-๿]")

CURATOR_PROMPT = (
    "너는 패션·문화·기술의 교차점을 관찰하는 트렌드 큐레이터다. 단순히 뉴스를 요약하는 것이 아니라, "
    "\"이 소식이 어떤 흐름의 신호인가\"를 읽어내는 것이 너의 임무다.\n\n"
    "[선별 기준]\n"
    "아래 중 하나 이상에 해당하는 소식만 고른다:\n"
    "1. 패션·문화와 기술이 교차하는 소식 (브랜드의 AI 활용, 디지털 패션, 크리에이터 이코노미 등)\n"
    "2. 소비자 행동이나 문화적 흐름의 변화 신호\n"
    "3. 개인 개발자·크리에이터가 실제로 활용할 수 있는 AI·자동화 도구나 기법\n"
    "4. 산업 구조를 바꿀 수 있는 움직임 (인수, 규제, 기술 전환)\n\n"
    "[제외 기준]\n"
    "다음은 고르지 않는다:\n"
    "- 문화적 맥락 없이 스펙만 나열된 단순 신제품 홍보\n"
    "- 클릭베이트성 제목 (과장된 숫자, \"충격\", \"결국\" 류)\n"
    "- 이미 고른 항목과 실질적으로 같은 소식\n"
    "- 일반화하기 어려운 지역 단신\n\n"
    "[작성 규칙]\n"
    "각 항목을 아래 형식으로 쓴다:\n\n"
    "제목: (원문 제목을 자연스러운 한국어로)\n"
    "요약: (핵심 내용 1~2문장)\n"
    "왜 주목: (이 소식이 어떤 흐름의 신호인지 1문장. 반드시 원문 내용에 근거할 것)\n\n"
    "[중요한 제약]\n"
    "- 반드시 한국어로만 작성한다. 한자, 일본어, 태국어, 베트남어를 포함한 모든 외국 문자를 절대 쓰지 않는다.\n"
    "- 원문에 없는 사실을 지어내지 않는다. \"왜 주목\" 부분도 원문에서 읽어낼 수 있는 범위 안에서만 해석한다. "
    "확실하지 않으면 단정하지 않는다.\n"
    "- 과장된 표현을 쓰지 않는다. 담백하고 명확하게 쓴다.\n"
    "- 설명이나 인사말을 앞뒤에 붙이지 않는다. 위 형식의 결과만 출력한다.\n\n"
    "[좋은 예시]\n"
    "제목: 럭셔리 브랜드 A, 생성형 AI로 아카이브 기반 디자인 실험\n"
    "요약: A사가 과거 30년 아카이브를 학습시킨 자체 AI로 신규 컬렉션 시안을 만드는 실험을 공개했다.\n"
    "왜 주목: 브랜드 유산이 \"보존 대상\"에서 \"창작 재료\"로 바뀌는 신호로, 다른 헤리티지 브랜드로 번질 수 있는 움직임이다.\n\n"
    "[나쁜 예시 — 이렇게 쓰지 말 것]\n"
    "제목: B사 신형 이어폰 출시... 가격은 충격적\n"
    "요약: B사가 신형 이어폰을 냈다. 음질이 좋아졌고 비싸졌다.\n"
    "(문화적 맥락 없는 신제품 홍보 + 클릭베이트 제목. 흐름의 신호가 아니라 제외 대상이다.)\n\n"
    "제목: {title}\n본문: {source}"
)


def fetch_body(url, limit=2000):
    """기사 본문을 실제로 가져온다 (RSS 요약 대신 재료를 풍부하게)."""
    try:
        html = requests.get(
            url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}
        ).text
        soup = BeautifulSoup(html, "html.parser")
        paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        return " ".join(paras)[:limit]
    except Exception as e:
        print(f"   (본문 수집 실패: {e})")
        return ""


def ai_summarize(title, link, description):
    """본문을 가져와 '핵심 / 왜 주목' 2줄 큐레이션을 생성한다."""
    body = fetch_body(link)
    source = body if len(body) > 200 else description  # 본문 실패 시 RSS 폴백
    prompt = CURATOR_PROMPT.format(title=title, source=source)

    def generate(extra=""):
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt + extra}],
            temperature=0.5,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()

    try:
        out = generate()
        # 안전장치: 외국어 문자가 새면 한 번 더 강하게 재생성
        if BANNED_SCRIPTS.search(out):
            print("   (외국어 문자 감지 -> 재생성)")
            out = generate(
                "\n\n[경고] 방금 외국어 문자가 섞였어. 한국어와 이모지만 써서 다시 써."
            )
        return out
    except Exception as e:
        print(f"   ⚠️ 요약 실패: {e}")
        return ""


def build_html(items_by_category):
    today = datetime.now().strftime("%Y년 %m월 %d일")
    
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>오늘의 트렌드 · {today}</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 640px; 
         margin: 40px auto; padding: 0 20px; color: #222; line-height: 1.6; }}
  h1 {{ font-size: 22px; border-bottom: 2px solid #222; padding-bottom: 10px; }}
  h2 {{ font-size: 16px; margin-top: 32px; color: #555; }}
  .item {{ margin: 12px 0; padding: 14px; background: #f7f7f5; border-radius: 8px; }}
  .item a {{ color: #222; text-decoration: none; font-weight: 500; display: block; margin-bottom: 6px; }}
  .item a:hover {{ text-decoration: underline; }}
  .ai-summary {{ font-size: 14px; color: #444; line-height: 1.6;
                 padding: 8px 0 0; border-top: 1px dashed #ddd; margin-top: 8px; }}
  .ai-summary .s-line {{ margin: 3px 0; }}
  .ai-summary strong {{ color: #222; margin-right: 5px; }}
  .original {{ font-size: 12px; color: #999; line-height: 1.4; margin-top: 6px; }}
  .footer {{ margin-top: 40px; font-size: 12px; color: #999; text-align: center; }}
</style>
</head>
<body>
<h1>🌱 오늘의 트렌드 · {today}</h1>
"""
    
    for category, items in items_by_category.items():
        html += f"<h2>{category}</h2>\n"
        for item in items:
            html += f'<div class="item">'
            html += f'<a href="{item["link"]}" target="_blank">{item["title"]}</a>'
            if item["ai_summary"]:
                html += '<div class="ai-summary">'
                for line in item["ai_summary"].split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    if ":" in line:
                        label, _, rest = line.partition(":")
                        html += f'<div class="s-line"><strong>{label}</strong>{rest.strip()}</div>'
                    else:
                        html += f'<div class="s-line">{line}</div>'
                html += '</div>'
            html += f'</div>\n'
    
    html += """
<div class="footer">trend-radar v0.1.0 · made by ssik · powered by Groq</div>
</body>
</html>"""
    return html


def build_markdown(items_by_category):
    today = datetime.now().strftime("%Y년 %m월 %d일")
    weekday = ["월", "화", "수", "목", "금", "토", "일"][datetime.now().weekday()]
    
    md = f"# 🌱 오늘의 트렌드 · {today} ({weekday})\n\n"
    
    for category, items in items_by_category.items():
        md += f"## {category}\n\n"
        for item in items:
            md += f"- **[{item['title']}]({item['link']})**\n"
            if item["ai_summary"]:
                for line in item["ai_summary"].split("\n"):
                    line = line.strip()
                    if line:
                        md += f"  > {line}\n"
            md += "\n"

    md += "\n---\n*trend-radar v0.1.0 · made by ssik · powered by Groq*\n"
    return md


def fetch_and_summarize():
    """모든 피드를 가져와서 AI 요약까지 붙임"""
    items_by_category = {}
    total = 0
    
    print("\n🌱 트렌드 수집 + AI 요약 시작\n" + "=" * 40)
    
    for category, url in FEEDS.items():
        print(f"\n📡 {category}")
        feed = feedparser.parse(url)
        items = []
        
        for entry in feed.entries[:3]:
            title = entry.title
            description = clean_summary(entry.get("summary", ""))
            
            print(f"  · {title[:40]}...")
            ai_summary = ai_summarize(title, entry.link, description)
            if ai_summary:
                print(f"    🤖 {ai_summary}")
            
            items.append({
                "title": title,
                "link": entry.link,
                "ai_summary": ai_summary,
            })
            total += 1
            
            # API 호출 간격 (분당 15회 제한 회피)
            time.sleep(1)
        
        items_by_category[category] = items
    
    return items_by_category, total


# === SQLite 아카이빙 ===
# 매일 새로 만드는 html/md는 '그날의 스냅샷'이라 검색·누적이 안 된다.
# 그래서 모든 기사를 DB 한 곳에 쌓는다.
# 중복 판정의 핵심: 'URL 완전 일치'는 너무 빡빡해서, 같은 기사인데 ?utm=… 같은
# 추적 파라미터·끝 슬래시·http/https·www 차이만 있어도 다른 기사로 새어든다.
# 그래서 link를 '정규화(normalize)'한 link_key를 진짜 중복 기준으로 삼는다.
DB_PATH = "trends.db"


def normalize_link(url):
    """URL에서 본질만 남긴다: scheme·www·쿼리·프래그먼트·끝 슬래시 제거."""
    try:
        p = urlsplit((url or "").strip())
        netloc = p.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        path = p.path.rstrip("/")
        key = urlunsplit(("", netloc, path, "", ""))  # scheme·query·fragment 버림
        return key or (url or "").strip().lower()
    except Exception:
        return (url or "").strip().lower()


def init_db():
    """DB·테이블을 만들고, 구버전 DB면 link_key 컬럼으로 마이그레이션한다."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trends (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            collected_date TEXT NOT NULL,
            category       TEXT NOT NULL,
            title          TEXT NOT NULL,
            link           TEXT NOT NULL,
            link_key       TEXT,
            ai_summary     TEXT,
            created_at     TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # --- 구버전 DB 마이그레이션: link_key 컬럼이 없으면 추가·채우고 중복 청소 ---
    cols = [r[1] for r in conn.execute("PRAGMA table_info(trends)")]
    if "link_key" not in cols:
        conn.execute("ALTER TABLE trends ADD COLUMN link_key TEXT")
    # link_key가 비어 있는 행 채우기 (신규·구버전 모두 안전)
    for row_id, link in conn.execute(
        "SELECT id, link FROM trends WHERE link_key IS NULL OR link_key = ''"
    ).fetchall():
        conn.execute(
            "UPDATE trends SET link_key = ? WHERE id = ?",
            (normalize_link(link), row_id),
        )
    # 같은 link_key가 여러 개면 가장 먼저 들어온 것(min id)만 남기고 삭제
    conn.execute("""
        DELETE FROM trends WHERE id NOT IN (
            SELECT MIN(id) FROM trends GROUP BY link_key
        )
    """)
    # 이제부터 link_key는 유일해야 한다 (INSERT OR IGNORE가 이 인덱스로 걸러줌)
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_trends_link_key ON trends(link_key)"
    )
    conn.commit()
    conn.close()


def save_to_db(items_by_category):
    """오늘 수집한 기사를 DB에 누적한다. 정규화 링크(link_key)가 같으면 건너뛴다."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    new_count = 0
    for category, items in items_by_category.items():
        for item in items:
            cur = conn.execute(
                "INSERT OR IGNORE INTO trends "
                "(collected_date, category, title, link, link_key, ai_summary) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    today, category, item["title"], item["link"],
                    normalize_link(item["link"]), item["ai_summary"],
                ),
            )
            if cur.rowcount > 0:
                new_count += 1
    conn.commit()
    conn.close()
    return new_count


def save_all(items_by_category):
    today_str = datetime.now().strftime('%Y%m%d')
    
    html_filename = f"trends_{today_str}.html"
    with open(html_filename, "w", encoding="utf-8") as f:
        f.write(build_html(items_by_category))
    
    md_filename = f"trends_{today_str}.md"
    with open(md_filename, "w", encoding="utf-8") as f:
        f.write(build_markdown(items_by_category))
    
    print(f"\n✅ HTML 저장: {html_filename}")
    print(f"✅ Markdown 저장: {md_filename}")


if __name__ == "__main__":
    items, total = fetch_and_summarize()
    
    # 안전장치: 요약이 하나도 없으면 저장 안 함
    summary_count = sum(
        1 for cat_items in items.values() 
        for item in cat_items 
        if item["ai_summary"]
    )
    if summary_count == 0:
        print("\n⚠️ AI 요약이 전부 실패했습니다. 파일 저장을 건너뜁니다.")
        print("   (기존 파일을 덮어쓰지 않았습니다.)")
    else:
        save_all(items)
        init_db()
        new_count = save_to_db(items)
        print(f"🗄️ DB 누적: 새 기사 {new_count}개 추가 (중복 제외)")
        print(f"\n🎉 완료! 총 {total}개 중 {summary_count}개 요약 성공")