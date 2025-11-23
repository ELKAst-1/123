import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os
import json

class SheetsService:
    def __init__(self, sheet_id):
        self.sheet_id = sheet_id
        self.client = None
        self.sheet = None
        self.worksheet = None
        self._authenticate()
    
    def _authenticate(self):
        service_account_key = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY', '')
        
        if not service_account_key:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_KEY не найден в переменных окружения")
        
        try:
            creds_dict = json.loads(service_account_key)
        except json.JSONDecodeError as e:
            raise ValueError(f"GOOGLE_SERVICE_ACCOUNT_KEY содержит невалидный JSON: {e}")
        
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        self.client = gspread.authorize(creds)
        
        try:
            self.sheet = self.client.open_by_key(self.sheet_id)
            self.worksheet = self.sheet.sheet1
        except Exception as e:
            print(f"Ошибка при открытии таблицы: {e}")
            self.sheet = self.client.create("3D Print Requests")
            self.sheet.share('', perm_type='anyone', role='writer')
            self.worksheet = self.sheet.sheet1
            self._init_worksheet()
    
    def _init_worksheet(self):
        headers = ['ID', 'Дата', 'Имя', 'Фамилия', 'Группа', 'Цель печати', 
                   'Статус', 'Файл URL', 'File ID', 'Telegram ID', 'Username']
        self.worksheet.append_row(headers)
        self.worksheet.format('A1:K1', {'textFormat': {'bold': True}})
    
    def add_request(self, request_data):
        row = [
            request_data.get('id', ''),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            request_data.get('first_name', ''),
            request_data.get('last_name', ''),
            request_data.get('group', ''),
            request_data.get('purpose', ''),
            'В очереди',
            request_data.get('file_url', ''),
            request_data.get('file_id', ''),
            request_data.get('telegram_id', ''),
            request_data.get('username', '')
        ]
        self.worksheet.append_row(row)
        row_number = len(self.worksheet.get_all_values())
        self._update_row_color(row_number, 'white')
    
    def update_status(self, request_id, new_status):
        cell = self.worksheet.find(str(request_id))
        if cell:
            row_number = cell.row
            self.worksheet.update_cell(row_number, 7, new_status)
            
            if new_status == 'В очереди':
                self._update_row_color(row_number, 'white')
            elif new_status == 'В работе':
                self._update_row_color(row_number, 'yellow')
            elif new_status == 'Готово':
                self._update_row_color(row_number, 'red')
    
    def _update_row_color(self, row_number, color):
        color_map = {
            'white': {'red': 1, 'green': 1, 'blue': 1},
            'yellow': {'red': 1, 'green': 1, 'blue': 0},
            'red': {'red': 1, 'green': 0, 'blue': 0}
        }
        
        self.worksheet.format(f'A{row_number}:K{row_number}', {
            'backgroundColor': color_map.get(color, color_map['white'])
        })
    
    def get_all_requests(self):
        records = self.worksheet.get_all_records()
        return records
    
    def get_pending_count(self):
        records = self.get_all_requests()
        return sum(1 for r in records if r.get('Статус') == 'В очереди')
    
    def get_request_by_id(self, request_id):
        records = self.get_all_requests()
        for record in records:
            if str(record.get('ID')) == str(request_id):
                return record
        return None
