import pandas as pd
import numpy as np


def create_html(df: pd.DataFrame) -> str:
    
    # HTML 시작 부분
    html_content = """
        <div class="container">
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
                if i == 0:      # 첫번째 줄은 제목으로 별로 처리
                    html_content += f"""
                    <div class="container">
                        <div class="header">{title}</div>
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
