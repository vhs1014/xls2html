# 신규 rowspan 처리 관련 페이지   이후 안정화 되면 head2html.py 로 이동..

import pandas as pd
import numpy as np
import re
from typing import Tuple, Dict
from bs4 import BeautifulSoup

def format_cell(x):
    if pd.notna(x):
        if hasattr(x, 'strftime'):  # datetime 객체인 경우
            return x.strftime('%Y-%m-%d')
        elif isinstance(x, (int, float)):  # 숫자인 경우
            return '{:,}'.format(x)
        else:
            return str(x)
    return ''

def head2json(df: pd.DataFrame) -> Dict:
    """엑셀 데이터를 JSON으로 변환"""
    result = {}
    product_name_found = False
    
    # 월 추출을 위한 패턴
    month_pattern = r'(\d+월)'
    
    # DataFrame을 문자열로 변환하고 한 번에 월 찾기
    df_str = df.to_string(index=False, na_rep='')
    months = set(re.findall(month_pattern, df_str))
    
    # 찾은 월들을 정렬하고 문자열로 변환 (숫자 부분으로 정렬)
    if months:
        result['출발월'] = ','.join(sorted(months, key=lambda x: int(x.rstrip('월'))))
    
    # 상품명 찾기 - 첫 번째로 나오는 한 줄에 한 칸만 값이 있는 데이터
    for i in range(df.shape[0]):
        row = df.iloc[i]
        # 데이터 포맷팅
        row_data = [format_cell(x) if pd.notna(x) else '' for x in row]
        # 빈 값이 아닌 셀 찾기
        non_empty_cells = [x for x in row_data if str(x).strip()]
        
        # # 한 줄에 한 칸만 값이 있는 경우
        # if len(non_empty_cells) == 1 and not product_name_found:
        #     result['상품명'] = non_empty_cells[0]
        #     product_name_found = True
        #     continue  # 이 행은 테이블 데이터에 포함하지 않음
    
    # 각 행을 순번을 키로 하여 처리
    row_num = 1  # 새로운 행 번호 카운터
    for i in range(df.shape[0]):
        row = df.iloc[i]
        row_data = [format_cell(x) if pd.notna(x) else '' for x in row]
        non_empty_cells = [x for x in row_data if str(x).strip()]
        
        # # 상품명 행은 건너뛰기
        # if len(non_empty_cells) == 1 and non_empty_cells[0] == result.get('상품명'):
        #     continue
            
        # 나머지 행들은 처리
        result[str(row_num)] = '||'.join(str(x).replace('\n', '<br>') for x in row_data)
        row_num += 1
    
    return result

