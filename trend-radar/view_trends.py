# view_trends.py — 누적된 trends.db를 검색·조회하는 CLI
# 이제 GitHub에 들어가 매일 복사할 필요 없이, 여기서 바로 찾아본다.
#
# 사용 예:
#   python view_trends.py                     # 최근 20개
#   python view_trends.py -n 50               # 최근 50개
#   python view_trends.py -c 패션             # 카테고리에 '패션' 들어간 것
#   python view_trends.py -k 애플             # 제목·요약에 '애플' 들어간 것
#   python view_trends.py -d 2026-07-03       # 특정 날짜
#   python view_trends.py --stats             # 통계만

import argparse
import sqlite3
import os

DB_PATH = "trends.db"


def connect():
    if not os.path.exists(DB_PATH):
        raise SystemExit(
            f"⚠️ {DB_PATH} 가 없습니다. 먼저 trend_radar.py 를 한 번 실행하세요."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def show_stats(conn):
    total = conn.execute("SELECT COUNT(*) FROM trends").fetchone()[0]
    days = conn.execute(
        "SELECT COUNT(DISTINCT collected_date) FROM trends"
    ).fetchone()[0]
    print(f"\n📊 총 {total}개 기사 · {days}일치 누적\n")
    rows = conn.execute(
        "SELECT category, COUNT(*) AS n FROM trends "
        "GROUP BY category ORDER BY n DESC"
    ).fetchall()
    for r in rows:
        print(f"  {r['n']:>4}개  {r['category']}")
    print()


def query(conn, args):
    sql = "SELECT collected_date, category, title, link, ai_summary FROM trends"
    where, params = [], []

    if args.category:
        where.append("category LIKE ?")
        params.append(f"%{args.category}%")
    if args.keyword:
        where.append("(title LIKE ? OR ai_summary LIKE ?)")
        params += [f"%{args.keyword}%", f"%{args.keyword}%"]
    if args.date:
        where.append("collected_date = ?")
        params.append(args.date)

    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY collected_date DESC, id DESC LIMIT ?"
    params.append(args.number)

    return conn.execute(sql, params).fetchall()


def print_rows(rows):
    if not rows:
        print("\n(조건에 맞는 기사가 없습니다.)\n")
        return
    current_date = None
    for r in rows:
        if r["collected_date"] != current_date:
            current_date = r["collected_date"]
            print(f"\n━━━ {current_date} ━━━")
        print(f"\n[{r['category']}] {r['title']}")
        print(f"  {r['link']}")
        if r["ai_summary"]:
            for line in r["ai_summary"].split("\n"):
                line = line.strip()
                if line:
                    print(f"  {line}")
    print()


def main():
    p = argparse.ArgumentParser(description="누적된 trends.db 조회")
    p.add_argument("-n", "--number", type=int, default=20, help="최대 개수 (기본 20)")
    p.add_argument("-c", "--category", help="카테고리 필터 (부분 일치)")
    p.add_argument("-k", "--keyword", help="제목·요약 키워드 검색")
    p.add_argument("-d", "--date", help="날짜 (YYYY-MM-DD)")
    p.add_argument("--stats", action="store_true", help="통계만 출력")
    args = p.parse_args()

    conn = connect()
    if args.stats:
        show_stats(conn)
    else:
        print_rows(query(conn, args))
    conn.close()


if __name__ == "__main__":
    main()
