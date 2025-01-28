from s3_uploader import S3FileUploader
from fastapi import FastAPI, HTTPException, UploadFile, File, Body
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import pandas as pd
from bs4 import BeautifulSoup

from datetime import datetime
from dateutil.relativedelta import relativedelta

import datetime
import unicodedata

from io import BytesIO
import httpx 
from collections import Counter
from pathlib import Path
from typing import Optional, List
from urllib.parse import quote
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pydantic import BaseModel, EmailStr
import re
import tempfile
import os
import subprocess
from typing import List, Dict


from head2html import create_html 
from head2html_cellMerge import create_html_merge                                 # 이후 삭제 예정 (셀병합을 위한 임시)
from extract_words import extract_sorted_unique_words
import itn2html
from itn2html import ItineraryHtmlGenerator


app = FastAPI()

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 운영환경에서는 구체적인 도메인을 지정하는 것이 좋습니다
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# class DataFrameInput(BaseModel):
#     # DataFrame을 JSON 형식으로 받기 위한 Pydantic 모델
#     columns: List[str]
#     data: List[List]

# class ProcessedResult(BaseModel):
#     # 처리된 결과를 반환하기 위한 Pydantic 모델
#     summary: Dict
#     processed_data: List[Dict]
class TableData(BaseModel):
    tableData: List[List[str]]
     
uploader = S3FileUploader()
# 정적 파일 경로를 /itinerary/static으로 설정
app.mount("/itinerary/static", StaticFiles(directory="static"), name="static")
# templates 디렉토리 경로 설정
TEMPLATES_DIR = Path("templates")

# Email configuration
SMTP_SERVER = "smtp.kakaowork.com"
SMTP_PORT = 465
SMTP_USERNAME = "support@tripbox.co.kr"
SMTP_PASSWORD = "trb082603*trb082603*"


class EmailRequest(BaseModel):
    recipients: List[EmailStr]
    subject: str
    body: str

# 멀티라인 줄 분리
async def  split_multiline_rows(df: pd.DataFrame) -> pd.DataFrame:
    new_rows = []
    # 각 행을 순회하면서 처리
    for idx, row in df.iterrows():
        # 각 컬럼의 값을 확인
        has_multiline = False
        split_contents = {}
        max_lines = 1
        multiline_cols = set()  # 줄바꿈이 있는 컬럼들을 저장
        
        # 각 컬럼의 내용을 확인하고 줄바꿈이 있는지 체크
        for col in df.columns:
            if isinstance(row[col], str):
                lines = row[col].split('<br/>')
                if len(lines) > 1:
                    has_multiline = True
                    multiline_cols.add(col)  # 줄바꿈이 있는 컬럼 기록
                    split_contents[col] = [line.strip() if line.strip() else '' for line in lines]
                    max_lines = max(max_lines, len(lines))
                else:
                    split_contents[col] = [row[col]] + [''] * (max_lines - 1)
            else:
                split_contents[col] = [row[col]] + [''] * (max_lines - 1)
        
        # 멀티라인이 없는 경우 원래 행을 그대로 추가
        if not has_multiline:
            new_rows.append(row.to_dict())
        else:
            # 멀티라인이 있는 경우 분리하여 새로운 행 생성
            for line_idx in range(max_lines):
                new_row = {}
                for col in df.columns:
                    if line_idx == 0:  # 첫 번째 행은 모든 컬럼의 값을 유지
                        new_row[col] = split_contents[col][0]
                    else:  # 그 이후 행에서는 줄바꿈이 있는 컬럼만 값을 유지
                        if col in multiline_cols:
                            try:
                                new_row[col] = split_contents[col][line_idx]
                            except IndexError:
                                new_row[col] = ''
                        else:
                            new_row[col] = ''
                new_rows.append(new_row)

    # 새로운 데이터프레임 생성
    result_df = pd.DataFrame(new_rows)
    return result_df

