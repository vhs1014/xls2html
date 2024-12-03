import pandas as pd
import numpy as np


def create_html(df: pd.DataFrame) -> str:
    
    # HTML 시작 부분
    html_content = """
        <div class="container">
    """
    
    # 내용이 있는 카드와 없는 카드 분리
    empty_content_titles = []


    before_content = ""
    title_chk = False
    # 데이터 처리 및 HTML 컨텐츠 생성
    for i in range(df.shape[0]):
        row = df.iloc[i]
        row_data = [str(x) if pd.notna(x) else '' for x in row if str(x).strip() != '']  # 빈셀 유지 구문
        # row_data = [str(x) for x in row if pd.notna(x) and str(x).strip() != '']  # 빈셀 삭제 구문
        if row_data:
            title = row_data[0].strip()
            # content = ' | '.join(row_data[1:]).strip() if len(row_data) > 1 else ''.strip()
            content = ' | '.join(x for x in row_data[1:] if x.strip()).strip() if len(row_data) > 1 else ''.strip()
            if content.replace(' ', '').replace('|', '') != '':
                if title:     # 타이틀이 없고 컨텐츠가 있는 경우는 상위와 병합
                    html_content += f"""
                    <div class="content-card">
                        <div class="content-title">{title}</div>
                        <div class="content-body">{content}</div>
                    </div>
                    """
                    title_chk = True
                    before_content = content
                else:
                    html_content = html_content.replace(before_content, before_content + '<br>' + content)
                    before_content = content
                    
            else:
                if i == 0:      # 첫번째 줄은 제목으로 별로 처리
                    html_content += f"""
                    <div class="container">
                        <div class="header">{title}</div>
                    </div>
                    """
                else:
                    # empty_content_titles.append(title)
                    if title_chk:
                        html_content = html_content.replace(before_content, before_content + '<br>' + title)
                    else:
                        # 신규로 타이틀만 표시하는 인터페이스
                        html_content += f"""
                        <div style="background-color: #248fd63d; padding: 10px 0 10px 20px; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08)">{title}</div>
                        """
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
