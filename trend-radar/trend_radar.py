# trend_radar.py — v0.2.0: 큐레이션 요약 + SQLite 아카이빙 (매일 DB에 누적)
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import os
import time
import sqlite3
from dotenv import load_dotenv
from groq import Groq

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
    "너는 패션·음악·테크 트렌드를 골라 소개하는 매거진 에디터야. "
    "아래 기사를 한국어로 정리해줘.\n\n"
    "[반드시 지킬 규칙]\n"
    "- 한국어로만 써. 한자·일본어·태국어 등 다른 언어 문자를 절대 섞지 마 "
    "(예: '愛好家' 금지 -> '애호가').\n"
    "- 제목을 그대로 번역·반복하지 마.\n"
    "- 감각적이되 과장하지 마. 트렌드 매거진 톤.\n"
    "- 문장은 반드시 '~다'로 끝내라. '~하세요', '~써보세요', '~시대입니다' 같은 "
    "권유·광고 문구는 금지.\n"
    "- 이모지는 한 줄에 최대 1개, 포인트로만.\n\n"
    "[두 줄의 역할을 분명히 나눠라 — 같은 말을 반복하면 실패다]\n"
    "핵심: 무슨 일인지 '구체적 사실'로. 고유명사·디테일·숫자를 반드시 살려라. "
    "추상적 감상('~감성을 담았다')은 금지. (90자 이내)\n"
    "왜 주목: 핵심에 쓴 단어를 반복하지 말고, 그 사실 '너머의 더 큰 흐름·맥락·의미'만 "
    "짚어라. (90자 이내)\n\n"
    "[출력은 이 두 줄만]\n"
    "핵심: ...\n"
    "왜 주목: ...\n\n"
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
# 그래서 모든 기사를 DB 한 곳에 쌓고, link를 UNIQUE로 잡아 중복은 자동으로 건너뛴다.
DB_PATH = "trends.db"


def init_db():
    """DB와 테이블이 없으면 만든다. (있으면 그대로 둔다)"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trends (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            collected_date TEXT NOT NULL,
            category       TEXT NOT NULL,
            title          TEXT NOT NULL,
            link           TEXT NOT NULL UNIQUE,
            ai_summary     TEXT,
            created_at     TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.commit()
    conn.close()


def save_to_db(items_by_category):
    """오늘 수집한 기사를 DB에 누적한다. link가 이미 있으면 건너뛴다."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    new_count = 0
    for category, items in items_by_category.items():
        for item in items:
            cur = conn.execute(
                "INSERT OR IGNORE INTO trends "
                "(collected_date, category, title, link, ai_summary) "
                "VALUES (?, ?, ?, ?, ?)",
                (today, category, item["title"], item["link"], item["ai_summary"]),
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