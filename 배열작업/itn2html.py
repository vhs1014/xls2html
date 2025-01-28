import json
from datetime import datetime, timedelta
import re

__all__ = ['generate_itinerary_html', 'ItineraryHtmlGenerator']

def generate_itinerary_html(data: dict, head_html: str = '') -> str:
    """여행 일정 데이터를 HTML로 변환"""
    generator = ItineraryHtmlGenerator(data)
    html_content = generator.generate_html(head_html)
    
    with open('./templates/template.html', 'r', encoding='utf-8') as f:
        template = f.read()
    
    template = template.replace('{{content}}', html_content)
    return template

class ItineraryHtmlGenerator:
    def __init__(self, data):
        self.data = data
        self.exclude_fields = {'locations', 'places', 'itinerary', '출발월'}
        
    def generate_html(self, head_html: str = '') -> str:
        sections = []
        
        # 상품명 섹션 (최상위 레벨)
        # if "상품명" in self.data:
        #     sections.append(f'''
        #     <div class="title-section">
        #         <h1>{self.data["상품명"]}</h1>
        #     </div>
        #     ''')
        
        # # product-info 섹션 시작
        # sections.append('<div class="product-info">')
        
        # # 정보 섹션
        # sections.append('<div class="info-section">')
        if head_html:
            sections.append(head_html)
        # sections.append('</div>')  # info-section 종료
        
        # 일정 정보 추가
        if 'itinerary' in self.data:
            sections.append('<div class="itinerary-section">')
            for i, day in enumerate(self.data['itinerary'], 1):
                sections.append(self._generate_day_section(day, i))
            sections.append('</div>')
        
        # sections.append('</div>')  # product-info 종료
        
        return '\n'.join(sections)

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

    def _generate_schedule_items(self, location_data):
        icon = "flight" if any(self.is_valid_flight_number(item.get('flight', '')) 
                             for item in location_data.get('schedule', [])) else "place"
        
        schedule_html = []
        # if 'schedule' in location_data:
        #     schedule_html.append('<table class="schedule-table">')
        #     schedule_html.append('<tbody>')
        #     schedule_html.append(self._process_schedule(location_data['schedule']))
        #     schedule_html.append('</tbody>')
        #     schedule_html.append('</table>')
        if 'schedule' in location_data:
            schedule_html.append('<sapn>')
            schedule_html.append(self._process_schedule(location_data['schedule']))
            schedule_html.append('<span>')
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

    def _process_schedule(self, schedule):
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

    def _generate_meals_section(self, meals):
        if not meals:
            return ''
        
        meal_items = []
        for meal in meals:
            if meal.strip():
                meal_items.append(f'<span class="meal-item">{meal}</span>')
        
        if not meal_items:
            return ''

        return f'''
        <div class="meals">
            <div class="meal-info">
                <span class="icon"><span class="material-icons-round">restaurant</span></span>
                {' '.join(meal_items)}
            </div>
        </div>
        '''

    def is_valid_flight_number(self, flight_str):
        if not flight_str:
            return False
        return bool(re.match(r'^[A-Z]{2}\d+$', flight_str.strip())) 