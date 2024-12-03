import json

def save_names_to_text():
    # 2.json 파일 읽기
    with open('2.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # name 값만 추출
    names = [city['name'] for city in data]
    
    # 텍스트 파일로 저장
    with open('city_names.txt', 'w', encoding='utf-8') as f:
        for name in names:
            f.write("'" + name + '\n')
    
    print(f"총 {len(names)}개의 도시 이름이 city_names.txt 파일에 저장되었습니다.")

# 함수 실행
save_names_to_text()