# html 을 함수로 받아서. 변경하고 html 과 json 결과물을 return 하는 함수를 만들고자해.. 
# 먼저 본프로젝트 루트 폴더에 있는 코드베이스를 확인하.. 
# 만들함수는 
# html 의   table 을 받아서 
# 1. 현 테이블의 셀별 colspan, rowspan 을  [colspan,rowspan] 으로 배열의 배열값으로 저장
# 2. 테이블의 모든 병합된 셀을 분리하여 콜스판, 로스판을 1로 만든다. 
# 3. 일정표 헤더 row 을 찾는다.. 일자, 지역, 시간, 교통, 주요일정, 식사 중 3개 이상 들어간 줄
# 4. 헤더 row 하단에 푸터 row 를 찾는다.  주요일정고, 지역에 해당하는 값이 하나라도 없는 줄
# 5. 헤더줄 상단, 푸터줄 하단은   head_df, footer_df 로 df 형태로 분리 하는데 
#      innerHTML 값으로 df 데이터를 채우고 
# 6. 일정은 itn_df 로 하되   셀 내에 <br>태그는 상하 셀분리를해야 하기 때문에
#     해당줄마다 최대 br 수를 체크해서 전줄 rowspan을 적용한다음 
#     개별 셀 마다 br 태그만큼 셀분리하면서 rowspan을 대응 수정한다. 
#      그리고 나서 itn_df 로 df 데이터 형식으로 변환하고 이때 innerText 를 사용한다. 

# 7. 각각의 df 는 json으로 변경하고,  이를 합쳐서 return 할꺼고
# 8.  각각의 json은 html 로 전환 해서 합쳐서 리텅 할껀데.. 
#     기타 유사 참조 코드 는 본트로젝트 코드베이스를 확인해서 참조해줘




# 3. DF 형태의 데이터로 변경 한다. 
# 4. 
#    1) table 태그를 DF 데이터 프레임으로 전환 
#       1-1) 병합된 셀을 분리 한다. 
#       1-2) 헤더를 찾는다, 푸터를 찾는다 
#       1-3) 헤더 상단의 모든 row 는 innerHtml 을 추출하고 <br> 태그의 셀분리를 안한다.  
#            row, colspan 데이터 추출 -> DF전화 -> Json 전환 -> HTML로전환 -> 다시 셀병합   
#            html -> html 로전환 안하는 이유는 json자료추출(인쇄 모듈 이후 디자인 변경을 위해서 )      
#       1-4) 헤더 하단의 모든 row 는 innerText을 추출하고 <br> 태그의 셀분리를 한다.
#            DF전화 -> Json 전환 -> HTML로전환
#       1-5) 푸터는 헤더상단과 동일하게 처리 한다.      
#     2) 헤더상하단을 합쳐  response 한다. 

import pandas as pd
from bs4 import BeautifulSoup
from typing import Dict, Any, Tuple, List
import re
import unicodedata
import numpy as np
from datetime import datetime, timedelta
import json

def separate_merged_cells(table: BeautifulSoup) -> BeautifulSoup:
    """
    병합된 셀을 분리하는 함수 (JavaScript 코드의 Python 구현)
    """
    rows = table.find_all('tr')
    
    for row_idx, row in enumerate(rows):
        cells = row.find_all(['td', 'th'])
        col_idx = 0
        
        while col_idx < len(cells):
            cell = cells[col_idx]
            colspan = int(cell.get('colspan', '1'))
            rowspan = int(cell.get('rowspan', '1'))
            
            # colspan 처리
            if colspan > 1:
                cell['colspan'] = '1'
                for _ in range(colspan - 1):
                    new_cell = BeautifulSoup('<td></td>', 'html.parser').td
                    cell.insert_after(new_cell)
                    cells = row.find_all(['td', 'th'])  # 셀 목록 업데이트
            
            # rowspan 처리
            if rowspan > 1:
                cell['rowspan'] = '1'
                current_col_idx = col_idx
                
                # 현재 행까지의 실제 컬럼 수 계산
                for i in range(col_idx):
                    prev_cell = cells[i]
                    prev_colspan = int(prev_cell.get('colspan', '1'))
                    current_col_idx += prev_colspan - 1
                
                # 아래 행들에 빈 셀 추가
                for i in range(1, rowspan):
                    target_row = rows[row_idx + i] if row_idx + i < len(rows) else None
                    if not target_row:
                        continue
                    
                    # 새 셀 생성
                    new_cell = BeautifulSoup('<td></td>', 'html.parser').td
                    if colspan > 1:
                        new_cell['colspan'] = str(colspan)
                    
                    # 타겟 행에서 올바른 위치 찾기
                    target_cells = target_row.find_all(['td', 'th'])
                    insert_idx = 0
                    current_pos = 0
                    
                    while insert_idx < len(target_cells) and current_pos < current_col_idx:
                        target_cell = target_cells[insert_idx]
                        target_colspan = int(target_cell.get('colspan', '1'))
                        current_pos += target_colspan
                        insert_idx += 1
                    
                    # 새 셀 삽입
                    if insert_idx < len(target_cells):
                        target_cells[insert_idx].insert_before(new_cell)
                    else:
                        target_row.append(new_cell)
            
            col_idx += 1
    
    return table

