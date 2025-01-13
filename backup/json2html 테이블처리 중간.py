import json
from datetime import datetime, timedelta
import re

def generate_itinerary_html(json_data):
    class ItineraryGenerator:
        def __init__(self, data):
            self.data = data
            
            # 아이콘 규칙을 우선순위 순서대로 정의
            self.icon_rules = [

                # 일반 매칭 규칙
                {
                    "keywords": ["일정", "날짜"],
                    "icon": "calendar_month"
                },
                {
                    "keywords": ["가격", "price", "원"],
                    "icon": "payments"
                },
                {
                    "keywords": ["항공", "비행", "출발", "도착", "수속", "탑승"],
                    "icon": "flight"
                },
                {
                    "keywords": ["포함"],
                    "icon": "check_circle"
                },
                {
                    "keywords": ["불포함"],
                    "icon": "remove_circle"
                },
                {
                    "keywords": ["쇼핑", "상점", "센터"],
                    "icon": "shopping_bag"
                },
                {
                    "keywords": ["추천", "특전"],
                    "icon": "star"
                },
                {
                    "keywords": ["선택", "옵션", "투어"],
                    "icon": "tour"
                },
                {
                    "keywords": ["안내", "참고", "remark", "유의"],
                    "icon": "info"
                },
                {
                    "keywords": ["호텔", "숙박"],
                    "icon": "hotel"
                },
                {
                    "keywords": ["교통", "차량"],
                    "icon": "directions_car"
                },
                {
                    "keywords": ["식사", "음식"],
                    "icon": "restaurant"
                },
                {
                    "keywords": ["관광", "투어"],
                    "icon": "tour"
                },
                {
                    "keywords": ["보험", "보장"],
                    "icon": "health_and_safety"
                },
                {
                    "keywords": ["할인", "혜택"],
                    "icon": "local_offer"
                },
                {
                    "keywords": ["비자", "여권"],
                    "icon": "badge"
                },
                {
                    "keywords": ["가이드", "인솔"],
                    "icon": "person"
                },
                {
                    "keywords": ["기타", "일정"],
                    "icon": "schedule"
                }
            ]
            
            self.default_icon_rules = {
                '기타': 'more_horiz',
                '일반': 'article',
                '정보': 'info_outline',
                '기본': 'label_important'
            }
            
            self.exclude_fields = {'locations', 'places', 'itinerary'}

        def _get_display_order(self):
            """JSON의 원래 키 순서를 완벽하게 유지하면서 일부 필드만 우선순위 부여"""
            # 원본 순서 유지를 위해 OrderedDict 사용
            original_order = list(self.data.keys())
            
            # 제외할 필드 제거
            fields = [k for k in original_order if k not in self.exclude_fields]

            result = []
            # 나머지 필드들은 JSON의 원래 순서 그대로 추가
            result.extend(fields)
            
            return result

        def _get_icon_for_key(self, key):
            """키워드를 분석하여 적절한 아이콘 반환"""
            # '/'가 포함된 경우 기본 아이콘 사용
            if '/' in key:
                return self.default_icon_rules['일반']
                
            key_lower = key.lower().strip()
            
            # 기존 규칙으로 매칭 시도
            for rule in self.icon_rules:
                if any(keyword in key_lower for keyword in rule["keywords"]):
                    return rule["icon"]
            
            # 매칭되지 않은 경우 키워드 분석
            if any(char.isdigit() for char in key):
                return 'format_list_numbered'  # 숫자가 포함된 경우
            elif len(key) <= 2:
                return 'label'  # 짧은 키워드
            elif '기타' in key_lower or '그외' in key_lower:
                return self.default_icon_rules['기타']
            elif '정보' in key_lower or '내용' in key_lower:
                return self.default_icon_rules['정보']
            elif any(word in key_lower for word in ['중요', '필수', '주의']):
                return self.default_icon_rules['기본']
            else:
                return self.default_icon_rules['일반']

        def _get_handler_for_key(self, key):
            """키에 따른 적절한 핸들러 함수 반환"""
            return lambda content: self._create_info_section(key, content)

        def _create_info_section(self, key, content):
            # file_url 특별 처리
            if key == 'file_url':
                return f'''
                <div class="info-item">
                    <div class="icon">
                        <span class="material-icons-round">link</span>
                    </div>
                    <div class="content">
                        <div class="title">파일 URL</div>
                        <div class="detail">
                            <a href="{content}" target="_blank" rel="noopener noreferrer" class="download-button">일정표 다운로드</a>
                        </div>
                    </div>
                </div>
                '''

            icon = self._get_icon_for_key(key)
            display_key = key.replace('REMARK', '안내사항')

            content_str = str(content) if not isinstance(content, str) else content
            
            # \n과 ||이 모두 있는지 확인
            has_newline = '\n' in content_str or '\r' in content_str
            has_valid_separator = False
            # print(content_str)
            if '||' in content_str:
                # 실제 데이터가 있는 ||인지 확인
                rows = content_str.split('\n')
                for row in rows:
                    cells = [cell.strip() for cell in row.split('||')]
                    if len([cell for cell in cells if cell.strip()]) > 1:
                        has_valid_separator = True
                        break
            
            # \n과 데이터가 있는 ||이 모두 있으면 테이블로 처리
            if has_newline and has_valid_separator:
                content_html = self._process_table(content_str)
            else:
                # \n만 있고 데이터가 있는 ||이 없으면 멀티라인으로 처리
                content_html = self._process_multiline(content_str)

            return f'''
            <div class="info-item">
                <div class="icon">
                    <span class="material-icons-round">{icon}</span>
                </div>
                <div class="content">
                    <div class="title">{display_key}</div>
                    {content_html}
                </div>
            </div>
            '''

        def generate_html(self):
            sections = ['<div class="product-info">']
            sections.append(f'''
            <style>
                .info-item {{
                    display: flex;
                    align-items: flex-start;
                    padding: 10px;
                }}
                .icon {{
                    margin-right: 10px;
                }}
                .content {{
                    flex: 1;
                }}
                .title {{
                    font-weight: bold;
                    margin-bottom: 10px;
                }}
                .title-with-content {{
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    font-weight: bold;
                }}
                .detail {{
                    color: #666;
                    padding-left: 2px;
                }}

                /* 테이블 스타일 */
                .table-container {{
                    width: 100%;
                    margin: 0.5rem 0;
                }}
                
                .info-table {{
                    width: 100%;
                    border-collapse: separate;
                    border-spacing: 0;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    background: white;
                    font-size: 14px;
                    table-layout: fixed;
                }}
                
                .info-table td {{
                    padding: 12px 8px;
                    color: #4a5568;
                    word-break: keep-all;
                    white-space: normal;
                    line-height: 1.4;
                    vertical-align: top;
                }}
                
                .info-table tr:first-child td {{
                    font-weight: 600;
                    color: #344767;
                    background: #f8f9fa;
                }}
                
                @media screen and (max-width: 768px) {{
                    .table-container {{
                        margin: 0;
                    }}
                    
                    .info-table {{
                        box-shadow: none;
                    }}
                    
                    .info-table tbody {{
                        display: flex;
                        flex-direction: column;
                        gap: 12px;
                        padding: 12px 8px;
                    }}
                    
                    .info-table tr {{
                        display: flex;
                        flex-direction: column;
                        background: white;
                        border-radius: 8px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        margin: 0;
                        overflow: hidden;
                    }}
                    
                    .info-table tr:first-child {{
                        background: white;
                    }}
                    
                    .info-table tr:first-child td {{
                        background: none;
                    }}
                    
                    .info-table td {{
                        display: flex;
                        padding: 12px;
                        align-items: flex-start;
                        border-bottom: 1px solid #f0f0f0;
                        line-height: 1.4;
                    }}
                    
                    .info-table td:last-child {{
                        border-bottom: none;
                    }}
                    

                }}
            </style>
            <div class="title-section">
                <h1>{self.data.get("상품명", "")}</h1>
            </div>
            ''')
            sections.append('<div class="info-section">')
            
            # 제목없는 테이플 처리를 위한 구문 
            # value를 ||로 분리해서 첫배열 빼고 2개이상 빈값이 아닌 데이터를 추출 
            # 그런 데이터가 연속 두개 이상 나오은 key값을 배열로 추출 해서 주요정보 라는 key 의 값으로 적용
            # 훙 _process_table 함수로 전달
            display_order = self._get_display_order()

            tablekeys = []
            key_groups = []  # 연속된 키들을 그룹으로 저장
            current_group = []
            
            sorted_keys = sorted([key for key in self.data.keys() if key not in self.exclude_fields], 
                               key=lambda x: int(x.split('_')[-1]) if x.split('_')[-1].isdigit() else 0)
            
            for key in sorted_keys:
                value = self.data[key]
                if isinstance(value, str) and '||' in value:
                    cols = [x.strip() for x in value.split('||')[1:] if x.strip()]
                    if len(cols) >= 2:
                        current_group.append(key)
                    else:
                        if len(current_group) >= 2:
                            key_groups.append(current_group)
                        current_group = []
                else:
                    if len(current_group) >= 2:
                        key_groups.append(current_group)
                    current_group = []
            
            # 마지막 그룹 처리
            if len(current_group) >= 2:
                key_groups.append(current_group)
            
            # 결과 데이터 구조화
            formatted_entries = []
            for group in key_groups:
                for key in group:
                    formatted_entries.append(f"{key}||{self.data[key]}")
            
            result_data = {"주요정보": "\r\n".join(formatted_entries)}
            print(result_data)
            # print(key_groups[0])
            
            # 모든 필드를 원래 순서대로 처리
            for field in display_order:
                if field in self.data:
                    if key_groups and field in key_groups[0]:
                        handler = self._get_handler_for_key('주요정보')
                        sections.append(handler(result_data['주요정보']))
                        for key in key_groups[0]:
                            self.data.pop(key, None)
                    else:    
                        handler = self._get_handler_for_key(field)
                        sections.append(handler(self.data[field]))
            
            sections.append('</div></div>')
            
            # 일정 정보 추가
            if 'itinerary' in self.data:
                for i, day in enumerate(self.data['itinerary'], 1):
                    sections.append(self._generate_day_section(day, i))
            
            return '\n'.join(sections)

        def _process_multiline(self, text):
            lines = []
            for line in text.split('\n'):
                if '||' in line:
                    # || 구분자로 나누고 빈 값이 아닌 것들만 추가
                    parts = [part.strip() for part in line.split('||')]
                    non_empty_parts = [part for part in parts if part]
                    if non_empty_parts:
                        lines.extend(non_empty_parts)
                else:
                    # || 구분자가 없는 경우 라인 전체를 추가
                    line = line.strip()
                    if line:
                        lines.append(line)
            
            # if not lines:
            #     return '<div class="detail">내용 없음</div>'
            
            return '<div class="detail">' + '<br>'.join(lines) + '</div>'

        def _process_table(self, content):
            """줄바꿈과 || 구분자가 있는 컨텐츠를 테이블로 처리"""
            rows = [row.strip() for row in re.split(r'\r\n|\n', content) if row.strip()]
            # if not rows:
            #     return '<div class="detail">내용 없음</div>'

            table_html = ['<div class="table-container"><table class="info-table"><tbody>']
            
            def process_row(cells, is_header=False):
                table_html.append('<tr>')
                current_colspan = 1
                prev_td_index = -1
                
                for j, cell in enumerate(cells):
                    cell_content = cell if is_header else cell.replace('\n', '<br>')
                    if not cell_content:
                        if prev_td_index >= 0:
                            current_colspan += 1
                            table_html[prev_td_index] = table_html[prev_td_index].replace('<td', f'<td colspan="{current_colspan}"')
                    else:
                        current_colspan = 1
                        data_label = f' data-label="{labels[j]}"' if not is_header else ''
                        cell_html = f'<td{data_label}>{cell_content}</td>'
                        table_html.append(cell_html)
                        prev_td_index = len(table_html) - 1
                table_html.append('</tr>')
            
            # 모든 행을 동일하게 처리
            for i, row in enumerate(rows):
                cells = [cell.strip() for cell in row.split('||')]
                
                # 첫 번째 행의 셀을 레이블로 저장
                if i == 0:
                    labels = cells
                    process_row(cells, is_header=True)
                else:
                    # 데이터 셀 개수를 첫 번째 행 개수에 맞추기
                    while len(cells) < len(labels):
                        cells.append('')
                    cells = cells[:len(labels)]  # 첫 번째 행보다 많은 셀은 제거
                    process_row(cells)
            
            table_html.append('</tbody></table></div>')
            return '\n'.join(table_html)

        def is_valid_flight_number(self, flight_str):
            if not flight_str:
                return False
            return bool(re.match(r'^[A-Z]{2}\d+$', flight_str.strip()))

        def _process_schedule(self, schedule):
            """스케줄 정보를 HTML로 변환"""
            schedule_html = []
            for item in schedule:
                time = item.get('time', '')
                flight = item.get('flight', '')
                details = item.get('details', [])
                
                details_html = []
                for detail in details:
                    detail_text = detail
                    if flight and time:
                        detail_text = f"{detail} (<strong>{flight}</strong>, {time})"
                    elif flight:
                        detail_text = f"{detail} (<strong>{flight}</strong>)"
                    elif time:
                        detail_text = f"{detail} ({time})"
                    details_html.append(f'<div class="detail-row"><span class="detail-text">{detail_text}</span></div>')
                
                details_html = ''.join(details_html)
                schedule_html.append(f'<tr><td class="detail">{details_html}</td></tr>')
            
            return '\n'.join(schedule_html)

        def _generate_schedule_items(self, location_data):
            icon = "flight" if any(self.is_valid_flight_number(item.get('flight', '')) for item in location_data.get('schedule', [])) else "place"
            
            schedule_html = []
            if 'schedule' in location_data:
                schedule_html.append('<table class="schedule-table">')
                schedule_html.append('<tbody>')
                schedule_html.append(self._process_schedule(location_data['schedule']))
                schedule_html.append('</tbody>')
                schedule_html.append('</table>')
            
            return f'''
            <div class="schedule-item">
                <span class="icon">
                    <span class="material-icons-round">{icon}</span>
                </span>
                <div>
                    <div class="location">{location_data['place']}</div>
                    {''.join(schedule_html)}
                </div>
            </div>
            '''

        def _generate_meals_section(self, meals):
            if not meals:
                return ''
            
            meal_items = []
            for meal in meals:
                if meal.strip():  # 빈 값이 아닌 경우만 추가
                    meal_items.append(f'<span class="meal-item">{meal}</span>')
            
            if not meal_items:  # 모든 값이 빈 값인 경우 빈 문자열 반환
                return ''

            return f'''
            <div class="meals">
                <div class="meal-info">
                    <span class="icon"><span class="material-icons-round">restaurant</span></span>
                    {' '.join(meal_items)}
                </div>
            </div>
            '''

                
        def _generate_day_section(self, day_data, day_num):

            locations_html = '\n'.join(self._generate_schedule_items(location) 
                                     for location in day_data['locations'])
            meals_html = self._generate_meals_section(day_data.get('meals', []))

            return f'''
            <div id="day{day_num}" class="day-section">
                <div class="day-title">
                    <span>{day_num}일차 </span>
                    <span class="material-icons-round toggle-icon">expand_more</span>
                </div>
                <div class="day-content">
                    {locations_html}
                    {meals_html}
                </div>
            </div>
            '''

    # ItineraryGenerator 인스턴스 생성 및 HTML 생성
    generator = ItineraryGenerator(json_data)
    
    with open('./templates/template.html', 'r', encoding='utf-8') as f:
        template = f.read()
    
    html_content = generator.generate_html()
    template = template.replace('{{content}}', html_content)
    
    return template 