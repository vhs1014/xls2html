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

# def get_night_days(title):
#     night = int(re.findall(r'(\d+)박', title)[0]) if '박' in title else None
#     days = int(re.findall(r'(\d+)일', title)[0]) if '일' in title else None
    
#     if night and days:
#         return night, days
#     elif night:
#         return night, night + 1
#     elif days:
#         return days - 1, days
#     return None, None
def create_html(df: pd.DataFrame) -> Tuple[str, Dict[str, str]]:
    # 초기화
    subData = dict()
    subData['title'] = ''
    
    # HTML 시작 부분
    html_content = """
        <div class="container">
    """
    
    before_content = ""
    before_title = ""
    title_chk = False
    
    # 데이터 처리 및 HTML 컨텐츠 생성
    for i in range(df.shape[0]):
        row = df.iloc[i]
        # 빈 셀 제거하고 데이터 포맷팅
        # row_data = [format_cell(x) for x in row if pd.notna(x) and str(x).strip()]
        row_data = [format_cell(x) for x in row if str(x).strip() != ''] 
        
        if not row_data:
            continue
            
        # 첫 번째 열은 제목으로, 나머지는 내용으로 처리
        title = row_data[0].strip()
        content = ' | '.join(x.strip() for x in row_data[1:] if x.strip()) if len(row_data) > 1 else ''
        
        # 내용이 있는 경우
        if content.replace(' ', '').replace('|', ''):
            if title:
                # 제목이 일정 타이틀인 경우
                if not subData['title'] and ('일' in title or '박' in title):
                    subData['title'] = title
                elif title.replace(' ', '') == '상품명':
                    subData['title'] = content
                else:
                    short_title = title.replace(' ', '').replace('\xa0', '')
                    # 가격 정보인 경우 특별 처리
                    if any(price_title in title for price_title in ["상품가격", "상품가", "가격"]):
                        subData['price'] = content
                    else:
                        subData[short_title] = content
                    title_chk = True
                    before_content = content
                    before_title = short_title
            else:
                # 제목 없이 내용만 있는 경우 이전 내용에 추가
                if before_content and before_title:
                    if subData.get(before_title):
                        subData[before_title] = subData.get(before_title) + '\r\n' + content
                    else:
                        subData[before_title] = content                        
                    # subData[before_title] = subData[before_title] + '\r\n' + content
                    before_content = content
        # 내용이 없는 경우
        else:
            # 첫 번째 일정 타이틀인 경우
            if not subData['title'] and ('일' in title or '박' in title):
                subData['title'] = title
    
    return  subData