from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import pandas as pd
from io import BytesIO
import httpx
from itn2html import create_html
from pathlib import Path

app = FastAPI()

# 정적 파일 경로를 /itinerary/static으로 설정
app.mount("/itinerary/static", StaticFiles(directory="static"), name="static")
# templates 디렉토리 경로 설정
TEMPLATES_DIR = Path("templates")

async def itn_search(df: pd.DataFrame) -> pd.DataFrame:
        keyword_count = 0
        # 특정 단어가 한 줄에 2개 이상 나오는 줄을 찾고, 해당 줄 위에 모든 데이터를 삭제
        keywords = ['일자', '교통편', '시간', '일정', '식사']

        # 해당 줄 위에 모든 데이터를 삭제합니다.
        for idx, row in df.iterrows():
            # 각 셀의 값에서 모든 빈칸을 지워줍니다.
            cleaned_row = [str(cell).replace(' ', '') for cell in row]
            # keywords와 비교하여 한 줄에 3개 이상 일치하는지 확인합니다.
            for keyword in keywords:
                if keyword in cleaned_row:
                    keyword_count += 1
            
            if keyword_count >= 3:
                # 해당 줄 위에 모든 데이터를 삭제합니다.
                df = df.iloc[idx:]
                break
        df = df.dropna(axis=1, how='all')   
        df.columns = range(len(df.columns))  
        df = df.dropna(axis=0, how='all') 
        return df
    
async def read_excel_from_upload(file: UploadFile) -> pd.DataFrame:
    """업로드된 엑셀 파일을 DataFrame으로 읽기"""
    try:
        contents = await file.read()
        excel_data = BytesIO(contents)
        
        # BytesIO에서 직접 DataFrame으로 읽기
        df = pd.read_excel(excel_data, header=None)
        df = await itn_search(df)


        return df    
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
            df = await itn_search(df)
            return df
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"엑셀 파일 읽기 실패: {str(e)}")


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
        df = await read_excel_from_upload(file)
        
        # HTML로 변환
        html_content = create_html(df)  # create_html 함수 수정 필요
        
        return HTMLResponse(content=html_content, status_code=200)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"변환 실패: {str(e)}")

@app.get("/itinerary/health")
async def health():
    return 'ok'

@app.get("/itinerary/")
async def convert_excel_to_html(excel_url: str):
    try:
        # URL에서 직접 DataFrame으로 읽기
        df = await read_excel_from_url(excel_url)
        
        # 여기서 create_html 함수를 DataFrame을 직접 사용하도록 수정
        html_content = create_html(df)  # create_html 함수 수정 필요
        
        return HTMLResponse(content=html_content, status_code=200)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"변환 실패: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)