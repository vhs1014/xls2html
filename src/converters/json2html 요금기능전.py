import json
from datetime import datetime, timedelta

def generate_itinerary_html(json_data):
    class ItineraryGenerator:
        def __init__(self, data):
            self.data = data
            
            self.icon_rules = {
                ('일정', '날짜'): 'calendar_month',
                ('가격', 'price', '원'): 'payments',
                ('항공', '비행', '출발', '도착', '수속', '탑승'): 'flight',
                ('포함',): 'check_circle',
                ('불포함',): 'remove_circle',
                ('쇼핑', '상점', '센터'): 'shopping_bag',
                ('추천', '특전'): 'star',
                ('선택', '옵션', '투어'): 'tour',
                ('안내', '참고', 'remark', '유의'): 'info',
                ('호텔', '숙박'): 'hotel',
                ('교통', '차량'): 'directions_car',
                ('식사', '음식'): 'restaurant',
                ('관광', '투어'): 'tour',
                ('보험', '보장'): 'health_and_safety',
                ('할인', '혜택'): 'local_offer',
                ('비자', '여권'): 'badge',
                ('가이드', '인솔'): 'person',
                ('기타', '일정'): 'schedule'
            }
            
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
            key_lower = key.lower()
            
            # 기존 규칙으로 매칭 시도
            for keywords, icon in self.icon_rules.items():
                if any(keyword in key_lower for keyword in keywords):
                    return icon
            
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
                return self.default_icon_rules['일반']  # 가장 기본적인 아이콘

        def _get_handler_for_key(self, key):
            """키워드를 분석하여 적절한 핸들러 반환"""
            key_lower = key.lower()
            
            # 기존 핸들러 매핑 시도
            for keywords, handler in self.special_handler_rules.items():
                if any(keyword in key_lower for keyword in keywords):
                    return handler
            
            # 매칭되지 않은 경우 컨텐츠 형식에 따른 기본 핸들러 결정
            def default_handler(content):
                if isinstance(content, str):
                    if '\n' in content or '\r' in content:
                        return self._process_multiline(content)
                    elif ',' in content:
                        return self._process_list(content)
                    else:
                        return f'<div class="detail">{content}</div>'
                return f'<div class="detail">{str(content)}</div>'
            
            return default_handler

        def _create_info_section(self, key, content):
            # file_url 특별 처리
            if key == 'file_url':
                return f'''
                <div class="info-item">
                    <div class="icon">
                        <span class="material-icons-round">download</span>
                    </div>
                    <div class="content">
                        <div class="title-with-content">
                            <span>첨부파일</span>
                            <a href="{content}" class="download-button">
                                일정표 다운로드
                            </a>
                        </div>
                    </div>
                </div>
                '''

            icon = self._get_icon_for_key(key)
            display_key = key.replace('REMARK', '안내사항')

            # 컨텐츠 처리
            if isinstance(content, str):
                if '||' in content:
                    items = [item.strip() for item in content.split('||') if item.strip()]
                    if items:
                        buttons_html = []
                        total_items = len(items)
                        
                        for i, item in enumerate(items):
                            if '\n' in item:
                                formatted_item = item.replace('\n', '<br>')
                            else:
                                formatted_item = item
                            
                            # 3개 이상일 때 나머지 아이템들의 너비 계산
                            if total_items > 3 and i >= 3:
                                width_class = f'full-width-{total_items - 3}'
                            else:
                                width_class = ''
                            
                            buttons_html.append(
                                f'<div class="detail-button {width_class}">{formatted_item}</div>'
                            )
                        content_html = f'<div class="detail-buttons-container">{" ".join(buttons_html)}</div>'
                    else:
                        content_html = f'<div class="detail">{content}</div>'
                elif '\n' in content or '\r' in content:
                    content_html = self._process_multiline(content)
                else:
                    content_html = f'<div class="detail">{str(content).replace("* ", "")}</div>'
            else:
                content_html = f'<div class="detail">{str(content)}</div>'

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
                .detail-buttons-container {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 10px;
                    width: 100%;
                    margin-top: 5px;
                    padding-left: 2px;
                }}
                .detail-button {{
                    flex: 1 0 calc((100% - 100px) / 3);
                    max-width: calc((100% - 100px) / 3);
                    min-width: calc((100% - 100px) / 3);
                    text-align: left;
                    padding: 10px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    background-color: #f8f9fa;
                    cursor: pointer;
                    white-space: normal;
                    overflow-wrap: break-word;
                    height: 100%;
                    display: flex;
                    align-items: center;
                    font-size: 14px;
                }}
                .detail-button.full-width-1 {{
                    flex: 1 0 95%;
                    max-width: 95%;
                    min-width: 95%;
                }}
                .detail-button.full-width-2 {{
                    flex: 1 0 calc((100% - 90px) / 2);
                    max-width: calc((100% - 90px) / 2);
                    min-width: calc((100% - 90px) / 2);
                }}
                .detail-button:hover {{
                    background-color: #e9ecef;
                }}
                @media (max-width: 768px) {{
                    .detail-button {{
                        flex: 1 0 100%;
                        max-width: 100%;
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
                    sections.append(self._create_info_section(field, self.data[field]))
            
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
            return '\n'.join([f'<div class="detail">{line.strip()}</div>' 
                             for line in text.split('\r\n')])

        def _process_list(self, text, prefix=''):
            return text.replace('* ', '')

        def _process_remarks(self, text):
            items = text.replace('* ', '').split('\r\n')
            return '\n'.join([f'<div class="detail">• {item}</div>' for item in items])

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
            meals_html = self._generate_meals_section(day_data.get('meals', {}))

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