# trend_radar.py — v0.0.4: 요약 추가
import feedparser
from datetime import datetime
import re


FEEDS = {
    "AI/테크":  "https://news.ycombinator.com/rss",
    "디자인":   "https://abduzeedo.com/rss.xml",
    "패션":     "https://hypebeast.com/feed",
    "음악":     "https://pitchfork.com/rss/news/",
}


def clean_summary(raw):
    """RSS에 들어있는 description은 HTML 태그가 섞여있을 때가 많아서 청소."""
    if not raw:
        return ""
    # HTML 태그 제거
    text = re.sub(r"<[^>]+>", "", raw)
    # 줄바꿈·공백 정리
    text = " ".join(text.split())
    # 너무 길면 자르기 (200자)
    if len(text) > 200:
        text = text[:200].rsplit(" ", 1)[0] + "…"
    return text


def build_html():
    today = datetime.now().strftime("%Y년 %m월 %d일")
    
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>오늘의 트렌드 · {today}</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 600px; 
         margin: 40px auto; padding: 0 20px; color: #222; line-height: 1.6; }}
  h1 {{ font-size: 22px; border-bottom: 2px solid #222; padding-bottom: 10px; }}
  h2 {{ font-size: 16px; margin-top: 32px; color: #555; }}
  .item {{ margin: 12px 0; padding: 14px; background: #f7f7f5; border-radius: 8px; }}
  .item a {{ color: #222; text-decoration: none; font-weight: 500; display: block; margin-bottom: 6px; }}
  .item a:hover {{ text-decoration: underline; }}
  .summary {{ font-size: 13px; color: #666; line-height: 1.5; }}
  .footer {{ margin-top: 40px; font-size: 12px; color: #999; text-align: center; }}
</style>
</head>
<body>
<h1>🌱 오늘의 트렌드 · {today}</h1>
"""

    for category, url in FEEDS.items():
        html += f"<h2>{category}</h2>\n"
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]:
            summary = clean_summary(entry.get("summary", ""))
            html += f'<div class="item">'
            html += f'<a href="{entry.link}" target="_blank">{entry.title}</a>'
            if summary:
                html += f'<div class="summary">{summary}</div>'
            html += f'</div>\n'

    html += """
<div class="footer">trend-radar v0.0.4 · made by ssik</div>
</body>
</html>"""
    return html


def build_markdown():
    today = datetime.now().strftime("%Y년 %m월 %d일")
    weekday = ["월", "화", "수", "목", "금", "토", "일"][datetime.now().weekday()]
    
    md = f"# 🌱 오늘의 트렌드 · {today} ({weekday})\n\n"
    
    for category, url in FEEDS.items():
        md += f"## {category}\n\n"
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]:
            summary = clean_summary(entry.get("summary", ""))
            md += f"- **[{entry.title}]({entry.link})**\n"
            if summary:
                md += f"  > {summary}\n"
            md += "\n"
    
    md += "\n---\n*trend-radar v0.0.4 · made by ssik*\n"
    return md


def save_all():
    today_str = datetime.now().strftime('%Y%m%d')
    
    html_filename = f"trends_{today_str}.html"
    with open(html_filename, "w", encoding="utf-8") as f:
        f.write(build_html())
    
    md_filename = f"trends_{today_str}.md"
    with open(md_filename, "w", encoding="utf-8") as f:
        f.write(build_markdown())
    
    print(f"✅ HTML 저장: {html_filename}")
    print(f"✅ Markdown 저장: {md_filename}")


if __name__ == "__main__":
    save_all()