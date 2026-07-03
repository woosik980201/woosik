# build_archive.py — trends.db 전체를 하나의 브라우징 가능한 아카이브 HTML로 뽑는다.
# trends_YYYYMMDD.html 이 '그날의 스냅샷'이라면, 이건 '전체를 한 페이지에서 검색'하는 아카이브다.
# 카테고리 탭 + 키워드 검색은 브라우저 안에서 도는 순수 JS라 서버가 필요 없다.
#
# 실행:  python build_archive.py   ->  index.html 생성

import sqlite3
import os
import html
from datetime import datetime

DB_PATH = "trends.db"
OUT_PATH = "index.html"


def load_rows():
    if not os.path.exists(DB_PATH):
        raise SystemExit(
            f"⚠️ {DB_PATH} 가 없습니다. 먼저 trend_radar.py 를 실행하세요."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT collected_date, category, title, link, ai_summary "
        "FROM trends ORDER BY collected_date DESC, id DESC"
    ).fetchall()
    conn.close()
    return rows


def summary_html(ai_summary):
    """'핵심: ... / 왜 주목: ...' 2줄을 라벨 강조해서 렌더한다."""
    if not ai_summary:
        return ""
    out = '<div class="ai-summary">'
    for line in ai_summary.split("\n"):
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            label, _, rest = line.partition(":")
            out += (
                f'<div class="s-line"><strong>{html.escape(label)}</strong>'
                f'{html.escape(rest.strip())}</div>'
            )
        else:
            out += f'<div class="s-line">{html.escape(line)}</div>'
    out += "</div>"
    return out


def build(rows):
    total = len(rows)
    days = len({r["collected_date"] for r in rows})
    categories = sorted({r["category"] for r in rows})
    generated = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")

    tabs = '<button class="tab active" data-cat="전체">전체</button>'
    for c in categories:
        tabs += f'<button class="tab" data-cat="{html.escape(c)}">{html.escape(c)}</button>'

    items = ""
    current_date = None
    for r in rows:
        if r["collected_date"] != current_date:
            current_date = r["collected_date"]
            items += f'<h2 class="date" data-cat="__date__">{current_date}</h2>\n'
        items += (
            f'<div class="item" data-cat="{html.escape(r["category"])}">'
            f'<span class="cat">{html.escape(r["category"])}</span>'
            f'<a href="{html.escape(r["link"])}" target="_blank">{html.escape(r["title"])}</a>'
            f'{summary_html(r["ai_summary"])}'
            f"</div>\n"
        )

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>트렌드 아카이브 · trend-radar</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         max-width: 720px; margin: 0 auto; padding: 40px 20px 80px;
         color: #222; line-height: 1.6; background: #fff; }}
  h1 {{ font-size: 24px; margin: 0 0 4px; }}
  .meta {{ color: #999; font-size: 13px; margin-bottom: 24px; }}
  .controls {{ position: sticky; top: 0; background: #fff; padding: 12px 0;
               border-bottom: 1px solid #eee; z-index: 10; }}
  #search {{ width: 100%; padding: 10px 14px; font-size: 14px; border: 1px solid #ddd;
             border-radius: 8px; margin-bottom: 10px; }}
  .tabs {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .tab {{ font-size: 13px; padding: 6px 12px; border: 1px solid #ddd; background: #fafafa;
          border-radius: 999px; cursor: pointer; color: #555; }}
  .tab.active {{ background: #222; color: #fff; border-color: #222; }}
  h2.date {{ font-size: 14px; color: #aaa; margin: 32px 0 8px; font-weight: 500;
             border-top: 1px solid #f0f0f0; padding-top: 20px; }}
  .item {{ margin: 10px 0; padding: 14px; background: #f7f7f5; border-radius: 10px; }}
  .cat {{ display: inline-block; font-size: 11px; color: #888; background: #ececec;
          padding: 2px 8px; border-radius: 999px; margin-bottom: 8px; }}
  .item a {{ color: #222; text-decoration: none; font-weight: 600; display: block; }}
  .item a:hover {{ text-decoration: underline; }}
  .ai-summary {{ font-size: 14px; color: #444; padding-top: 8px; margin-top: 8px;
                 border-top: 1px dashed #ddd; }}
  .ai-summary .s-line {{ margin: 3px 0; }}
  .ai-summary strong {{ color: #222; margin-right: 5px; }}
  .footer {{ margin-top: 48px; font-size: 12px; color: #bbb; text-align: center; }}
  .empty {{ color: #aaa; text-align: center; padding: 40px 0; display: none; }}
</style>
</head>
<body>
<h1>🌱 트렌드 아카이브</h1>
<div class="meta">총 {total}개 · {days}일치 누적 · 갱신 {generated}</div>

<div class="controls">
  <input id="search" type="text" placeholder="키워드 검색 (제목·요약)">
  <div class="tabs">{tabs}</div>
</div>

<div id="list">
{items}
</div>
<div class="empty" id="empty">조건에 맞는 기사가 없습니다.</div>

<div class="footer">trend-radar · made by ssik · powered by Groq</div>

<script>
  const search = document.getElementById('search');
  const tabs = document.querySelectorAll('.tab');
  const items = document.querySelectorAll('.item');
  const dates = document.querySelectorAll('h2.date');
  const empty = document.getElementById('empty');
  let activeCat = '전체';

  function apply() {{
    const q = search.value.trim().toLowerCase();
    let shown = 0;
    items.forEach(el => {{
      const catOk = activeCat === '전체' || el.dataset.cat === activeCat;
      const textOk = !q || el.textContent.toLowerCase().includes(q);
      const show = catOk && textOk;
      el.style.display = show ? '' : 'none';
      if (show) shown++;
    }});
    // 날짜 헤더: 그 아래 보이는 항목이 하나도 없으면 숨긴다
    dates.forEach(h => {{
      let next = h.nextElementSibling, any = false;
      while (next && !next.classList.contains('date')) {{
        if (next.classList.contains('item') && next.style.display !== 'none') any = true;
        next = next.nextElementSibling;
      }}
      h.style.display = any ? '' : 'none';
    }});
    empty.style.display = shown === 0 ? 'block' : 'none';
  }}

  tabs.forEach(t => t.addEventListener('click', () => {{
    tabs.forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    activeCat = t.dataset.cat;
    apply();
  }}));
  search.addEventListener('input', apply);
</script>
</body>
</html>"""


def main():
    rows = load_rows()
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(build(rows))
    print(f"✅ 아카이브 생성: {OUT_PATH} ({len(rows)}개 기사)")


if __name__ == "__main__":
    main()