async def itn_search(df: pd.DataFrame) -> pd.DataFrame:
    # 컬럼 매핑 정의
    column_aliases = {
        'date': ['일자', '날짜', '순번', '일시', 'DATE', 'Day', 'No', '월/일', '일차' ],
        'place': ['지역', '장소', 'place', 'CITY', '도시', '여행지', '행선지', '방문도시', '방문장소'],
        'transport': ['교통편', '이동수단', '교통', 'TRANS', 'Transport', '구분'],
        'time': ['시간', 'time'],
        'itinerary': ['주요일정', '일정', '관광지', 'itinerary', '여정', '세부내용', '세부일정', '주요내용', '주요관광지', 'SCHEDULE', '행사일정'],
        'meal': ['식사', 'meal', 'meals']
    }
    
    # 특정 단어가 한 줄에 3개 이상 나오는 줄을 찾고, 해당 줄 위에 모든 데이터를 삭제
    idy = -1
    for idx, row in df.iterrows():
        # 각 셀의 값에서 모든 빈칸을 지워줍니다.
        # cleaned_row = [str(cell).replace(' ', '').replace('\xa0', '').replace('\n', '').lower() for cell in row]
        cleaned_row = [str(cell).strip() if pd.notna(cell) else '' for cell in row]
        # 각 셀이 어떤 카테고리에 속하는지 확인
        cells_with_matches = 0  # 매칭된 셀의 수를 카운트
        
        for cell in cleaned_row:
            has_match = False  # 현재 셀이 매칭되었는지 여부
            # cell이 비어있거나 None이면 건너뛰기
            if not cell:
                continue
                
            for category, aliases in column_aliases.items():
                if any(alias.lower() in cell.lower().replace(' ', '').replace('\xa0', '').replace('\n', '').strip() for alias in aliases):
                    has_match = True
                    break
            if has_match:
                cells_with_matches += 1
                    
        if cells_with_matches >= 3:
            idy = idx
            break
    
    if idy == -1: idy = len(df)            
    head_df = df.iloc[:idy]  # 헤더 부분
    itn_df = df.iloc[idy:]   # 일정 부분
    
    # head_df 처리
    # head_df = head_df.loc[:, (head_df != '').any()]  # 모든 값이 빈 문자열인 열 제거
    # head_df = head_df.loc[(head_df != '').any(axis=1)]  # 모든 값이 빈 문자열인 행 제거

    # itn_df 처리
    # itn_df = itn_df.loc[:, (itn_df != '').any()]     # 모든 값이 빈 문자열인 열 제거
    # itn_df = itn_df.loc[(itn_df != '').any(axis=1)]  # 모든 값이 빈 문자열인 행 제거

    # head, itn 각각 빈줄, 빈칸 제거
    # head_df = head_df.dropna(axis=1, how='all')   
    # head_df = head_df.dropna(axis=0, how='all') 
    
    # itn_df = itn_df.dropna(axis=1, how='all')   
    # itn_df = itn_df.dropna(axis=0, how='all')


    head_df.columns = range(len(head_df.columns))  
    itn_df.columns = range(len(itn_df.columns))      

    return head_df, itn_df, column_aliases
    
async def read_excel_from_upload(file: UploadFile) -> pd.DataFrame:
    """업로드된 엑셀 파일을 DataFrame으로 읽기"""
    try:
        contents = await file.read()
        excel_data = BytesIO(contents)
        
        # 파일 확장자 확인
        file_ext = file.filename.split('.')[-1].lower()
        
        try:
            if file_ext == 'xlsx':
                df = pd.read_excel(excel_data, header=None, engine='openpyxl')
            elif file_ext == 'xls':
                # xls를 xlsx로 변환
                xlsx_contents = convert_xls_to_xlsx(contents)
                excel_data = BytesIO(xlsx_contents)
                df = pd.read_excel(excel_data, header=None, engine='openpyxl')
            else:
                raise HTTPException(status_code=400, detail="지원하지 않는 파일 형식입니다. .xlsx 또는 .xls 파일만 업로드해주세요.")
        except Exception as e:
            if "xlrd" in str(e):
                raise HTTPException(status_code=400, detail="xls 파일 읽기에 실패했습니다. 파일이 손상되었거나 올바른 Excel 파일이 아닐 수 있습니다.")
            raise e
        
        head_df, itn_df, column_aliases = await itn_search(df)
        return head_df, itn_df, column_aliases
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"엑셀 파일 읽기 실패: {str(e)}")

