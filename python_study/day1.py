# 아이템 하나를 '이름표(key) + 값' 으로 표현
coat = {
    "brand": "Acne Studios",
    "name": "오버사이즈 울 코트",
    "price": 890000,
    "category": "outer",
}

print(coat["name"])    # 이름표로 값 꺼내기 → 오버사이즈 울 코트
print(coat["price"])   # → 890000

closet = [
    {"brand": "Acne Studios", "name": "오버사이즈 울 코트", "price": 890000, "category": "outer"},
    {"brand": "COS", "name": "코튼 오버셔츠", "price": 79000, "category": "top"},
    {"brand": "Lemaire", "name": "와이드 트라우저", "price": 420000, "category": "bottom"},
    {"brand": "무신사 스탠다드", "name": "베이직 반팔티", "price": 19900, "category": "top"},
    {"brand": "Our Legacy", "name": "워싱 데님 자켓", "price": 350000, "category": "outer"},
]


for item in closet:
    print(f'{item["brand"]} · {item["name"]} · {item["price"]}원')


    cheap_first = sorted(closet, key=lambda x: x["price"])

for item in cheap_first:
    print(f'{item["price"]}원 · {item["name"]}')