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



async def itn_search(df: pd.DataFrame) -> pd.DataFrame:
        keyword_count = 0
        # 특정 단어가 한 줄에 2개 이상 나오는 줄을 찾고, 해당 줄 위에 모든 데이터를 삭제
        keywords = ['일자', '교통편', '시간', '일정', '식사', '장소', '날짜', 'DATE', 'CITY', 'TRANS', 'TIME', 'ITINERARY', 'MEAL']

        # 해당 줄 위에 모든 데이터를 삭제합니다.
        idy  = -1
        for idx, row in df.iterrows():
            # 각 셀의 값에서 모든 빈칸을 지워줍니다.
            cleaned_row = [str(cell).replace(' ', '') for cell in row]
            # keywords와 비교하여 한 줄에 3개 이상 일치하는지 확인합니다.
            for keyword in keywords:
                if keyword in cleaned_row:
                    keyword_count += 1

            if keyword_count >= 3:
                idy = idx    
                break
        head_df = df.iloc[:idy]  # 헤더 부분
        itn_df = df.iloc[idy:]   # 일정 부분
        
        # head , itn 가각 빈줄, 빈칸 제거
        head_df = head_df.dropna(axis=1, how='all')   
        head_df.columns = range(len(head_df.columns))  
        head_df = head_df.dropna(axis=0, how='all') 
        
        itn_df = itn_df.dropna(axis=1, how='all')   
        itn_df.columns = range(len(itn_df.columns))  
        itn_df = itn_df.dropna(axis=0, how='all') 
        return head_df, itn_df
    
async def read_excel_from_upload(file: UploadFile) -> pd.DataFrame:
    """업로드된 엑셀 파일을 DataFrame으로 읽기"""
    try:
        contents = await file.read()
        excel_data = BytesIO(contents)
        
        # BytesIO에서 직접 DataFrame으로 읽기
        df = pd.read_excel(excel_data, header=None)
        # unique_words = extract_sorted_unique_words(df)
        head_df, itn_df = await itn_search(df)
        return head_df, itn_df
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
            head_df, itn_df = await itn_search(df)
            return head_df, itn_df
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"엑셀 파일 읽기 실패: {str(e)}")



async def convert_df_to_json(df: pd.DataFrame) -> str:
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
        # 문자열로 변환
        text = str(text)
        # 유니코드 정규화 (NFKC)
        text = unicodedata.normalize('NFKC', text)
        # \xa0를 일반 공백으로 변환
        text = text.replace('\xa0', ' ')
        # 연속된 공백을 하나로
        text = ' '.join(text.split())
        return text
    
    # 첫 번째 행의 컬럼명을 가져옴
    columns = df.columns.tolist()
    
    # 첫 번째 행은 제외하고 처리
    df = df.iloc[1:]
    locations = set()
    places = set()
    itinerary = []
    current_day = None
    current_location = None
    day_data = None

    # DataFrame의 각 행을 순회하며 처리
    for idx, row in df.iterrows():
        
        # 일자 처리
        if pd.notna(row[columns[0]]):
            day_str = clean_text(row[columns[0]])
            # 숫자만 추출
            numbers = ''.join(filter(str.isdigit, day_str))
            # 숫자가 있는 경우에만 처리
            if numbers:
                day_num = int(numbers)
                
                if day_num != current_day:
                    if day_data is not None:
                        itinerary.append(day_data)
                    current_day = day_num
                    day_data = {
                        "day": day_num,
                        "locations": [],
                        "meals": {}
                    }
                    current_location = None
        
        if pd.isna(row[columns[0]]) and day_data is None:
            continue
            
        # 지역 처리
        if pd.notna(row[columns[1]]):
            location_name = clean_text(row[columns[1]])
            if current_location is None or current_location['place'] != location_name:
                current_location = {
                    "place": location_name,
                    "schedule": []
                }
                locations.add(location_name)
                if pd.notna(row[columns[2]]):
                    current_location['flight'] = clean_text(row[columns[2]])
                day_data['locations'].append(current_location)
        
        # 일정 처리
        if current_location is not None and pd.notna(row[columns[4]]):
            schedule_item = {}
            if pd.notna(row[columns[3]]):
                time_value = row[columns[3]]
                # datetime.time 객체인 경우
                if isinstance(time_value, (datetime.time, datetime.datetime)):
                    time_value = time_value.strftime('%H:%M')
                # 문자열인 경우 정제해서 사용
                else:
                    time_value = clean_text(time_value)
                schedule_item['time'] = time_value
            
            # 주요일정을 details 배열로 처리
            activity_text = clean_text(row[columns[4]])
            details = []
            
            # 줄바꿈으로 분리하여 처리
            activities = activity_text.split('\n')
            for activity in activities:
                activity = clean_text(activity)
                details.append(activity)
                places.add(activity)                    
            
            schedule_item['details'] = details
            current_location['schedule'].append(schedule_item)
        
        # 식사 정보 처리
        if pd.notna(row[columns[5]]):
            meals = clean_text(row[columns[5]]).split('\n')
            for meal in meals:
                meal = clean_text(meal)
                if meal.startswith('조:'):
                    day_data['meals']['breakfast'] = meal.replace('조:', '')
                elif meal.startswith('중:'):
                    day_data['meals']['lunch'] = meal.replace('중:', '')
                elif meal.startswith('석:'):
                    day_data['meals']['dinner'] = meal.replace('석:', '')
    
    # 마지막 일정 추가
    if day_data is not None:
        itinerary.append(day_data)

    # return json.dumps(result, ensure_ascii=False)
    return itinerary, locations , places 



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
        head_df, itn_df  = await read_excel_from_url(excel_url)
        subData =  create_html(head_df)
        subData['itinerary'], locations, places = await convert_df_to_json(itn_df)
        subData['file_url'] = excel_url
        subData['locations'] = ','.join(locations)
        subData['places'] = extract_sorted_unique_words(','.join(places))
        final_html = json2html.generate_itinerary_html(subData['itinerary'])
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
            head_df, itn_df = await read_excel_from_upload(file)
        try:
            if itn_id and file_url:
                result = uploader.update_file(file.file, file.filename, file_url)
            else:
                result = uploader.upload_file(file.file, file.filename)
                
            if not result:
                raise Exception("파일 업로드/업데이트 실패")
                
        except Exception as e:
            raise Exception(f"파일 처리 실패: {str(e)}")
        
        # final_html, subData = await sum_html(head_df, itn_df, result['file_url'], save_btn=True)
        
        subData =  create_html(head_df)
        subData['itinerary'], locations, places = await convert_df_to_json(itn_df)
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
