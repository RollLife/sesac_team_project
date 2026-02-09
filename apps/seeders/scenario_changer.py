"""
시나리오 전환기 - Redis를 통해 실행 중인 realtime_generator의 시나리오를 변경

사용법:
  python apps/seeders/scenario_changer.py
"""

import redis
import sys

SCENARIOS = {
    1: "여성 구매고객 대량 유입",
    2: "남성 IT/게이밍 폭주",
    3: "블랙프라이데이 대규모 세일",
    4: "설날/추석 선물세트 시즌",
    5: "여름 패션/뷰티 시즌",
    6: "겨울 패딩/방한용품 시즌",
    7: "뷰티 인플루언서 바이럴",
    8: "MZ세대 (10-20대) 트렌드 쇼핑",
    9: "5060 건강/식품 집중 구매",
    10: "캠핑 시즌 (봄/가을)",
    11: "신학기 시즌 (가구/IT)",
    12: "결혼/혼수 시즌",
    13: "새해 다이어트/헬스 시즌",
    14: "육아맘 생필품 대량 구매",
    15: "골프 시즌 (봄/가을)",
    16: "여행 성수기 (여름/연말)",
    17: "새벽배송 식품 집중",
    18: "가전 할인 행사 (빅세일)",
    19: "평일 심야 소량 주문",
    20: "전 카테고리 균등 대량 주문",
    21: "트래픽 폭증 (스트레스 테스트)",
}


def print_menu():
    print("\n╔═══════════════════════════════════════════╗")
    print("║          시나리오 선택 메뉴               ║")
    print("╠═══════════════════════════════════════════╣")
    for num, desc in SCENARIOS.items():
        print(f"║  {num:>2}. {desc:<35} ║")
    print("║   0. 기본 패턴 (현실적 분포)              ║")
    print("╚═══════════════════════════════════════════╝")


def main():
    try:
        r = redis.Redis(host='localhost', port=6379, decode_responses=True, socket_timeout=3)
        r.ping()
    except Exception as e:
        print(f"Redis 연결 실패: {e}")
        sys.exit(1)

    print_menu()
    print("\n번호를 입력하세요 (exit: 종료)\n")

    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not raw:
            continue
        if raw.lower() == "exit":
            break

        try:
            num = int(raw)
        except ValueError:
            print("숫자를 입력하세요.")
            continue

        if num < 0 or num > 21:
            print("0~21 사이 번호를 입력하세요.")
            continue

        r.set('scenario:current', str(num))

        if num == 0:
            print("-> 기본 패턴으로 복귀")
        else:
            print(f"-> 시나리오 {num} ({SCENARIOS[num]}) 적용됨")

    print("종료.")


if __name__ == "__main__":
    main()
