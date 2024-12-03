import pandas as pd
import numpy as np
from datetime import datetime, time

def convert_excel_time(time_str):
    if pd.isna(time_str) or time_str == '':
        return ''
    try:
        if isinstance(time_str, float):
            # Excel 시간 형식 변환
            total_seconds = int(time_str * 24 * 60 * 60)
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours:02d}:{minutes:02d}"
        elif isinstance(time_str, str):
            # 문자열 형식의 시간 변환
            try:
                # 시:분:초 형식의 문자열을 시:분으로 변환
                parsed_time = datetime.strptime(time_str, "%H:%M:%S").time()
                return parsed_time.strftime("%H:%M")
            except ValueError:
                # 이미 시:분 형식인 경우
                return time_str
        else:
            return (time_str.strftime("%H:%M"))
            # return str(time_str)
    except:
        return str(time_str)

def clean_text(text, for_data_attr=False):
    if pd.isna(text) or text == '':
        return ''
    
    if for_data_attr:
        return str(text)
    
    # 연속된 줄바꿈을 하나로 통일
    cleaned = str(text).replace('\n\n', '\n')
    # 줄바꿈을 | 로 변환
    cleaned = cleaned.replace('\n', ' | ')
    # 연속된 | 제거
    while ' |  | ' in cleaned:
        cleaned = cleaned.replace(' |  | ', ' | ')
    
    return cleaned.strip()

def insert_time_to_schedule(schedule, time):
    if not time or not schedule:
        return schedule
    
    # 시간 배열 생성
    times = [t.strip() for t in time.split('<br>') if t.strip()]
    if not times:
        return schedule
    
    # 키워드와 매칭할 시간 인덱스
    time_index = 0
    
    # 키워드 리스트
    keywords = ['탑승', '출발', '도착']
    
    # 각 키워드에 대해 시간 정보 삽입
    modified_schedule = schedule
    for keyword in keywords:
        if time_index >= len(times):
            break
            
        if keyword in modified_schedule:
            # 키워드 뒤에 시간 정보 삽입
            modified_schedule = modified_schedule.replace(
                keyword,
                # f"{keyword}({times[time_index]})"
                f"{keyword}<span-victory style='color: #3498db;'>({times[time_index]})</span-victory>"
            )
            time_index += 1
    
    return modified_schedule


def create_html(df: pd.DataFrame) -> str:
    # HTML 템플릿 시작 부분
    html_template_start = '''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>여행 일정표</title>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
                * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Noto Sans KR', sans-serif;
        }

        body {
            background: #f8f9fa;
            color: #535353;
            line-height: 1.6;
            font-size: 15px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0px;
        }

        table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            background: #fff;
            box-shadow: 0 3px 12px rgba(0,0,0,0.05);
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
        }

        /* 테이블 헤더 */
        tr:first-child td {
            background: linear-gradient(135deg, #2c3e50, #34495e);
            font-weight: 500;
            color: #fff;
            font-size: 15px !important;
            padding: 20px 5px;
            text-align: center;  /* 텍스트 중앙 정렬 */
            vertical-align: middle;  /* 수직 중앙 정렬도 함께 적용 */
        }

        /* 날짜 열 스타일 */
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
            color: #3498db;
            font-weight: 500;
        }

        @media screen and (max-width: 768px) {
            .container {
                padding: 0px;
                margin: 0;
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
                color: #fff;
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
                color: #3498db;
                font-weight: 500;
            }

            /* 빈 셀 숨김 */
            td:empty {
                display: none;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <table>
            <tbody>'''

    html_template_end = '''
            </tbody>
        </table>
    </div>
</body>
</html>'''


    html_rows = []
    current_date = ''
    current_meals = []
    is_first_meal_overall = True  # 전체 일정의 첫 번째 식사 정보 체크용 플래그
        # 테이블 헤더 행 추가

    # 각 행을 HTML로 변환
    for idx, row in df.iterrows():
        if pd.isna(row[4]):
            combined_text = ' | '.join([str(cell).replace('\n', '<br>') for cell in row if not pd.isna(cell)])
            html_row = f'''                <tr>
                    <td colspan="6">{combined_text}</td>
                </tr>'''
            html_rows.append(html_row)
        else:    
            date = str(row[0]).replace('\n', '<br>') if not pd.isna(row[0]) else ''
            location = str(row[1]).replace('\n', '<br>') if not pd.isna(row[1]) else ''
            transport = str(row[2]).replace('\n', '<br>') if not pd.isna(row[2]) else ''
            time =convert_excel_time(row[3]).replace('\n', '<br>')
            schedule = str(row[4]).replace('\n', '<br>') if not pd.isna(row[4]) else ''
            meals = str(row[5]) if not pd.isna(row[5]) else ''
            
            # 모바일용 schedule에 time 정보 삽입
            mobile_schedule = insert_time_to_schedule(schedule, time)
            
            # 새로운 날짜가 시작될 때
            if (date and date != current_date) :
            # if (date and date != current_date) and current_date != '':
                # 이전 날짜의 식사 정보 추가
                if current_meals:
                    meals_text = ' | '.join(filter(None, current_meals))
                    html_rows.append(f'''                <tr class="meals-summary">
                        <td colspan="6" class="daily-meals">{meals_text}</td>
                    </tr>''')
                    current_meals = []
                current_date = date
            
            # 식사 정보 수집 (전체 일정의 첫 번째는 제외)
            if meals:
                if is_first_meal_overall:
                    is_first_meal_overall = False  # 첫 번째 식사 정보 처리 후 플래그 변경
                else:
                    current_meals.append(meals)
            ctext = str(row[1]) if not pd.isna(row[1]) else ''
            data_location = f' data-location="{clean_text(ctext, True)}"' if date else ''

            
            html_row = f'''                <tr>
                        <td{data_location}>{clean_text(date)}</td>
                        <td>{clean_text(location)}</td>
                        <td>{clean_text(transport)}</td>
                        <td class="mobile-hidden">{time}</td>
                        <td>{mobile_schedule}</td>
                        <td class="mobile-hidden">{meals}</td>
                    </tr>'''
                    
            html_rows.append(html_row)
    # 가로 병합된 cell이면 td에 colspan을 적용
    # 마지막 날짜의 식사 정보 처리
        if current_meals:
            meals_text = ' | '.join(filter(None, current_meals))
            html_rows.append(f'''                <tr class="meals-summary">
                        <td colspan="6" class="daily-meals">{meals_text}</td>
                    </tr>''')
    
    # CSS 스타일 추가
    html_template_start = html_template_start.replace('</style>',
    '''
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
            
            /* 모바일에서 식사 요약 표시 (첫 번째 제외) */
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
        </style>''')
    
    # 최종 HTML 생성
    final_html = html_template_start + '\n'.join(html_rows) + html_template_end
    return final_html  
    # # HTML 파일 저장
    # with open('target.html', 'w', encoding='utf-8') as f:
    #     f.write(final_html)

# if __name__ == "__main__":
#     create_html()