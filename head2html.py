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

def get_night_days(title):
    night = int(re.findall(r'(\d+)박', title)[0]) if '박' in title else None
    days = int(re.findall(r'(\d+)일', title)[0]) if '일' in title else None
    
    if night and days:
        return night, days
    elif night:
        return night, night + 1
    elif days:
        return days - 1, days
    return None, None

def create_html(df: pd.DataFrame) -> Tuple[str, Dict]:
    subData = {}
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
        row_data = [format_cell(x) for x in row if str(x).strip() != '']
        
        if row_data:
            title = row_data[0].strip()
            content = ' | '.join(x for x in row_data[1:] if x.strip()).strip() if len(row_data) > 1 else ''.strip()
            
            if content.replace(' ', '').replace('|', '') != '':
                if title:
                    html_content += f"""
                    <div class="content-card">
                        <div class="content-title">{title}</div>
                        <div class="content-body">{content}</div>
                    </div>
                    """
                    short_title = title.replace(' ', '').replace('\xa0', '')
                    if title in ["상품가격", "상품가", "가격"]:
                        subData['price'] = content
                    else:
                        subData[short_title] = content
                    title_chk = True
                    before_content = content
                    before_title = short_title
                else:
                    html_content = html_content.replace(before_content, before_content + '<br>' + content)
                    subData[before_title] = subData[before_title] + '\r\n' + content
                    before_content = content
            else:          # content가 없는 경우
                if i == 0:
                    subData['title'] = title
                    subData['nights'], subData['days'] = get_night_days(title)
                    
                    html_content += f"""
                    <div class="container">
                        <div class="header">{title}</div>
                    </div>
                    """
                else:  # 첫번째 상품명이 아닌경우 
                    if title_chk:
                        html_content = html_content.replace(before_content, before_content + '<br>' + title)
                    else:
                        html_content += f"""
                        <div style="background-color: #248fd63d; padding: 10px 0 10px 20px; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08)">{title}</div>
                        """
    
    html_content += """
        </div>
    </body>
    </html>
    """
    
    return html_content, subData
