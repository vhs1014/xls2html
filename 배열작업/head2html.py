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

# def create_html(df: pd.DataFrame) -> Tuple[str, Dict[str, str]]:
#     # 초기화
#     subData = dict()
#     subData['상품명'] = ''
    
#     # # HTML 시작 부분
#     # html_content = """
#     #     <div class="container">
#     # """
    
#     before_content = ''
#     before_title = ""
#     title_chk = False
#     print(df)
#     # 데이터 처리 및 HTML 컨텐츠 생성
#     for i in range(df.shape[0]):
#         row = df.iloc[i]
#         non_empty = [x for x in row if not pd.isna(x)]
#         tmpTitle = non_empty[0] if len(non_empty) == 1 else ''
#         print(row)
#         if not title_chk and tmpTitle:
#             subData['상품명'] = tmpTitle
#             title_chk = True
#             continue
        
#         # 빈 셀 제거하고 데이터 포맷팅
#         row_data = [format_cell(x) for x in row if str(x).strip() != ''] 
        
#         if not row_data:
#             continue
            
#         # 첫 번째 열은 제목으로, 나머지는 내용으로 처리
#         title = row_data[0].strip()
#         content = '||'.join(x for x in row_data[1:]) if len(row_data) > 1 else ''
        
        
#         # 내용이 있는 경우
#         if content.replace('||', ''):
#             # 제목이 일정 타이틀인 경우
#             if not subData['상품명'] and ('일' in title or '박' in title):
#                 subData['상품명'] = title
#             elif title.replace(' ', '') == '상품명':
#                 subData['상품명'] = content
#             else:
#                 short_title = title.replace(' ', '').replace('\xa0', '')
#                 # 제목이 있고 내용이 있는 경우
#                 if short_title:
#                     if short_title in subData:
#                         subData[short_title] = subData[short_title] + '\r\n' + '||' + content  # 거의 발생안함..    같은 제목의 내용이 떨어져 있는경우
#                     else:
#                         subData[short_title] = content
#                     before_title = short_title
#                     before_content = content
#                 # 제목 없이 내용만 있는 경우 이전 내용에 추가
#                 elif before_title:
#                     if before_title in subData:
#                         # subData[before_title] = subData[before_title] + '\r\n' + '||' + content
#                         subData[before_title] = subData[before_title] + '\r\n'  + content
#                     else:
#                         subData[before_title] = content
#                     before_content = content 
#         # 내용이 없는 경우
#         else:
#             # if "REMARK" not in subData:
#             #     subData["REMARK"] = title
#             # else:
#             #     subData["REMARK"] = subData["REMARK"] + '\r\n' + '||' + title
#             subData[title] = ''
            
#     return subData

def create_html(df: pd.DataFrame) -> Dict:
    # 초기화
    result = {}
    current_key = None
    
    # 상품명 찾기 - 첫 번째로 나오는 한 줄에 한 칸만 값이 있는 데이터
    for i in range(df.shape[0]):
        row = df.iloc[i]
        # 데이터 포맷팅
        row_data = [format_cell(x) for x in row]
        # 빈 값이 아닌 셀 찾기
        non_empty_cells = [x for x in row_data if str(x).strip()]
        
        # 한 줄에 한 칸만 값이 있는 경우
        if len(non_empty_cells) == 1:
            result['상품명'] = [non_empty_cells[0]]
            break
    
    # 데이터 처리
    for i in range(df.shape[0]):
        row = df.iloc[i]
        # 데이터 포맷팅
        row_data = [format_cell(x) for x in row]
        
        # 빈 행 스킵
        if all(not str(x).strip() for x in row_data):
            continue
        
        # 첫 번째 셀과 나머지 셀들 분리
        first_cell = str(row_data[0]).strip()
        remaining_cells = [str(x).strip() for x in row_data[1:] if str(x).strip()]
        
        # 첫 번째 셀이 비어있는 경우
        if not first_cell and current_key and remaining_cells:
            # 이전 키의 값 배열에 추가
            if isinstance(result[current_key], list):
                result[current_key].append('||'.join(remaining_cells))
        else:
            # 새로운 키 생성
            if first_cell and remaining_cells:
                current_key = first_cell
                if current_key not in result:
                    result[current_key] = []
                result[current_key].append('||'.join(remaining_cells))
    
    return result