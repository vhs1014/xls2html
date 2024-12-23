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
            
            self.special_handler_rules = {
                ('출발', '일정', '날짜'): self._process_multiline,
                ('가격', 'price', '원'): self._format_price_with_html,
                ('추천', '특전'): self._process_list,
                ('선택', '옵션', '투어'): self._process_multiline,
                ('안내', '참고', 'remark', '유의'): self._process_remarks,
            }

            self.max_columns = self._calculate_max_columns()

        def _calculate_max_columns(self):
            """모든 값들의 최대 컬럼 수를 계산"""
            max_cols = 1
            for key, value in self.data.items():
                if key not in self.exclude_fields and isinstance(value, str) and '||' in value:
                    cols = len([x for x in value.split('||') if x.strip()])
                    max_cols = max(max_cols, cols)
            return max_cols

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
                    padding: 15px 20px;
                }}
                .icon {{
                    margin-right: 15px;
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
                @media (max-width: 768px) {{
                    .detail-button {{
                        flex: 1 0 100%;
                        max-width: 100%;
                    }}
                }}
                .info-table {{
                    width: 100%;
                    border-collapse: separate;
                    border-spacing: 0;
                    margin: 15px 0;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    background: white;
                    font-size: 14px;
                }}

                .info-table thead {{
                    background: #f8f9fa;
                }}

                .info-table th {{
                    padding: 8px;
                    text-align: left;
                    font-weight: 600;
                    color: #344767;
                }}

                .info-table td {{
                    padding: 8px;
                    color: #4a5568;
                }}

                .info-table tbody tr:last-child td {{
                    border-bottom: none;
                }}

                .info-table tbody tr:hover {{
                    background-color: #f8fafc;
                    transition: background-color 0.2s ease;
                }}

                .info-table th:first-child,
                .info-table td:first-child {{
                    padding-left: 12px;
                }}

                .info-table th:last-child,
                .info-table td:last-child {{
                    padding-right: 12px;
                }}

                /* 반응형 테이블 스타일 */
                @media (max-width: 768px) {{
                    .info-table {{
                        display: block;
                        overflow-x: auto;
                        -webkit-overflow-scrolling: touch;
                    }}
                    
                    .info-table th,
                    .info-table td {{
                        white-space: nowrap;
                        min-width: 120px;
                    }}
                }}
            </style>
            <div class="title-section">
                <h1>{self.data.get("상품명", "")}</h1>
            </div>
            ''')
            sections.append('<div class="info-section">')
            
            # JSON의 원래 순서대로 필드 처리
            display_order = self._get_display_order()
            
            # 모든 필드를 원래 순서대로 처리
            for field in display_order:
                if field in self.data:
                    handler = self._get_handler_for_key(field)
                    sections.append(handler(self.data[field]))
            
            sections.append('</div></div>')
            
            # 일정 정보 추가
            if 'itinerary' in self.data:
                for i, day in enumerate(self.data['itinerary'], 1):
                    sections.append(self._generate_day_section(day, i))
            
            return '\n'.join(sections)

        def _format_price_with_html(self, price_str):
            if not isinstance(price_str, str):
                return f'<div class="detail">{price_str}</div>'
            prices = price_str.split('|')
            return '\n'.join([f'<div class="detail">{price.strip()}</div>' for price in prices])

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
            
            if not lines:
                return '<div class="detail">내용 없음</div>'
            
            return '<div class="detail">' + '<br>'.join(lines) + '</div>'

        def _process_list(self, text, prefix=''):
            return text.replace('* ', '')

        def _process_remarks(self, text):
            items = text.replace('* ', '').split('\r\n')
            return '\n'.join([f'<div class="detail">• {item}</div>' for item in items])

        def _process_table(self, content):
            """줄바꿈과 || 구분자가 있는 컨텐츠를 테이블로 처리"""
            rows = [row.strip() for row in re.split(r'\r\n|\n', content) if row.strip()]
            if not rows:
                return '<div class="detail">내용 없음</div>'

            table_html = ['<div class="table-container"><table class="info-table">']
            
            # 첫 번째 행은 헤더로 처리
            header = rows[0]
            header_cols = [col.strip() for col in header.split('||')]
            
            # 헤더 정보 저장 (모바일 카드 뷰에서 사용)
            headers = []
            for col in header_cols:
                headers.append(col if col.strip() else '')
            
            table_html.append('<thead><tr>')
            for col in header_cols:
                table_html.append(f'<th>{col}</th>')
            table_html.append('</tr></thead>')
            
            if len(rows) > 1:
                table_html.append('<tbody>')
                
                # 데이터 행 처리
                for row in rows[1:]:
                    cells = [cell.strip() for cell in row.split('||')]
                    
                    # 데이터 셀 개수를 헤더 개수에 맞추기
                    while len(cells) < len(headers):
                        cells.append('')
                    cells = cells[:len(headers)]  # 헤더보다 많은 셀은 제거
                    
                    # 데스크톱 뷰용 행
                    table_html.append('<tr>')
                    for i, cell in enumerate(cells):
                        cell_content = cell.replace('\n', '<br>')
                        table_html.append(f'<td data-label="{headers[i]}">{cell_content}</td>')
                    table_html.append('</tr>')
                    
                    # 모바일 카드 뷰용 요소
                    table_html.append('<tr class="mobile-card">')
                    for i, cell in enumerate(cells):
                        cell_content = cell.replace('\n', '<br>')
                        if headers[i].strip():  # 헤더가 비어있지 않은 경우만 표시
                            table_html.append(f'''
                                <td class="card-item">
                                    <div class="card-label">{headers[i]}</div>
                                    <div class="card-value">{cell_content}</div>
                                </td>
                            ''')
                    table_html.append('</tr>')
                
                table_html.append('</tbody>')
            
            table_html.append('</table></div>')
            
            # CSS 스타일 추가
            table_html.append('''
            <style>
                .table-container {
                    width: 100%;
                    overflow-x: auto;
                    margin: 1rem 0;
                }
                
                .info-table {
                    width: 100%;
                    border-collapse: separate;
                    border-spacing: 0;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    background: white;
                    font-size: 14px;
                }
                
                .info-table th {
                    background: #f8f9fa;
                    padding: 8px;
                    text-align: left;
                    font-weight: 600;
                    color: #344767;
                }
                
                .info-table td {
                    padding: 8px;
                    color: #4a5568;
                }
                
                .info-table tr:last-child td {
                    border-bottom: none;
                }
                
                .mobile-card {
                    display: none;
                }
                
                @media screen and (max-width: 768px) {
                    .info-table thead {
                        display: none;
                    }
                    
                    .info-table tr {
                        display: none;
                    }
                    
                    .info-table .mobile-card {
                        display: flex;
                        flex-direction: column;
                        background: white;
                        margin-bottom: 1rem;
                        border-radius: 8px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }
                    
                    .info-table .card-item {
                        display: flex;
                        padding: 12px;
                    }
                    
                    .info-table .card-label {
                        font-weight: 600;
                        color: #344767;
                        width: 35%;
                        padding-right: 12px;
                    }
                    
                    .info-table .card-value {
                        color: #4a5568;
                        width: 65%;
                    }
                    
                    .info-table .mobile-card:last-child {
                        margin-bottom: 0;
                    }
                    
                    .info-table .card-item:last-child {
                        border-bottom: none;
                    }
                }
            </style>
            ''')
            
            return '\n'.join(table_html)

        def _generate_schedule_items(self, location_data):
            icon = "flight" if "flight" in location_data else "place"
            
            schedule_html = []
            if 'schedule' in location_data:
                for item in location_data['schedule']:
                    time = item.get('time', '')
                    for detail in item.get('details', []):
                        if time:
                            schedule_html.append(f'<div class="detail">{detail} ({time})</div>')
                        else:
                            schedule_html.append(f'<div class="detail">{detail}</div>')

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