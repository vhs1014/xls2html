from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
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

from s3_uploader import S3FileUploader

from head2html import create_html 
from extract_words import extract_sorted_unique_words

import datetime
import unicodedata

import json2html


app = FastAPI()

# CORS 미들웨어 설정 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 origin 허용. 프로덕션에서는 특정 도메인만 지정하는 것이 좋습니다
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 HTTP 헤더 허용
)

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
        
        # 각 컬럼의 내용을 확인하고 줄바꿈이 있는지 체크
        for col in df.columns:
            if isinstance(row[col], str):
                lines = row[col].split('\n')
                if len(lines) > 1:
                    has_multiline = True
                    split_contents[col] = lines
                    max_lines = max(max_lines, len(lines))
                else:
                    split_contents[col] = [row[col]] * max_lines
            else:
                split_contents[col] = [row[col]] * max_lines
        
        # 멀티라인이 없는 경우 원래 행을 그대로 추가
        if not has_multiline:
            new_rows.append(row.to_dict())
        else:
            # 멀티라인이 있��� 경우 분리하여 새로운 행 생성
            for line_idx in range(max_lines):
                new_row = {}
                for col in df.columns:
                    try:
                        new_row[col] = split_contents[col][line_idx]
                    except IndexError:
                        new_row[col] = split_contents[col][-1]  # 라인이 부족한 경우 마지막 값 사용
                new_rows.append(new_row)

    # 새로운 데이터프레임 생성
    result_df = pd.DataFrame(new_rows)
    return result_df

async def itn_search(df: pd.DataFrame) -> pd.DataFrame:
    # 컬럼 매핑 정의
    column_aliases = {
        'date': ['일자', '날짜', '순번', '일시', 'Date', 'Day', 'No'],
        'place': ['지역', '장소', 'place', 'city', '도시', '여행지'],
        'transport': ['교통편', '이동수단', '교통', 'Trans', 'Transport'],
        'time': ['시간', 'time'],
        'itinerary': ['주요일정', '일정', '관광지', 'itinerary'],
        'meal': ['식사', 'meal', 'meals']
    }
    
    # 특정 단어가 한 줄에 3개 이상 나오는 줄을 찾고, 해당 줄 위에 모든 데이터를 삭제
    idy = -1
    for idx, row in df.iterrows():
        # 각 셀의 값에서 모든 빈칸을 지워줍니다.
        cleaned_row = [str(cell).replace(' ', '').lower() for cell in row]
        # 각 셀이 어떤 카테고리에 속하는지 확인
        cells_with_matches = 0  # 매칭된 셀의 수를 카운트
        
        for cell in cleaned_row:
            has_match = False  # 현재 셀이 매칭되었는지 여부
            for category, aliases in column_aliases.items():
                if any(alias.lower() in cell for alias in aliases):
                    has_match = True
                    break
            if has_match:
                cells_with_matches += 1
                    
        if cells_with_matches >= 3:
            idy = idx
            break
            
    head_df = df.iloc[:idy]  # 헤더 부분
    itn_df = df.iloc[idy:]   # 일정 부분
    
    # head, itn 각각 빈줄, 빈칸 제거
    head_df = head_df.dropna(axis=1, how='all')   
    head_df.columns = range(len(head_df.columns))  
    head_df = head_df.dropna(axis=0, how='all') 
    
    itn_df = itn_df.dropna(axis=1, how='all')   
    itn_df.columns = range(len(itn_df.columns))  
    itn_df = itn_df.dropna(axis=0, how='all')
    
    return head_df, itn_df, column_aliases
    
async def read_excel_from_upload(file: UploadFile) -> pd.DataFrame:
    """업로드된 엑셀 파일을 DataFrame으로 읽기"""
    try:
        contents = await file.read()
        excel_data = BytesIO(contents)
        
        # BytesIO에서 직접 DataFrame으로 읽기
        df = pd.read_excel(excel_data, header=None)
        # unique_words = extract_sorted_unique_words(df)
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
            df = pd.read_excel(excel_data, header=None)
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
            r'제?\d+일차?$',  # '제1일', '1일차', '제1일차'
            r'\d+일$',        # '1일'
        ]
        return any(re.search(pattern, text) for pattern in day_patterns)

    for idx, row in df.iterrows():
        # 일자 처리
        if date_col is not None and pd.notna(row[date_col]) and is_day_header(str(row[date_col])):
            # 이전 day_data가 있으면 현재 location을 추가하고 itinerary에 추가
            if day_data is not None and current_location is not None:
                if current_location["schedule"]:  # schedule이 있는 경우만 추가
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
                if current_location is not None and current_location["schedule"]:
                    day_data['locations'].append(current_location)
                
                location_name = new_location_name
                current_location = {
                    "place": location_name,
                    "schedule": []
                }
                locations.add(location_name)
                if transport_col is not None and pd.notna(row[transport_col]):
                    current_location['flight'] = clean_text(row[transport_col])
        
        # 일정 처리
        if current_location is not None and itinerary_col is not None and pd.notna(row[itinerary_col]):
            schedule_item = {}
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
                if len(schedule_item['details']) > 0:
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

    # 마지막 day_data 처리
    if day_data is not None and current_location is not None:
        if current_location["schedule"]:  # schedule이 있는 경우만 추가
            day_data['locations'].append(current_location)
        itinerary.append(day_data)

    return itinerary, locations, places



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
        subData =  create_html(head_df)
        subData['itinerary'], locations, places = await convert_df_to_json(itn_df, column_aliases)
        
        subData['file_url'] = excel_url
        final_html = json2html.generate_itinerary_html(subData)
        

        # html 생성후 추가 정보 추가
        subData['locations'] = ','.join(locations)
        subData['places'] = extract_sorted_unique_words(','.join(places))

        result = {
            'html': final_html,
            'subData': subData,
            'file_url': excel_url
        }
        return JSONResponse(content=result , status_code=200)
        # return HTMLResponse(content=final_html, status_code=200)
            
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
        # 초기 result 변수 선언
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="엑셀 파일만 업로드 가능합니다.")
        
        
        if file.filename.endswith(('.xlsx', '.xls')):
            # 엑셀 파일 처리
            head_df, itn_df ,column_aliases= await read_excel_from_upload(file)
        try:
            if itn_id and file_url:
                result = uploader.update_file(file.file, file.filename, file_url)
            else:
                result = uploader.upload_file(file.file, file.filename)
                
            if not result:
                raise Exception("파일 업로드/업데이트 실패")
                
        except Exception as e:
            raise Exception(f"파일 처리 실패: {str(e)}")
        
        itn_df = await split_multiline_rows(itn_df)
        subData =  create_html(head_df)
        subData['itinerary'], locations, places = await convert_df_to_json(itn_df, column_aliases)
        subData['file_url'] = result['file_url']
        final_html = json2html.generate_itinerary_html(subData)
        
        # html 생성후 추가 정보 추가
        subData['locations'] = ','.join(locations).replace(' ', '')
        subData['places'] = extract_sorted_unique_words(','.join(places))
        
        # JSON 2 html 
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9001)
