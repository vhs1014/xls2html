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
        if key != '상품명':  # 상품명은 처리하지 않음
            cells = data[key].split('||')
            non_empty_cells = [cell for cell in cells if cell.strip()]
            
            # 한 줄에 한 칸만 있는 경우
            if len(non_empty_cells) == 1:
                # 값이 있는 셀의 위치 찾기
                value_index = next(i for i, cell in enumerate(cells) if cell.strip())
                
                html_parts.append('<tr class="single-cell-row">')
                # 값이 있는 셀 이전의 빈 셀들
                for _ in range(value_index):
                    html_parts.append('<td></td>')
                # 값이 있는 셀과 나머지 빈 셀들을 colspan으로 처리
                remaining_cells = len(cells) - value_index
                if remaining_cells > 1:
                    html_parts.append(f'<td colspan="{remaining_cells}">{non_empty_cells[0]}</td>')
                else:
                    html_parts.append(f'<td>{non_empty_cells[0]}</td>')
                html_parts.append('</tr>')
            else:
                html_parts.append('<tr>')
                i = 0
                while i < len(cells):
                    if not cells[i].strip():
                        # 빈 셀은 그대로 출력
                        html_parts.append('<td></td>')
                        i += 1
                    else:
                        # 현재 셀에 값이 있는 경우, 오른쪽의 빈 셀만 확인
                        colspan = 1
                        next_pos = i + 1
                        while next_pos < len(cells) and not cells[next_pos].strip():
                            colspan += 1
                            next_pos += 1
                        
                        if colspan > 1:
                            html_parts.append(f'<td colspan="{colspan}">{cells[i]}</td>')
                            i = next_pos
                        else:
                            html_parts.append(f'<td>{cells[i]}</td>')
                            i += 1
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
        
        /* 첫 번째 셀 기본 스타일 */
        .info-table td:first-child {
            background-color: #f8f9fa;
            font-weight: 700;
        }
        
        /* colspan이 있는 첫번째 셀 스타일 */
        .info-table td:first-child[colspan] {
            background-color: transparent;
            font-weight: 400;
        }

        /* 행 테두리 기본 스타일 */
        .info-table tr {
            border-top: 1px solid #ccc;
        }

        /* 첫 번째 셀이 비어있는 행의 모든 테두리 제거 */
        .info-table tr:has(td:first-child:empty) {
            border-top: none;
            border-bottom: none;
        }

        /* single-cell-row가 연속될 때의 테두리 처리 */
        .info-table tr.single-cell-row:has(+ tr.single-cell-row),
        .info-table tr.single-cell-row + tr.single-cell-row {
            border-top: none;
            border-bottom: none;
        }


        /* 테이블의 마지막 행은 항상 하단 테두리 표시 */
        .info-table tr:last-child {
            border-bottom: 1px solid #ccc !important;
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