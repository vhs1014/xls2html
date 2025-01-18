import pandas as pd
import numpy as np
import re
from typing import Tuple, Dict

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
        
        # 한 줄에 한 칸만 값이 있는 경우
        if len(non_empty_cells) == 1 and not product_name_found:
            result['상품명'] = non_empty_cells[0]
            product_name_found = True
            continue  # 이 행은 테이블 데이터에 포함하지 않음
    
    # 각 행을 순번을 키로 하여 처리
    row_num = 1  # 새로운 행 번호 카운터
    for i in range(df.shape[0]):
        row = df.iloc[i]
        row_data = [format_cell(x) if pd.notna(x) else '' for x in row]
        non_empty_cells = [x for x in row_data if str(x).strip()]
        
        # 상품명 행은 건너뛰기
        if len(non_empty_cells) == 1 and non_empty_cells[0] == result.get('상품명'):
            continue
            
        # 나머지 행들은 처리
        result[str(row_num)] = '||'.join(str(x).replace('\n', '<br>') for x in row_data)
        row_num += 1
    
    return result

def json2html(data: Dict) -> str:
    """JSON 데이터를 HTML로 변환"""
    html_parts = []
    
    # 테이블 컨테이너 시작 (상품명 섹션 제거)
    html_parts.append('<div class="info-section">')
    html_parts.append('<table class="info-table">')
    html_parts.append('<tbody>')
    
    # 각 행 처리
    for key in sorted(data.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        if key != '상품명' and key != '출발월':  # 상품명은 처리하지 않음
            cells = data[key].split('||')
            
            # 첫 번째 셀이 비어있는지 확인하여 클래스 추가
            is_first_empty = not cells[0].strip()
            tr_class = ' class="empty-first"' if is_first_empty else ''
            html_parts.append(f'<tr{tr_class}>')
            
            i = 0
            while i < len(cells):
                # 현재 셀이 비어있고 첫 번째 셀이 아니면 건너뛰기
                if i > 0 and not cells[i].strip():
                    i += 1
                    continue
                
                # 현재 셀 다음부터 연속된 빈 셀 개수 세기
                empty_count = 0
                next_pos = i + 1
                while next_pos < len(cells) and not cells[next_pos].strip():
                    empty_count += 1
                    next_pos += 1

                # 첫 번째 셀은 특별한 스타일 적용
                if i == 0:
                    html_parts.append(f'<td class="first-cell"' + (f' colspan="{empty_count + 1}"' if empty_count > 0 else '') + f'>{cells[i]}</td>')
                else:  # 값이 있는 셀
                    html_parts.append(f'<td class="data-cell"' + (f' colspan="{empty_count + 1}"' if empty_count > 0 else '') + f'>{cells[i]}</td>')
                
                # 다음 위치로 이동 (빈 셀은 건너뛰기)
                i = next_pos if empty_count > 0 else i + 1
                    
            html_parts.append('</tr>')

    html_parts.append('</tbody>')
    html_parts.append('</table>')
    html_parts.append('</div>')
    
    # 스타일 추가
    html_parts.insert(0, '''
    <style>
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
    </style>
    ''')
    
    return '\n'.join(html_parts)

def create_html(df: pd.DataFrame) -> Tuple[Dict, str]:
    """엑셀 데이터를 HTML로 변환하는 메인 함수"""
    # 엑셀 데이터를 JSON으로 변환
    json_data = head2json(df)
    
    # 상품명 섹션 HTML 생성
    title_html = ''
    if '상품명' in json_data:
        title_html = f'''
        <div class="title-section">
            <h1>{json_data['상품명']}</h1>
        </div>
        '''
    
    # JSON을 HTML로 변환 (테이블 부분)
    table_html = json2html(json_data)
    
    # 전체 HTML 조합
    html_content = title_html + table_html
    
    return json_data, html_content