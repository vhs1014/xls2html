from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pandas as pd
from io import BytesIO
import httpx, re, requests
from collections import Counter
from pathlib import Path
from typing import Optional, List
from urllib.parse import quote
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pydantic import BaseModel, EmailStr
# import json
# import os
# # from hwp5 import hwp5file
# import olefile

from s3_uploader import S3FileUploader
from itn2html import create_html
from head2html import create_html as create_html_head
from extract_words import extract_sorted_unique_words

import datetime
import unicodedata
import json


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
        keywords = ['일자', '교통편', '시간', '일정', '식사', 'DATE', 'CITY', 'TRANS', 'TIME', 'ITINERARY', 'MEAL']

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
                if activity.startswith('▶'):
                    details.append(activity.replace('▶ ', ''))
                else:
                    details.append(activity)
            
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
    return itinerary



async def sum_html(head_df, itn_df , url='', save_btn=False) -> pd.DataFrame:
    html_head, subData = create_html_head(head_df)  # create_html 함수 수정 필요
    html_itn , locations , places = create_html(itn_df)  # create_html 함수 수정 필요 , 도시리스트, 장소리스트를 받아옴.. 
    # subData에 저장하기 전에 리스트를 문자열로 변환
    subData['locations'] = ','.join(locations)
    subData['places'] = extract_sorted_unique_words(','.join(places))
    style1="""
     :root {
                --primary-color: #248fd6;
                --secondary-color: #333333;
                --bg-color: #f8f9fa;
            }
            
        body {
            font-family: 'Noto Sans KR', sans-serif;
            background-color: var(--bg-color) !important;
            margin: 0;
            padding: 20px;
            line-height: 1.6;
        }
        

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .content-card {
            background: white;
            margin-bottom: 15px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
            display: flex;
            align-items: stretch;
            border-radius: 8px;
            overflow: hidden;
        }
        
        .content-title {
            font-size: 15px;
            font-weight: 500;
            color: #ffffff;
            background: #248fd6;
            padding: 12px 20px;
            margin: 0;
            letter-spacing: -0.5px;
            min-width: 180px;
            display: flex;
            align-items: center;
            position: relative;
            overflow: hidden;
        }
        
        .content-title:before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 100%;
            background: linear-gradient(
                to bottom,
                rgba(255, 255, 255, 0.1) 0%,
                rgba(255, 255, 255, 0.05) 50%,
                rgba(255, 255, 255, 0) 100%
            );
        }
        
        .content-body {
            font-size: 15px;
            padding: 12px 20px;
            color: #2c3e50;
            line-height: 1.7;
            background: white;
            flex: 1;
            display: flex;
            align-items: center;
        }
        
        .header {
            background: #2c3e50;
            border-radius: 8px;
            color: #ffffff;
            padding: 15px;
            margin-bottom: 20px;
            text-align: center;
            font-size: 20px;
            font-weight: 700;
            letter-spacing: -0.5px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        }
        
        .notice-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-top: 30px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        }
        
        .notice-title {
            font-size: 17px;
            font-weight: 500;
            color: #2c3e50;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #248fd6;
        }
        
        .notice-item {
            font-size: 15px;
            color: #2c3e50;
            margin-bottom: 10px;
            padding-left: 20px;
            position: relative;
        }
        
        .notice-item:before {
            content: "•";
            color: #248fd6;
            position: absolute;
            left: 0;
        }
        
        @media (max-width: 768px) {
            .content-card {
                flex-direction: column;
            }
            
            .content-title {
                min-width: auto;
                padding: 10px 15px;
            }
            
            .content-body {
                padding: 10px 15px;
            }
        }
        .se2_inputarea td {
            font-family: 'Noto Sans KR', sans-serif;
        }
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Noto Sans KR', sans-serif;
        }

        table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            background: #fff;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
            margin-bottom: 20px;
            border-radius: 12px;
            overflow: hidden;
        }
        
        td {
            padding: 3px 5px;
            text-align: left;
            border: none;
            vertical-align: top;
            font-size: 15px !important;
            background: #fff;
            color: #2c3e50;
        }

        /* 테이블 헤더 */
        tr:first-child td {
            background: linear-gradient(135deg, #2c3e50, #34495e);
            font-weight: 500;
            color: #ffffff;
            font-size: 15px !important;
            padding: 20px 5px;
            text-align: center;  /* 텍스트 중앙 정렬 */
            vertical-align: middle;  /* 수직 중앙 정렬도 함께 적용 */
        }

        /* 날 열 스타일 */
        td:first-child {
            width: 70px;
            font-weight: 600;
            font-size: 15px !important;
            padding: 0 0 0 15px;
        }

        /* 지역 열 스타일 */
        td:nth-child(2) {
            width: 100px;
            font-weight: 500;
            padding-left: 10px;
        }

        /* 교통편 열 스타일 */
        td:nth-child(3) {
            width: 80px;
            
        }

        /* 시간 열 스타일 */
        td:nth-child(4) {
            display: none;
            width: 80px;
            
        }

        /* 식사 열 스타일 */
        td:last-child {
            width: 110px;
            font-size: 15px;
        }

        /* 새로운 일자 시작 행의 모든 td 스타일 */
        tr:has(td:first-child:not(:empty)) td {
            padding-top: 20px;
            border-top: 1px solid #d3d3d3;
        }


        td:nth-child(5):contains('▶') {
            color: #248fd6;
            font-weight: 500;
        }

        @media screen and (max-width: 768px) {
            .content-title {
                font-size: 14px;
            }
            .content-body {
                font-size: 14px;
            }
            .notice-item {
                font-size: 14px;
            }
            .container {
                padding: 0px;
                margin: 0 0 10px;
            }

            table, tbody {
                display: block;
                background: transparent;
                box-shadow: none;
            }

            tbody {
                display: flex;
                flex-direction: column;
                /* gap: 1px; */
            }

            tr {
                display: block;
                /* margin-bottom: 2px; */
            }

            tr:first-child {
                display: none;
            }

            /* 일자 헤더 스타일 */
            tr td:first-child:not(:empty) {
                background: linear-gradient(135deg, #2c3e50, #3498db);
                color: #ffffff;
                font-weight: 500;
                font-size: 14px !important;
                border: none;
                width: 100%;
                padding: 13px 20px;
                margin-top: 10px;
            }

            tr td:first-child:not(:empty)::after {
                content: " | " attr(data-location);
                font-weight: normal;
                
            }

            /* 일정 카드 스타일 */
            tr {
                background: #fff;
                /* border-radius: 12px; */
                /* box-shadow: 0 2px 8px rgba(0,0,0,0.06); */
                overflow: hidden;
                
            }

            td {
                display: block;
                /* padding: 16px 20px; */
                border: none;
                font-size: 14px !important;
                background: #fff;
            }

            /* 숨길 열 */
            td:nth-child(2),
            td:nth-child(3),
            td:nth-child(4) {
                display: none;
            }

            /* 식사 정보 스타일 
            td:last-child:not(:empty) {
                padding: 16px 20px;
                background: #f8f9fa;
                font-size: 13px !important;
                width: 100%;
            }

            td:last-child br {
                display: none;
            }
            */
            td:last-child::after {
                content: attr(data-meals);
            }

            /* 화살표 아이콘 스타일 */
            td:nth-child(5):contains('▶') {
                color: #248fd6;
                font-weight: 500;
            }

            /* 빈 셀 숨김 */
            td:empty {
                display: none;
            }
        }
        /* 데스크톱에서 식사 요약 숨기기 */
        .meals-summary  {
            height: 20px;
        }

        .meals-summary  td {
            display: none;
        }

        @media screen and (max-width: 768px) {
            /* 모바일에서 원래 식사 정보 숨기기 */
            .mobile-hidden {
                display: none !important;
            }
            
            /* 모바에서 식사 요약 표시 (첫 번째 제외) */
            .meals-summary:not(:first-of-type) {
                display: block;
                background: #f5f6f7;

            }
            
            .meals-summary:not(:first-of-type) .daily-meals {
                /* padding: 16px 20px !important; */
                padding: 10px;
                background: #ffffff;
                margin-top: 0px;
                font-size: 13px !important;
                color: #919191;  /* 푸른색 */
                /* line-height: 1.6; */
                /* white-space: pre-line; */
            }
            
            /* 첫 번째 meals-summary 숨기기 */
            .meals-summary:first-of-type {
                display: none !important;
            }
            
            /* 마지막 식사 요약의 마진 제거 */
            .meals-summary:last-child {
                margin-bottom: 0;
            }
            .meals-summary  {
                height: auto;
            }

            .meals-summary  td {
                display: block;
            }
        }
    """
    btn_download = f'<a href="{url}" style="border-radius:8px;background: #248fd6;color: #ffffff;align-items: center;justify-content: center;width: 150px;height: 50px;display: grid;margin: 0 auto;text-decoration: none;">엑셀 다운로드</a>'
    final_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>여행 일정</title>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
        <style>
            {style1}
        </style>    
    </head>
    <body>
        {html_head}
        <div class="xls_itn">
            {html_itn + btn_download if save_btn else html_itn}
        </div>
    </body>
    </html>
    """
    return final_html, subData

@app.get("/itinerary/health")
async def health():
    return 'ok'


@app.get("/itinerary/fileselect/")
async def read_root():
    """업로드 폼을 보여주는 HTML 페이지 반환"""
    try:
        html_content = (TEMPLATES_DIR / "upload.html").read_text(encoding="utf-8")
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"HTML 파일 로드 실패: {str(e)}")


@app.post("/itinerary/upload/")
async def convert_excel_to_html(file: UploadFile = File(...)):
    try:
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="엑셀 파일만 업로드 가능합니다.")
        
        # 업로드된 파일에서 DataFrame으로 읽기
        head_df, itn_df = await read_excel_from_upload(file)
        
        result = uploader.upload_file(file.file, file.filename)
        final_html, subData = await sum_html(head_df, itn_df, result['file_url'], save_btn=True)
        
        subData['file_url'] =  result['file_url']
        subData['itn_id'] =  None
        
        return HTMLResponse(content=final_html, status_code=200)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"변환 실패: {str(e)}")


@app.get("/itinerary/url/")
async def convert_excel_to_html(excel_url: str):
    try:
        # URL에서 직접 DataFrame으로 읽기
        head_df, itn_df  = await read_excel_from_url(excel_url)
        final_html, subData = await sum_html(head_df, itn_df, excel_url)
        subData['itinerary'] = await convert_df_to_json(itn_df)
        result = {
            'html': final_html,
            'subData': subData,
            'file_url': excel_url
        }
        return JSONResponse(content=result , status_code=200)
        # return HTMLResponse(content=final_html, status_code=200)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"변환 실패: {str(e)}")


# =====================================================================================
# 엑셀 파일 업로드 및 S3 저장
# =====================================================================================


@app.get("/itinerary/s3select/")
async def read_root():
    """업로드 폼을 보여주는 HTML 페이지 반환"""
    try:
        html_content = (TEMPLATES_DIR / "s3upload.html").read_text(encoding="utf-8")
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"HTML 파일 로드 실패: {str(e)}")

@app.get("/itinerary/s3json/")
async def read_root():
    """업로드 폼을 보여주는 HTML 페이지 반환"""
    try:
        html_content = (TEMPLATES_DIR / "s3json.html").read_text(encoding="utf-8")
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
        
        final_html, subData = await sum_html(head_df, itn_df, result['file_url'], save_btn=True)
        
        subData['itinerary'] = await convert_df_to_json(itn_df)
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