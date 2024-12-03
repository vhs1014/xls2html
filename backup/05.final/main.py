from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from s3_uploader import S3FileUploader
import pandas as pd
from io import BytesIO
import httpx, re
from collections import Counter
from itn2html import create_html
from head2html import create_html as create_html_head
from pathlib import Path


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


def extract_sorted_unique_words(df, columns=None, min_length=2):
    """
    데이터프레임에서 정제된 고유 단어를 빈도순으로 추출
    """
    try:
        # 제외할 단어 목록
        exclude_words = {
            '호텔', '공항', '이동', '관광', '교통', 'remark', '휴식', '차량', '항공', '요금', '개인'
            '국제', '미팅', '기내', '조식', '수하물', '니다', '세요','조건', '견적은', '개월','도착', '출발', '상품', '식사', '중식', '석식', '동급', '현지','으로', '투숙', '예약', '가능', '기사', '만원', '필수','하는', '기준' , '미만', '수속', '전일', '또는', '최소','특전', '특징', '일차', '체크', '일정','있는', '하여', '에서', '사용', '상기', '전체', '기는', '지정된', '출입', '탑승', '변경', '포함', '합산', '사정에', '옷과', '세워진', '요망', '출국',
            '귀국'
        }
        
        # 제외할 단어가 포함된 복합어도 제외
        exclude_patterns = '|'.join(exclude_words)
        
        if columns is None:
            columns = df.columns
            
        text_items = []
        
        def clean_text(text):
            # 괄호와 괄호 안 내용 제거
            text = re.sub(r'\([^)]*\)', '', str(text))
            # 특수문자 제거
            text = re.sub(r'[^가-힣a-zA-Z\s]', ' ', text)
            # 연속된 공백을 하나로
            text = ' '.join(text.split())
            return text
        
        def is_valid_word(word):
            # 최소 길이 체크
            if len(word) < min_length:
                return False
            
            # 한글 또는 영문으로만 구성되었는지 체크
            if not re.match(r'^[가-힣]+$|^[a-zA-Z]+$', word):
                return False
            
            # 한글 1글자 제외
            if re.match(r'^[가-힣]$', word):
                return False
            
            # 제외할 단어가 포함된 경우 제외
            if re.search(exclude_patterns, word, re.IGNORECASE):
                return False
                
            # 제외할 단어와 정확히 일치하는 경우 제외
            if word.lower() in {w.lower() for w in exclude_words}:
                return False
                
            return True
        
        # 텍스트 추출 및 처리
        for col in columns:
            series = df[col].dropna()
            
            for item in series:
                # 텍스트 정제
                cleaned_text = clean_text(item)
                
                # 공백으로 분리
                words = cleaned_text.split()
                
                for word in words:
                    # 영문은 소문자로 변환
                    if re.match(r'^[a-zA-Z]+$', word):
                        word = word.lower()
                    
                    if is_valid_word(word):
                        text_items.append(word)
        
        # 빈도수 계산 및 정렬
        word_counts = Counter(text_items)
        
        # 빈도수 순으로 정렬, 같은 빈도수면 단어 알파벳 순
        sorted_unique_words = [word for word, _ in sorted(word_counts.items(), key=lambda x: (-x[1], x[0]))]
        
        return sorted_unique_words
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        return []
    
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
        unique_words = extract_sorted_unique_words(df)
        head_df, itn_df = await itn_search(df)
        return head_df, itn_df, unique_words
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
            unique_words = extract_sorted_unique_words(df)
            head_df, itn_df = await itn_search(df)
            return head_df, itn_df, unique_words
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"엑셀 파일 읽기 실패: {str(e)}")
    
async def sum_html(head_df, itn_df , url='', save_btn=False) -> pd.DataFrame:
    html_head = create_html_head(head_df)  # create_html 함수 수정 필요
    html_itn = create_html(itn_df)  # create_html 함수 수정 필요
    style1="""
     :root {
                --primary-color: #248fd6;
                --secondary-color: #333333;
                --bg-color: #f8f9fa;
            }
            
        body {
            font-family: 'Noto Sans KR', sans-serif;
            background-color: var(--bg-color);
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
    return final_html

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
        head_df, itn_df, unique_words = await read_excel_from_upload(file)
        result = uploader.upload_file(file.file, file.filename)
        final_html = await sum_html(head_df, itn_df, result['file_url'], save_btn=True)
        
        return HTMLResponse(content=final_html, status_code=200)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"변환 실패: {str(e)}")


@app.get("/itinerary/url/")
async def convert_excel_to_html(excel_url: str):
    try:
        # URL에서 직접 DataFrame으로 읽기
        head_df, itn_df, unique_words = await read_excel_from_url(excel_url)
        final_html = await sum_html(head_df, itn_df, excel_url)
        result = {
            'html': final_html,
            'unique_words': unique_words
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


@app.post("/itinerary/saveupload/")
async def convert_excel_to_html(file: UploadFile = File(...)):
    try:
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="엑셀 파일만 업로드 가능합니다.")
        
        # 업로드된 파일에서 DataFrame으로 읽기
        head_df, itn_df, unique_words = await read_excel_from_upload(file)
        result = uploader.upload_file(file.file, file.filename)
        final_html = await sum_html(head_df, itn_df, result['file_url'], save_btn=True)
        if result['status'] == 'success':
            result['html'] = final_html  # html 키와 값 추가
            result['unique_words'] = unique_words
            return JSONResponse(content=result , status_code=200)
        else:
            return JSONResponse(
                content={'error': result['error']}, 
                status_code=500
            )
    except Exception as e:
        return JSONResponse(
            content={'error': str(e)}, 
            status_code=500
        )



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9001)
#     uvicorn.run(app, host="0.0.0.0", port=9000)