def find_header_row(df: pd.DataFrame) -> Tuple[int, Dict]:
    """
    일정표 헤더 row를 찾는 함수 (main.py의 itn_search 참조)
    """
    column_aliases = {
        'date': ['일자', '날짜', '순번', '일시', 'Date', 'Day', 'No', '월/일', '일차' ],
        'place': ['지역', '장소', 'place', 'city', '도시', '여행지', '행선지', '방문도시', '방문장소'],
        'transport': ['교통편', '이동수단', '교통', 'Trans', 'Transport', '구분'],
        'time': ['시간', 'time'],
        'itinerary': ['주요일정', '일정', '관광지', 'itinerary', '여정', '세부내용', '세부일정', '주요내용', '주요관광지', 'schedule'],
        'meal': ['식사', 'meal', 'meals']
    }
    
    for idx, row in df.iterrows():
        # 각 셀의 값에서 모든 빈칸을 지워줍니다.
        cleaned_row = [str(cell).replace(' ', '').replace('\xa0', '').replace('\n', '').lower() for cell in row]
        cells_with_matches = 0
        
        for cell in cleaned_row:
            has_match = False
            for aliases in column_aliases.values():
                if any(alias.lower() in cell for alias in aliases):
                    has_match = True
                    break
            if has_match:
                cells_with_matches += 1
                    
        if cells_with_matches >= 3:
            return idx, column_aliases
            
    return -1, column_aliases

def find_footer_row(df: pd.DataFrame, header_idx: int, column_aliases: Dict) -> int:
    """
    푸터 row를 찾는 함수 (main.py의 convert_df_to_json 참조)
    """
    def clean_text(text):
        if pd.isna(text):
            return ""
        text = str(text)
        text = unicodedata.normalize('NFKC', text)
        text = str(text).replace('\xa0', ' ')
        text = ' '.join(text.split())
        return text

    def identify_column_types(row, aliases):
        column_types = {}
        for col_idx, cell in enumerate(row):
            cell_str = str(cell).lower().strip()
            for col_type, alias_list in aliases.items():
                if any(alias.lower() in cell_str for alias in alias_list):
                    column_types[col_idx] = col_type
                    break
        return column_types

    if header_idx == -1:
        return -1

    # 헤더 행의 컬럼 타입 식별
    header_row = df.iloc[header_idx]
    header_row = [clean_text(r).replace(' ', '').lower() for r in header_row]
    column_types = identify_column_types(header_row, column_aliases)

    # 주요일정과 지역 컬럼 찾기
    itinerary_col = next((col for col, type_ in column_types.items() if type_ == 'itinerary'), None)
    place_col = next((col for col, type_ in column_types.items() if type_ == 'place'), None)

    # 푸터 찾기
    for idx in range(header_idx + 1, len(df)):
        row = df.iloc[idx]
        has_itinerary = False
        has_place = False

        if itinerary_col is not None and not pd.isna(row[itinerary_col]):
            cell_text = clean_text(row[itinerary_col]).lower()
            if cell_text:
                has_itinerary = True

        if place_col is not None and not pd.isna(row[place_col]):
            cell_text = clean_text(row[place_col]).lower()
            if cell_text:
                has_place = True

        if not has_itinerary and not has_place:
            return idx

    return -1