async def read_excel_from_url(url: str) -> pd.DataFrame:
    """URL에서 직접 엑셀 파일을 DataFrame으로 읽기"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            
            # 바이트 데이터를 BytesIO 객체로 변환
            excel_data = BytesIO(response.content)
            
            # BytesIO에서 직접 DataFrame으로 읽기
            try:
                # .xlsx 파일 시도
                df = pd.read_excel(excel_data, header=None, engine='openpyxl')
            except Exception:
                # .xls 파일 시도
                excel_data.seek(0)  # BytesIO 포인터를 처음으로 되돌림
                df = pd.read_excel(excel_data, header=None, engine='xlrd')
            
            head_df, itn_df, column_aliases = await itn_search(df)
            return head_df, itn_df, column_aliases
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"엑셀 파일 읽기 실패: {str(e)}")



async def convert_df_to_json(df: pd.DataFrame, column_aliases) -> str:
    """
    여행 일정이 담긴 DataFrame을 JSON 형식으로 변환하는 함수
    
    Args:
        df (pd.DataFrame): 일정 데이터가 담긴 DataFrame
    
    Returns:
        str: JSON 문자열로 변환된 여행 일정 데이터
    """

    def clean_text(text):
        """특수 문자와 공백을 정리하는 함수"""
        if pd.isna(text):
            return ""
        text = str(text)
        text = unicodedata.normalize('NFKC', text)
        text = str(text).replace('\xa0', ' ')
        text = ' '.join(text.split())
        return text
    def identify_column_types(row):
        """첫 번째 행을 기반으로 각 컬럼의 타입을 식별"""
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
    first_row = [clean_text(r).replace(' ', '').lower()  for r in first_row]
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
        # 시간 형식을 체크하는 정규식 패턴
        time_pattern = re.compile(r'^\d{1,2}:\d{2}$')
        
        # 시간 형식에 맞는 값만 필터링
        time_values = [str(val).strip() for val in df[time_col].dropna() 
                      if isinstance(val, (str, int, float)) and 
                      time_pattern.match(str(val).strip())]
        
        if time_values:
            depTime = time_values[0]
            arrTime = time_values[-1]


     # DataFrame 처리 시작
    df = df.iloc[1:]  # 첫 번째 행(헤더) 제외
    locations = set()
    places = set()
    itinerary = []
    location_name = ''
    current_day = None
    current_location = None
    day_data = None

    def is_day_header(text):
        """날짜 헤더인지 확인하는 함수"""
        text = clean_text(text).replace(' ', '')
        # 날짜 패턴 정의
        day_patterns = [
            r'(?i)d\.d',  # '숫자+일'이 포함된 모든 경우
            r'\d+일',  # '숫자+일'이 포함된 모든 경우
            r'(?i)day\d+',  # 'Day숫자', 'day숫자', 'DAY숫자' 등 대소문자 구분 없이
            r'(?i)\d+day',  # '숫자Day', '숫자day', '숫자DAY' 등 대소문자 구분 없이
            r'\d{2}-\d{2}\(\w+\)',  # mm-dd(요일)
            r'\d{2}-\d{2}',  # mm-dd
            r'\d{2}-\d{2}-\d{2}\(\w+\)',  # yy-mm-dd(요일)
            r'\d{2}-\d{2}-\d{2}',  # yy-mm-dd
            r'\d{2}/\d{2}',  # mm/dd
            r'\d{2}/\d{2}/\d{2}',  # yy/mm/dd
        ]
        return any(re.search(pattern, text) for pattern in day_patterns)

    last_valid_place = None  # 마지막으로 유효한 place를 저장
    current_flight = None
    previous_was_day_header = False  # 이전 row가 일자 헤더였는지 추적
    for idx, row in df.iterrows():
        # 일자 처리
        if date_col == 0 and pd.notna(row[date_col]) and is_day_header(str(row[date_col])):
            # 이전 row가 일자 헤더였다면 스킵
            if previous_was_day_header:
                previous_was_day_header = True
                continue
                
            # 이전 day_data가 있으면 현재 location을 추가하고 itinerary에 추가
            if day_data is not None and current_location is not None:
                if current_location["schedule"]:  # schedule이 있는 경우만 추가
                    if day_data is not None:
                        day_data['locations'].append(current_location)
                itinerary.append(day_data)
                
            day_str = clean_text(row[date_col])
            
            day_data = {
                "day": day_str,
                "locations": [],
                "meals": []
            }
            
            # 새로운 날짜에서 이전 location_name이 있으면 새로운 current_location 생성
            if location_name:
                current_location = {
                    "place": location_name,
                    "schedule": []
                }
            
        if date_col is not None and pd.isna(row[date_col]) and day_data is None:
            continue
            
        # 장소 처리
        if place_col is not None and pd.notna(row[place_col]):
            new_location_name = clean_text(row[place_col])
            if new_location_name:  # 새 장소가 빈 값이 아닌 경우
                # 이전 location이 있고 schedule이 있으면 추가
                if day_data is not None and current_location is not None and current_location["schedule"]:
                    day_data['locations'].append(current_location)
                
                location_name = new_location_name
                current_location = {
                    "place": location_name,
                    "schedule": []
                }
                locations.add(location_name)
                last_valid_place = location_name
        elif transport_col is not None and pd.notna(row[transport_col]) and current_location is not None:
            # place가 nan이고 flight가 있는 경우, 다음 schedule 항목을 위해 저장
            current_flight = clean_text(row[transport_col])
        
        # 일정 처리
        if current_location is not None and itinerary_col is not None and pd.notna(row[itinerary_col]):
            schedule_item = {}
            
            # 이전에 저장된 flight 정보가 있으면 추가
            if current_flight:
                schedule_item['flight'] = current_flight
                current_flight = None
            elif transport_col is not None and pd.notna(row[transport_col]):
                schedule_item['flight'] = clean_text(row[transport_col])
            
            if time_col is not None and pd.notna(row[time_col]):
                time_value = row[time_col]
                if isinstance(time_value, (datetime.time, datetime.datetime)):
                    time_value = time_value.strftime('%H:%M')
                else:
                    time_value = clean_text(time_value)
                schedule_item['time'] = time_value
            
            activity_text = clean_text(row[itinerary_col])
            if activity_text:  # 빈 문자열이 아닌 경우에만 추가
                # 새로운 schedule_item이면 details 배열 초기화
                if 'details' not in schedule_item:
                    schedule_item['details'] = []
                schedule_item['details'].append(activity_text)
                places.add(activity_text)
                
                # schedule_item에 내용이 있으면 추가
                if len(schedule_item['details']) > 0 or 'flight' in schedule_item:
                    current_location['schedule'].append(schedule_item)
        
        # 식사 정보 처리
        if meal_col is not None and pd.notna(row[meal_col]) and day_data is not None:
            meals = clean_text(row[meal_col]).split('\n')
            day_data['meals'].extend(meals)
            # meal_dict = {}
            # for meal in meals:
            #     meal = meal.strip()
            #     if meal.startswith('조식'):
            #         meal_dict['breakfast'] = meal.replace('조식', '').replace(':', '').strip()
            #     elif meal.startswith('중식'):
            #         meal_dict['lunch'] = meal.replace('중식', '').replace(':', '').strip()
            #     elif meal.startswith('석식'):
            #         meal_dict['dinner'] = meal.replace('석식', '').replace(':', '').strip()
            # if meal_dict:
            #     day_data['meals'].update(meal_dict)

        # 이전 row가 일자 헤더였는지 기록
        previous_was_day_header = date_col == 0 and pd.notna(row[date_col]) and is_day_header(str(row[date_col]))

    # 마지막 day_data 처리
    if day_data is not None and current_location is not None:
        if current_location["schedule"]:  # schedule이 있는 경우만 추가
            if day_data is not None:
                day_data['locations'].append(current_location)
        itinerary.append(day_data)

    return itinerary, locations, places, depTime, arrTime


def convert_xls_to_xlsx(xls_contents):
    """xls 파일을 xlsx로 변환"""
    # 임시 파일 생성
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xls') as temp_xls:
        temp_xls.write(xls_contents)
        temp_xls_path = temp_xls.name
    
    temp_xlsx_path = temp_xlsx_path.replace('.xls', '.xlsx')
    
    try:
        # ssconvert를 사용하여 변환
        subprocess.run(['ssconvert', temp_xls_path, temp_xlsx_path], check=True)
        
        # xlsx 파일 읽기
        with open(temp_xlsx_path, 'rb') as f:
            xlsx_contents = f.read()
        
        # 임시 파일 삭제
        os.unlink(temp_xls_path)
        os.unlink(temp_xlsx_path)
        
        return xlsx_contents
    except Exception as e:
        if os.path.exists(temp_xls_path):
            os.unlink(temp_xls_path)
        if os.path.exists(temp_xlsx_path):
            os.unlink(temp_xlsx_path)
        raise e

# =========================================================================================================================

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

@app.get("/itinerary/health")
async def health():
    return 'ok'

# =====================================================================================
# 엑셀 파일 업로드 및 S3 저장
# =====================================================================================

@app.get("/itinerary/url/")
async def convert_excel_to_html(excel_url: str):
    try:
        # URL에서 직접 DataFrame으로 읽기
        head_df, itn_df ,column_aliases = await read_excel_from_url(excel_url)

        itn_df = await split_multiline_rows(itn_df)
        subData = {}
        # subData['itinerary'], locations, places , deptime, arrtime = await convert_df_to_json(itn_df, column_aliases)
        # subData['file_url'] = result['file_url']
        # final_html = itn2html.generate_itinerary_html(subData)
        
        # 헤더 데이터 처리
        headjson, head_html = create_html(head_df)
        
        # 일정 데이터 처리
        subData['itinerary'], locations, places , deptime, arrtime = await convert_df_to_json(itn_df, column_aliases)
        # subData['file_url'] = result['file_url']
        
        # ItineraryHtmlGenerator를 사용하여 HTML 생성
        generator = ItineraryHtmlGenerator(subData)
        itinerary_html = generator.generate_html()  # 일정 HTML 생성 (상품명 제외)
        
        # 최종 HTML 생성
        with open('./templates/template.html', 'r', encoding='utf-8') as f:
            template = f.read()
        final_html = template.replace('{{content}}', head_html + itinerary_html)
        
        # 추가 정보 업데이트
        subData['출발시간'] = deptime
        subData['도착시간'] = arrtime
        subData['locations'] = ','.join(locations).replace(' ', '')
        subData['places'] = extract_sorted_unique_words(','.join(places))
        subData.update(headjson)
        
        return JSONResponse(content={
            'status': 'success',
            'html': final_html,
            'subData': subData,
            # 'file_url': result['file_url'],
        })
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"변환 실패: {str(e)}")

@app.get("/itinerary/s3select/")
async def read_root():
    """업로드 폼을 보여주는 HTML 페이지 반환"""
    try:
        html_content = (TEMPLATES_DIR / "s3upload.html").read_text(encoding="utf-8")
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"HTML 파일 로드 실패: {str(e)}")


#  itn_id 가 있으면 기존 일정표 수정, 없으면 새로운 일정표 생성
@app.post("/itinerary/saveupload/")
async def convert_excel_to_html(
    file: UploadFile = File(...),
    user_id: Optional[int] = None,
    itn_id: Optional[int] = None,
    file_url: Optional[str] = None
):
    try:
        # 초기 검증
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="엑셀 파일만 업로드 가능합니다.")
        
        # 엑셀 파일 처리
        head_df, itn_df, column_aliases = await read_excel_from_upload(file)
        
        # 파일 업로드 처리
        try:
            if itn_id and file_url:
                result = uploader.update_file(file.file, file.filename, file_url)
            else:
                result = uploader.upload_file(file.file, file.filename)
                
            if not result:
                raise Exception("파일 업로드/업데이트 실패")
                
        except Exception as e:
            raise Exception(f"파일 처리 실패: {str(e)}")
        
        # 데이터 처리
        itn_df = await split_multiline_rows(itn_df)
        subData = {}
        
        # 헤더 데이터 처리
        headjson, head_html = create_html(head_df)
        
        # 일정 데이터 처리
        subData['itinerary'], locations, places , deptime, arrtime = await convert_df_to_json(itn_df, column_aliases)
        # subData['file_url'] = result['file_url']
        
        # ItineraryHtmlGenerator를 사용하여 HTML 생성
        generator = ItineraryHtmlGenerator(subData)
        itinerary_html = generator.generate_html()  # 일정 HTML 생성 (상품명 제외)
        
        # 최종 HTML 생성
        with open('./templates/template.html', 'r', encoding='utf-8') as f:
            template = f.read()
        final_html = template.replace('{{content}}', head_html + itinerary_html)
        
        # 추가 정보 업데이트
        subData['출발시간'] = deptime
        subData['도착시간'] = arrtime
        subData['locations'] = ','.join(locations).replace(' ', '')
        subData['places'] = extract_sorted_unique_words(','.join(places))
        subData.update(headjson)
        
        return JSONResponse(content={
            'status': 'success',
            'html': final_html,
            'subData': subData,
            'file_url': result['file_url'],
        })
            
    except Exception as e:
        return JSONResponse(
            content={'error': str(e)}, 
            status_code=400
        )

# @app.post("/itinerary/df/", response_model=ProcessedResult)
# async def convert_df_to_html(df_input: DataFrameInput):

@app.post("/itinerary/df/")
async def convert_df_to_html(data: TableData):
    df = pd.DataFrame(data.tableData)
    head_df, itn_df, column_aliases = await itn_search(df)
    # head_df 에서는 출발월 을        1월||2월||3월
    # itn_df 에서는 출도착 시간을     12:00||13:00 

    itn_df = await split_multiline_rows(itn_df)
    subData = {}
    
    # 헤더 데이터 처리
    headjson, head_html = create_html(head_df)
    
    # 일정 데이터 처리
    subData['itinerary'], locations, places , deptime, arrtime = await convert_df_to_json(itn_df, column_aliases)
    # ItineraryHtmlGenerator를 사용하여 HTML 생성
    generator = ItineraryHtmlGenerator(subData)
    itinerary_html = generator.generate_html()  # 일정 HTML 생성 (상품명 제외)
    
    # 최종 HTML 생성
    with open('./templates/template.html', 'r', encoding='utf-8') as f:
        template = f.read()
    final_html = template.replace('{{content}}', head_html + itinerary_html)
    
    # 추가 정보 업데이트
    subData['locations'] = ','.join(locations).replace(' ', '')
    subData['places'] = extract_sorted_unique_words(','.join(places))
    subData['출발시간'] = deptime
    subData['도착시간'] = arrtime
    subData.update(headjson)
    
    return JSONResponse(content={
        'status': 'success',
        'html': final_html,
        'subData': subData,
        # 'file_url': result['file_url'],  # result가 정의된 경우에만 사용
    })

@app.post("/itinerary/df_cellMerge")
async def table_to_html(data: str = Body(...)):  
    # 특수 공백 문자 제거
    data = data.replace('\u3000', ' ')  # 전각 공백
    data = data.replace('\xa0', ' ')    # HTML &nbsp;
    data = data.replace('\u2003', ' ')  # Em 공백
    data = data.replace('\u2002', ' ')  # En 공백
    data = data.replace('\u2000', ' ')  # 1/2-Em 공백
    data = data.replace('\u2001', ' ')  # 1-Em 공백
    data = ' '.join(data.split())       # 연속된 공백을 하나로 통일
    
    # BeautifulSoup으로 파싱
    soup = BeautifulSoup(data, 'html.parser')
    table = soup.find('table')
    
    if not table:
        raise ValueError("HTML 테이블을 찾을 수 없습니다.")

    # 빈 행 제거
    rows = table.find_all('tr')
    for row in rows:
        # 행의 모든 셀이 비어있는지 확인
        cells = row.find_all(['td', 'th'])
        is_empty_row = all(not cell.get_text(strip=True) for cell in cells)
        if is_empty_row:
            row.decompose()

    # 1. 테이블의 모든 셀의 colspan과 rowspan을 저장
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
    
    # 먼저 텍스트만으로 DataFrame을 만들어서 헤더 위치 찾기
    df_data = []
    for row in table.find_all('tr'):
        row_data = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
        df_data.append(row_data)
    temp_df = pd.DataFrame(df_data)
    
    # 헤더 위치 찾기
    # head_df, itn_df, column_aliases = await itn_search(temp_df)
    # header_end_idx = len(head_df)
    
    # 다시 처음부터 DataFrame 만들기 (헤더는 HTML, 나머지는 텍스트)
    # df_data = []
    # for idx, row in enumerate(table.find_all('tr')):
    #     row_data = []
    #     for cell in row.find_all(['td', 'th']):
    #         if idx < header_end_idx:
    #             # 헤더 부분은 HTML 추출
    #             cell_content = ''.join(str(content) for content in cell.contents)
    #         else:
    #             # 일정 부분은 텍스트만 추출
    #             cell_content = cell.get_text(strip=True)
    #         row_data.append(cell_content)
    #     df_data.append(row_data)
    # df = pd.DataFrame(df_data)
    def clean_word_tags(text):
        """Word 문서 태그 제거"""
        if not isinstance(text, str):
            return text
        # Word 조건부 서식 태그 제거
        text = re.sub(r'\[if[^\]]*\]|\[endif\]', '', text)
        # Office XML 태그 제거
        text = re.sub(r'<o:[^>]*>|</o:[^>]*>', '', text)
        # 일반적인 빈 XML 태그 제거
        text = re.sub(r'<[^>]*></[^>]*>', '', text)
        # 연속된 공백을 하나로
        text = ' '.join(text.split())
        return text.strip()

    df_data = []
    for idx, row in enumerate(table.find_all('tr')):
        row_data = []
        for cell in row.find_all(['td', 'th']):
            cell_content = ''.join(str(content) for content in cell.contents)
            row_data.append(clean_word_tags(cell_content))  # Word 조건부 서식 태그 제거cell_content)
        df_data.append(row_data)
    df = pd.DataFrame(df_data)
    
    head_df, itn_df, column_aliases = await itn_search(df)
    # itn_df = await split_multiline_rows(itn_df)

    headjson, head_html = create_html_merge(head_df, spanData=span_data)
    # head_df 에서는 출발월 을        1월||2월||3월
    # itn_df에서는 출도착 시간을     12:00||13:00 
    subData = {}
    if len(itn_df) > 0 : 
        itn_df = await split_multiline_rows(itn_df)
        subData['itinerary'], locations, places , deptime, arrtime = await convert_df_to_json(itn_df, column_aliases)
    else:        
        locations = []
        places = []
        deptime = ''
        arrtime = ''
    
    # ItineraryHtmlGenerator를 사용하여 HTML 생성
    generator = ItineraryHtmlGenerator(subData)
    itinerary_html = generator.generate_html()  # 일정 HTML 생성 (상품명 제외)
    
    # 최종 HTML 생성
    with open('./templates/template.html', 'r', encoding='utf-8') as f:
        template = f.read()
    final_html = template.replace('{{content}}', head_html + itinerary_html)
    
    # 추가 정보 업데이트
    subData['locations'] = ','.join(locations).replace(' ', '')
    subData['places'] = extract_sorted_unique_words(','.join(places))
    subData['출발시간'] = deptime
    subData['도착시간'] = arrtime
    subData.update(headjson)
    
    return JSONResponse(content={
        'status': 'success',
        'html': final_html,
        'subData': subData,
        # 'file_url': result['file_url'],  # result가 정의된 경우에만 사용
    })
    
        
# @app.post("/itinerary/df_cellMerge/")
# async def convert_df_to_html(data: TableData):
#     df = pd.DataFrame(data.tableData)
#     head_df, itn_df, column_aliases = await itn_search(df)
#     # head_df 에서는 출발월 을        1월||2월||3월
#     # itn_df 에서는 출도착 시간을     12:00||13:00 

#     itn_df = await split_multiline_rows(itn_df)
#     subData = {}
    
#     # 헤더 데이터 처리
#     headjson, head_html = create_html_merge(head_df)
    
#     # 일정 데이터 처리
#     subData['itinerary'], locations, places , deptime, arrtime = await convert_df_to_json(itn_df, column_aliases)
#     # subData['file_url'] = result['file_url']
#     # ItineraryHtmlGenerator를 사용하여 HTML 생성
#     generator = ItineraryHtmlGenerator(subData)
#     itinerary_html = generator.generate_html()  # 일정 HTML 생성 (상품명 제외)
    
#     # 최종 HTML 생성
#     with open('./templates/template.html', 'r', encoding='utf-8') as f:
#         template = f.read()
#     final_html = template.replace('{{content}}', head_html + itinerary_html)
    
#     # 추가 정보 업데이트
#     subData['locations'] = ','.join(locations).replace(' ', '')
#     subData['places'] = extract_sorted_unique_words(','.join(places))
#     subData['출발시간'] = deptime
#     subData['도착시간'] = arrtime
#     subData.update(headjson)
    
#     return JSONResponse(content={
#         'status': 'success',
#         'html': final_html,
#         'subData': subData,
#         # 'file_url': result['file_url'],  # result가 정의된 경우에만 사용
#     })
    
                
        
# @app.post("/itinerary/df_cellMerge")
# async def table_to_html(data: str = Body(...)):  # Body로 변경
#     # html2html = HTML2HTML()
#     return html2html.process_html_table(data)




@app.post("/itinerary/send-email")
async def send_email(email_request: EmailRequest):
    if len(email_request.recipients) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 recipients allowed")
    
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = SMTP_USERNAME
        msg['To'] = ', '.join(email_request.recipients)
        msg['Subject'] = email_request.subject
        
        # HTML 형식으로 이메일 본문 추가
        msg.attach(MIMEText(email_request.body, 'html'))
        
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
            
        return {"message": "Email sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")


#  itn_id 가 있으면 기존 일정표 수정, 없으면 새로운 일정표 생성
@app.post("/itinerary/fileupload/")
async def file_upload(
    file: UploadFile = File(...),
    file_url: Optional[str] = None
):
        try:
            if  file_url:
                result = uploader.update_file(file.file, file.filename, file_url)
            else:
                result = uploader.upload_file(file.file, file.filename)
                
            if not result:
                raise Exception("파일 업로드/업데이트 실패")
                
        except Exception as e:
            raise Exception(f"파일 처리 실패: {str(e)}")
        
        
        # JSON 2 html 
        return JSONResponse(content={
            'status': 'success',
            'file_url': result['file_url'],
        })

#  itn_id 가 있으면 기존 일정표 수정, 없으면 새로운 일정표 생성
@app.post("/itinerary/counseling_fileupload/")
async def file_upload(
    file: UploadFile = File(...),
    companyNo: str = ''
):
        try:
            result = uploader.file_upload( file.file, file.filename, int(companyNo))
            if not result:
                raise Exception("파일 업로드/업데이트 실패")
                
        except Exception as e:
            raise Exception(f"파일 처리 실패: {str(e)}")
        
        
        # JSON 2 html 
        return JSONResponse(content={
            'status': 'success',
            'file_url': result['file_url'],
        })




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9001)