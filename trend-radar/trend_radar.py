# trend_radar.py — v0.0.5: Gemini AI 한국어 요약 추가
import feedparser
from datetime import datetime
import re
import os
import time
from dotenv import load_dotenv
import google.generativeai as genai


# === 환경 변수 로딩 ===
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("⚠️ GEMINI_API_KEY가 .env 파일에 없습니다.")
    exit()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash-lite")


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


def ai_summarize(title, description):
    """Gemini AI로 한국어 한 줄 요약 생성"""
    if not description:
        content = title
    else:
        content = f"제목: {title}\n내용: {description}"
    
    prompt = f"""다음 기사를 한국어로 한 문장(50자 이내)으로 요약해줘.
요약만 출력하고, 다른 말은 절대 붙이지 마.
어조는 차분하고 정보 전달 중심으로.

{content}"""
    
    try:
        response = model.generate_content(prompt)
        summary = response.text.strip()
        # 따옴표 제거 (AI가 가끔 붙임)
        summary = summary.strip('"').strip("'").strip("「").strip("」")
        return summary
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
  .ai-summary {{ font-size: 14px; color: #444; line-height: 1.5; 
                 padding: 8px 0 0; border-top: 1px dashed #ddd; margin-top: 8px; }}
  .ai-summary::before {{ content: "🤖 "; }}
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
                html += f'<div class="ai-summary">{item["ai_summary"]}</div>'
            html += f'</div>\n'
    
    html += """
<div class="footer">trend-radar v0.0.5 · made by ssik · powered by Gemini AI</div>
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
                md += f"  > 🤖 {item['ai_summary']}\n"
            md += "\n"
    
    md += "\n---\n*trend-radar v0.0.5 · made by ssik · powered by Gemini AI*\n"
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
        
        for entry in feed.entries[:2]:
            title = entry.title
            description = clean_summary(entry.get("summary", ""))
            
            print(f"  · {title[:40]}...")
            ai_summary = ai_summarize(title, description)
            if ai_summary:
                print(f"    🤖 {ai_summary}")
            
            items.append({
                "title": title,
                "link": entry.link,
                "ai_summary": ai_summary,
            })
            total += 1
            
            # API 호출 간격 (분당 15회 제한 회피)
            time.sleep(13)
        
        items_by_category[category] = items
    
    return items_by_category, total


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
        print(f"\n🎉 완료! 총 {total}개 중 {summary_count}개 요약 성공")