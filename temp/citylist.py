import json

def remove_duplicates_and_save():
    # 파일 읽기
    with open('./temp/2.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 중복 체크를 위한 set
    seen_names = set()
    seen_iata = set()
    
    # 중복되지 않은 도시들을 저장할 리스트
    unique_cities = []

    # 각 도시 확인
    for city in data:
        name = city['name']
        iata = city['iata_code']
        
        # 도시명이나 IATA 코드가 중복되지 않은 경우만 추가
        if name not in seen_names and iata not in seen_iata:
            seen_names.add(name)
            seen_iata.add(iata)
            unique_cities.append(city)
        else:
            print(f"중복 발견: {name} ({iata})")

    # 결과 저장
    with open('2.json', 'w', encoding='utf-8') as f:
        json.dump(unique_cities, f, ensure_ascii=False, indent=2)

    print(f"원본 도시 수: {len(data)}")
    print(f"중복 제거 후 도시 수: {len(unique_cities)}")

# 함수 실행
remove_duplicates_and_save()
