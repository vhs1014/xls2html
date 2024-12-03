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
    html_template_start = '''
    <div class="container">
        <table>
            <tbody>'''

    html_template_end = '''
            </tbody>
        </table>
    </div>
'''


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
    # html_template_start = html_template_start.replace('</style>',
    # '''
    #     /* 데스크톱에서 식사 요약 숨기기 */
    #     .meals-summary  {
    #         height: 20px;
    #     }

    #     .meals-summary  td {
    #         display: none;
    #     }

    #     @media screen and (max-width: 768px) {
    #         /* 모바일에서 원래 식사 정보 숨기기 */
    #         .mobile-hidden {
    #             display: none !important;
    #         }
            
    #         /* 모바일에서 식사 요약 표시 (첫 번째 제외) */
    #         .meals-summary:not(:first-of-type) {
    #             display: block;
    #             background: #f5f6f7;

    #         }
            
    #         .meals-summary:not(:first-of-type) .daily-meals {
    #             /* padding: 16px 20px !important; */
    #             padding: 10px;
    #             background: #ffffff;
    #             margin-top: 0px;
    #             font-size: 13px !important;
    #             color: #919191;  /* 푸른색 */
    #             /* line-height: 1.6; */
    #             /* white-space: pre-line; */
    #         }
            
    #         /* 첫 번째 meals-summary 숨기기 */
    #         .meals-summary:first-of-type {
    #             display: none !important;
    #         }
            
    #         /* 마지막 식사 요약의 마진 제거 */
    #         .meals-summary:last-child {
    #             margin-bottom: 0;
    #         }
    #         .meals-summary  {
    #             height: auto;
    #         }

    #         .meals-summary  td {
    #             display: block;
    #         }
    #     }
    #     </style>''')
    
    # 최종 HTML 생성
    final_html = html_template_start + '\n'.join(html_rows) + html_template_end
    return final_html  
    # # HTML 파일 저장
    # with open('target.html', 'w', encoding='utf-8') as f:
    #     f.write(final_html)

# if __name__ == "__main__":
#     create_html()