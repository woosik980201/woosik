# compare_summary.py
# 요약 개선 실험용 스크립트 — "기존 방식" vs "개선 방식"을 나란히 비교한다.
# trend_radar.py 는 전혀 건드리지 않는 독립 실험 파일. (자동화에 영향 없음)
#
# 실행: venv 활성화 상태에서  ->  python compare_summary.py

import os
import re
import time
import feedparser
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from groq import Groq

# === 환경 변수 ===
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise SystemExit("⚠️ GROQ_API_KEY가 .env에 없습니다.")

client = Groq(api_key=GROQ_API_KEY)
MODEL = "llama-3.3-70b-versatile"

# 한자 / 일본어(가나) / 태국어 문자 탐지용 — 한글(uac00-ud7a3)은 허용, 이모지도 허용
BANNED_SCRIPTS = re.compile(r"[一-鿿぀-ゟ゠-ヿ฀-๿]")

# 비교는 빠르게 보려고 피드 2개 × 기사 2개만
FEEDS = {
    "패션 (해외)":    "https://hypebeast.com/feed",
    "AI/테크 (한국)": "https://feeds.feedburner.com/geeknews-feed",
}
N_PER_FEED = 2


def strip_html(raw: str) -> str:
    text = re.sub(r"<[^>]+>", "", raw or "")
    return " ".join(text.split())


# ---------------- 기존 방식 ----------------
# 입력: 제목 + RSS 짧은 요약(300자로 자름) / 출력: 50자 한 줄
def old_summary(title: str, rss_desc: str) -> str:
    desc = strip_html(rss_desc)[:300]
    prompt = (
        "다음 기사를 한국어로 한 문장(50자 이내)으로 요약해줘.\n"
        "요약만 출력하고, 다른 말은 절대 붙이지 마.\n\n"
        f"제목: {title}\n내용: {desc}"
    )
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=100,
    )
    return r.choices[0].message.content.strip().strip('"').strip("'")


# ---------------- 개선 방식 ----------------
# 변화 1: RSS 대신 기사 '본문'을 실제로 가져온다.
def fetch_body(url: str, limit: int = 2000) -> str:
    try:
        html = requests.get(
            url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}
        ).text
        soup = BeautifulSoup(html, "html.parser")
        paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        body = " ".join(paras)
        return body[:limit]
    except Exception as e:
        print(f"   (본문 수집 실패: {e})")
        return ""


# 변화 2: '요약'이 아니라 '큐레이션'. 감각적 큐레이터 톤 + 핵심/왜주목 2줄.
PROMPT_V2 = (
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


def new_summary(title: str, url: str, rss_desc: str):
    body = fetch_body(url)
    source = body if len(body) > 200 else strip_html(rss_desc)  # 본문 실패 시 RSS 폴백
    prompt = PROMPT_V2.format(title=title, source=source)

    def generate(extra: str = "") -> str:
        r = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt + extra}],
            temperature=0.5,
            max_tokens=300,
        )
        return r.choices[0].message.content.strip()

    out = generate()
    # 안전장치: 외국어 문자가 새면 한 번 더 강하게 재생성
    if BANNED_SCRIPTS.search(out):
        print("   (외국어 문자 감지 -> 재생성)")
        out = generate("\n\n[경고] 방금 외국어 문자가 섞였어. 한국어와 이모지만 써서 다시 써.")

    return out, len(source)


def main():
    print("\n🔬 요약 개선 비교 실험 시작\n")
    for cat, url in FEEDS.items():
        feed = feedparser.parse(url)
        print("=" * 72)
        print(f"[{cat}]")
        for entry in feed.entries[:N_PER_FEED]:
            title = entry.title
            desc = entry.get("summary", "")
            print("-" * 72)
            print(f"제목: {title}")
            print(f"링크: {entry.link}")

            old = old_summary(title, desc)
            time.sleep(1)
            new, srclen = new_summary(title, entry.link, desc)
            time.sleep(1)

            print(f"\n  [기존] {old}")
            print(f"\n  [개선] (본문 {srclen}자 사용)")
            for line in new.splitlines():
                print(f"  {line}")
            print()


if __name__ == "__main__":
    main()