def json2html(data: Dict, spanData: list) -> str:
    """JSON 데이터를 HTML로 변환"""
    from bs4 import BeautifulSoup
    
    # 기본 HTML 구조 생성
    html = '<div class="info-section"><table class="info-table"><tbody></tbody></table></div>'
    soup = BeautifulSoup(html, 'html.parser')
    tbody = soup.find('tbody')
    
    # 1단계: 기본 테이블 생성 (colspan, rowspan 없는 상태)
    table_map = []  # 셀의 원래 위치를 저장할 2차원 배열
    row_index = 0
    
    for key in sorted(data.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        if key != '출발월':
            cells = data[key].split('||')
            tr = soup.new_tag('tr')
            tbody.append(tr)
            
            # 현재 행의 위치 맵핑 배열 생성
            current_row_map = []
            table_map.append(current_row_map)
            
            # 모든 셀 생성
            for col_idx, cell_content in enumerate(cells):
                td = soup.new_tag('td')
                td['class'] = 'first-cell' if col_idx == 0 else 'data-cell'
                
                # HTML 태그가 포함된 경우에만 BeautifulSoup 사용
                if '<' in str(cell_content) and '>' in str(cell_content):
                    parsed_content = BeautifulSoup(str(cell_content), 'html.parser').decode_contents()
                    td.append(BeautifulSoup(parsed_content, 'html.parser'))
                else:
                    td.string = str(cell_content)
                
                tr.append(td)
                current_row_map.append((row_index, col_idx))
            
            row_index += 1
    
    # 2단계: spanData를 기반으로 셀 병합 처리
    rows = tbody.find_all('tr')
    
    for row_idx, row_spans in enumerate(spanData):
        for col_idx, (colspan, rowspan) in enumerate(row_spans):
            if colspan == 1 and rowspan == 1:
                continue
                
            # 실제 위치 찾기
            actual_row, actual_col = find_actual_position(table_map, row_idx, col_idx)
            if actual_row is None or actual_col is None:
                continue
            
            # 현재 셀 가져오기
            current_row = rows[actual_row]
            current_cells = current_row.find_all('td')
            if actual_col >= len(current_cells):
                continue
            
            current_cell = current_cells[actual_col]
            cells_to_remove = []
            
            # span 값 적용
            if colspan > 1:
                current_cell['colspan'] = colspan
            if rowspan > 1:
                current_cell['rowspan'] = rowspan
            
            # rowspan 범위 내의 모든 행에서 셀 삭제 처리
            for r in range(actual_row, min(actual_row + rowspan, len(rows))):
                target_row = rows[r]
                target_cells = target_row.find_all('td')
                
                # 첫 번째 행이 아닌 경우에만 첫 번째 셀 삭제 대상에 추가
                if r > actual_row and actual_col < len(target_cells):
                    cells_to_remove.append(target_cells[actual_col])
                
                # colspan에 해당하는 우측 셀들 삭제 대상에 추가
                if colspan > 1:
                    for c in range(actual_col + 1, min(actual_col + colspan, len(target_cells))):
                        cells_to_remove.append(target_cells[c])
            
            # 수집된 셀들 삭제
            for cell in cells_to_remove:
                cell.decompose()
    
    # 각 행의 오른쪽 빈 셀들 병합 처리
    rows = tbody.find_all('tr')
    for row in rows:
        cells = row.find_all('td')
        if not cells:  # 셀이 없는 행은 건너뛰기
            continue
            
        # 오른쪽에서부터 빈 셀 찾기
        last_non_empty_idx = len(cells) - 1
        while last_non_empty_idx >= 0:
            cell_content = cells[last_non_empty_idx].get_text().strip()
            if cell_content:  # 내용이 있는 셀을 찾으면 중단
                break
            last_non_empty_idx -= 1
            
        # 내용이 있는 셀의 다음 셀부터 마지막 셀까지 병합
        if last_non_empty_idx >= 0 and last_non_empty_idx < len(cells) - 1:
            target_cell = cells[last_non_empty_idx]
            current_colspan = int(target_cell.get('colspan', 1))
            new_colspan = current_colspan + (len(cells) - 1 - last_non_empty_idx)
            target_cell['colspan'] = new_colspan
            
            # 병합될 셀들 삭제
            for i in range(last_non_empty_idx + 1, len(cells)):
                cells[i].decompose()
    
    # 스타일 추가
    style = soup.new_tag('style')
    style.string = '''
        /* 기본 테이블 스타일 */
        .info-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        /* 기본 셀 스타일 */
        .info-table td {
            padding: 8px 12px !important;
            font-size: 14px;
        }
        
        /* 첫 번째 셀 스타일 */
        .info-table td.first-cell {
            background-color: #f8f9fa;
            font-weight: 700;
        }
        
        /* 데이터 셀 스타일 (첫 번째 셀 제외) */
        .info-table td.data-cell {
            border-left: 1px solid #ccc;
        }
        
        /* 행 테두리 기본 스타일 */
        .info-table tr {
            border-top: 1px solid #ccc;
        }

        /* 첫 번째 셀이 비어있는 행의 상단 테두리 제거 */
        .info-table tr.empty-first {
            border-top: none;
        }

        /* 테이블의 마지막 행은 항상 하단 테두리 표시 */
        .info-table tr:last-child {
            border-bottom: 1px solid #ccc !important;
        }

        /* 모바일 스타일 */
        @media screen and (max-width: 768px) {
            /* info-section 패딩과 배경색 제거 */
            .info-section {
                padding: 0 !important;
                background-color: transparent !important;
            }

            /* title-section 마진 제거 */
            .title-section {
                margin: 0 !important;
            }

            /* 테이블 스타일 */
            .info-table, .info-table tbody {
                display: block;
                width: 100%;
            }

            /* tbody 패딩 제거 */
            .info-table tbody {
                padding: 0 !important;
            }
            
            /* 모든 행을 블록으로 표시 */
            .info-table tr {
                display: flex;
                flex-direction: column;
                margin-bottom: 16px;
                border: none;
            }
            
            /* 모든 셀을 블록으로 표시 */
            .info-table td {
                display: block;
                width: 100%;
                box-sizing: border-box;
            }
        }
    '''
    soup.insert(0, style)
    
    return str(soup)

def find_actual_position(table, merged_row, merged_col):
    for row in range(len(table)):
        for col in range(len(table[row])):
            if table[row][col] == (merged_row, merged_col):
                return row, col
    return None, None

def create_html_merge(df: pd.DataFrame, spanData: dict = None) -> Tuple[Dict, str]:
    """엑셀 데이터를 HTML로 변환하는 메인 함수"""
    # 엑셀 데이터를 JSON으로 변환
    json_data = head2json(df)
    
    # # 상품명 섹션 HTML 생성
    # title_html = ''
    # if '상품명' in json_data:
    #     title_html = f'''
    #     <div class="title-section">
    #         <h1>{json_data['상품명']}</h1>
    #     </div>
    #     '''
    
    # JSON을 HTML로 변환 (테이블 부분)
    table_html = json2html(json_data, spanData)
    
    # 전체 HTML 조합
    # html_content = title_html + table_html
    return json_data, table_html