def convert_df_to_json_data(df: pd.DataFrame, column_aliases: Dict) -> Tuple[List[Dict], List[str], List[str], str, str]:
    """
    DataFrame을 JSON 데이터로 변환하는 함수 (main.py의 convert_df_to_json 참조)
    """
    def clean_text(text):
        if pd.isna(text):
            return ""
        text = str(text)
        text = unicodedata.normalize('NFKC', text)
        text = str(text).replace('\xa0', ' ')
        text = ' '.join(text.split())
        return text

    def identify_column_types(row):
        column_types = {}
        for col_idx, cell in enumerate(row):
            cell_str = str(cell).lower().strip()
            for col_type, aliases in column_aliases.items():
                if any(alias.lower() in cell_str for alias in aliases):
                    column_types[col_idx] = col_type
                    break
        return column_types

    # 컬럼 타입 식별
    first_row = df.iloc[0]
    first_row = [clean_text(r).replace(' ', '').lower() for r in first_row]
    column_types = identify_column_types(first_row)

    # 데이터 처리를 위한 컬럼 인덱스 찾기
    date_col = next((col for col, type_ in column_types.items() if type_ == 'date'), None)
    place_col = next((col for col, type_ in column_types.items() if type_ == 'place'), None)
    transport_col = next((col for col, type_ in column_types.items() if type_ == 'transport'), None)
    time_col = next((col for col, type_ in column_types.items() if type_ == 'time'), None)
    itinerary_col = next((col for col, type_ in column_types.items() if type_ == 'itinerary'), None)
    meal_col = next((col for col, type_ in column_types.items() if type_ == 'meal'), None)

    # depTime과 arrTime 설정
    depTime = None
    arrTime = None
    if time_col is not None:
        time_pattern = re.compile(r'^\d{1,2}:\d{2}$')
        time_values = [str(val).strip() for val in df[time_col].dropna() 
                      if isinstance(val, (str, int, float)) and 
                      time_pattern.match(str(val).strip())]
        if time_values:
            depTime = time_values[0]
            arrTime = time_values[-1]

    # 장소와 관광지 추출
    locations = []
    places = []
    
    if place_col is not None:
        locations = [clean_text(loc) for loc in df[place_col].dropna() if clean_text(loc)]
        locations = list(dict.fromkeys(locations))  # 중복 제거

    if itinerary_col is not None:
        for itn in df[itinerary_col].dropna():
            itn_text = clean_text(itn)
            if itn_text:
                # 괄호 안의 내용 추출
                bracket_pattern = r'\((.*?)\)'
                matches = re.findall(bracket_pattern, itn_text)
                for match in matches:
                    if match and len(match) >= 2:  # 최소 2글자 이상
                        places.append(match)
                # 괄호 제거 후 단어 단위로 분리
                no_brackets = re.sub(bracket_pattern, '', itn_text)
                words = no_brackets.split()
                for word in words:
                    if len(word) >= 2:  # 최소 2글자 이상
                        places.append(word)
        places = list(dict.fromkeys(places))  # 중복 제거

    # JSON 데이터 생성
    itinerary_data = []
    for idx in range(1, len(df)):  # 헤더 제외
        row = df.iloc[idx]
        row_data = {}
        
        if date_col is not None:
            row_data['date'] = clean_text(row[date_col])
        if place_col is not None:
            row_data['place'] = clean_text(row[place_col])
        if transport_col is not None:
            row_data['transport'] = clean_text(row[transport_col])
        if time_col is not None:
            row_data['time'] = clean_text(row[time_col])
        if itinerary_col is not None:
            row_data['itinerary'] = clean_text(row[itinerary_col])
        if meal_col is not None:
            row_data['meal'] = clean_text(row[meal_col])
            
        if any(row_data.values()):  # 빈 행이 아닌 경우만 추가
            itinerary_data.append(row_data)

    return itinerary_data, locations, places, depTime, arrTime

def clean_text(text):
    """
    텍스트에서 특수 유니코드 문자와 불필요한 공백을 정리하는 함수
    """
    if not text:
        return text
        
    # 유니코드 정규화 (NFKC)
    text = unicodedata.normalize('NFKC', text)
    
    # 전각 공백(\u3000)과 특수문자 처리
    text = re.sub(r'[\u3000\u200b\u200c\u200d\ufeff\xa0]', ' ', text)
    
    # HTML 태그 제거
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # 연속된 공백과 줄바꿈을 단일 공백으로 변환
    text = re.sub(r'\s+', ' ', text)
    
    # 앞뒤 공백 제거
    text = text.strip()
    
    return text

