import pandas as pd
import numpy as np


def create_html(df: pd.DataFrame) -> str:
    
    # HTML 시작 부분
    html_content = """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>365투어 단독 상품</title>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary-color: #248fd6;
                --secondary-color: #2c3e50;
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
                padding: 20px;
            }
            
            .content-card {
                background: white;
                margin-bottom: 15px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.08);
                display: flex;
                align-items: stretch;
                border-radius: 8px;
                overflow: hidden;
            }
            
            .content-title {
                font-size: 15px;
                font-weight: 500;
                color: white;
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
                color: var(--secondary-color);
                line-height: 1.7;
                background: white;
                flex: 1;
                display: flex;
                align-items: center;
            }
            
            .header {
                background: var(--secondary-color);
                border-radius: 8px;
                color: white;
                padding: 20px;
                margin-bottom: 30px;
                text-align: center;
                font-size: 24px;
                font-weight: 700;
                letter-spacing: -0.5px;
                box-shadow: 0 4px 15px rgba(44, 62, 80, 0.2);
            }
            
            .notice-card {
                background: white;
                border-radius: 8px;
                padding: 20px;
                margin-top: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            }
            
            .notice-title {
                font-size: 17px;
                font-weight: 500;
                color: var(--secondary-color);
                margin-bottom: 15px;
                padding-bottom: 10px;
                border-bottom: 2px solid var(--primary-color);
            }
            
            .notice-item {
                font-size: 15px;
                color: var(--secondary-color);
                margin-bottom: 10px;
                padding-left: 20px;
                position: relative;
            }
            
            .notice-item:before {
                content: "•";
                color: var(--primary-color);
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
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">365투어 단독 상품</div>
    """
    
    # 내용이 있는 카드와 없는 카드 분리
    empty_content_titles = []
    
    # 데이터 처리 및 HTML 컨텐츠 생성
    for i in range(df.shape[0]):
        row = df.iloc[i]
        row_data = [str(x) for x in row if pd.notna(x) and str(x).strip() != '']
        if row_data:
            title = row_data[0]
            content = ' | '.join(row_data[1:]) if len(row_data) > 1 else ''
            
            if content:
                html_content += f"""
                <div class="content-card">
                    <div class="content-title">{title}</div>
                    <div class="content-body">{content}</div>
                </div>
                """
            else:
                empty_content_titles.append(title)
    
    # 내용이 없는 항목들을 하나의 카드로 표시
    if empty_content_titles:
        html_content += """
        <div class="notice-card">
            <div class="notice-title">주요 안내사항</div>
        """
        for title in empty_content_titles:
            html_content += f"""
            <div class="notice-item">{title}</div>
            """
        html_content += "</div>"
    
    # HTML 종료 부분
    html_content += """
        </div>
    </body>
    </html>
    """
    return html_content