def merge_cells_with_span_data(html_table, span_data):
    """
    HTML 테이블에 span_data를 적용하여 셀 병합을 수행
    """
    soup = BeautifulSoup(html_table, 'html.parser')
    tbody = soup.find('tbody') or soup
    
    rows = tbody.find_all('tr')
    for row_idx, row_spans in enumerate(span_data):
        if row_idx >= len(rows):
            continue
        dcount = 0     
        current_row = rows[row_idx]
        
        for col_idx, (colspan, rowspan) in enumerate(row_spans):
            current_cells = current_row.find_all('td')
            if col_idx >= len(current_cells):
                continue
                
            current_cell = current_cells[col_idx]
            
            # colspan 처리
            if colspan > 1:
                current_cell['colspan'] = str(colspan)
                cells_to_remove = []
                for i in range(1, colspan):
                    next_cell_idx = col_idx + i
                    if next_cell_idx < len(current_cells):
                        cells_to_remove.append(current_cells[next_cell_idx])
                
                for cell in cells_to_remove:
                    dcount += 1
                    cell.decompose()
            
            # rowspan 처리
            if rowspan > 1:
                current_cell['rowspan'] = str(rowspan)
                for r in range(row_idx + 1, min(row_idx + rowspan, len(rows))):
                    next_row = rows[r]
                    next_row_cells = next_row.find_all('td')
                    
                    cells_to_remove = []
                    span_width = colspan if colspan > 1 else 1
                    for c in range(col_idx, min(col_idx + span_width, len(next_row_cells))):
                        if c - dcount < len(next_row_cells) and c - dcount >= 0:
                            cells_to_remove.append(next_row_cells[c - dcount])
                    
                    # for cell in cells_to_remove:
                    #     dcount += 1
                    #     cell.decompose()
                    
                    # remaining_cells = next_row.find_all('td')
                    # if not remaining_cells:
                    #     next_row.decompose()
    
    return str(soup)

def process_html_table(html_content: str) -> Tuple[str, Dict[str, Any]]:
    """
    HTML 테이블을 처리하여 변환된 HTML과 JSON 데이터를 반환하는 함수
    """
    # 특수 문자 처리
    html_content = unicodedata.normalize('NFKC', html_content)
    html_content = re.sub(r'[\u3000\u200b\u200c\u200d\ufeff\xa0]', ' ', html_content)
    html_content = re.sub(r'&nbsp;', ' ', html_content)
    html_content = re.sub(r'\s+', ' ', html_content)
    
    # BeautifulSoup으로 HTML 파싱
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')
    
    if not table:
        raise ValueError("HTML 테이블을 찾을 수 없습니다.")

    # 1. 테이블의 모든 셀의 colspan과 rowspan 값을 저장
    span_data = []
    for row in table.find_all('tr'):
        row_spans = []
        for cell in row.find_all(['td', 'th']):
            colspan = int(cell.get('colspan', '1'))
            rowspan = int(cell.get('rowspan', '1'))
            row_spans.append([colspan, rowspan])
        span_data.append(row_spans)

    # 2. 테이블의 모든 병합된 셀을 분리
    table = separate_merged_cells(table)

    # DataFrame으로 변환하여 헤더와 푸터 찾기
    df_data = []
    for row in table.find_all('tr'):
        row_data = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
        df_data.append(row_data)
    df = pd.DataFrame(df_data)

    # 3. 헤더 row 찾기
    header_idx, column_aliases = find_header_row(df)
    
    # 4. 푸터 row 찾기
    footer_idx = find_footer_row(df, header_idx, column_aliases)

    # 헤더, 본문, 푸터 데이터 분리
    header_data = df.iloc[:header_idx]
    itn_df = df.iloc[header_idx:footer_idx]
    footer_data = df.iloc[footer_idx:]
    
    # span_data도 같은 방식으로 분리
    header_spans = span_data[:header_idx]
    itn_spans = span_data[header_idx:footer_idx]
    footer_spans = span_data[footer_idx:]

    # JSON 데이터 생성 (일정 데이터만 사용)
    json_data = convert_df_to_json_data(itn_df, column_aliases)

    # HTML 생성
    from head2html import json2html
    from itn2html import ItineraryHtmlGenerator
    
    # 헤더와 푸터를 딕셔너리로 변환
    header_dict = {str(i+1): '||'.join(row) for i, row in enumerate(header_data.values)}
    footer_dict = {str(i+len(header_data)+1): '||'.join(row) for i, row in enumerate(footer_data.values)}
    
    # 헤더와 푸터 HTML 생성 후 셀 병합 적용
    header_html = json2html(header_dict)
    header_html = merge_cells_with_span_data(header_html, header_spans)
    
    footer_html = json2html(footer_dict)
    footer_html = merge_cells_with_span_data(footer_html, footer_spans)
    
    # 일정표 HTML 생성
    generator = ItineraryHtmlGenerator(json_data)
    itinerary_html = generator.generate_html()
    
    # 최종 HTML 조합
    new_html = f"{header_html}{itinerary_html}{footer_html}"

    return new_html, json_data
