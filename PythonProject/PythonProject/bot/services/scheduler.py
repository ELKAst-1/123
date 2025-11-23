from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import os
import shutil

class SchedulerService:
    def __init__(self, sheets_service, drive_service):
        self.scheduler = BackgroundScheduler()
        self.sheets_service = sheets_service
        self.drive_service = drive_service
    
    def start(self):
        self.scheduler.add_job(
            self.delete_old_files,
            CronTrigger(hour=0, minute=0),
            id='delete_old_files',
            replace_existing=True
        )
        
        self.scheduler.add_job(
            self.create_weekly_backup,
            CronTrigger(day_of_week='sun', hour=23, minute=0),
            id='weekly_backup',
            replace_existing=True
        )
        
        self.scheduler.add_job(
            self.delete_old_backups,
            CronTrigger(day_of_week='sun', hour=23, minute=30),
            id='delete_old_backups',
            replace_existing=True
        )
        
        self.scheduler.start()
    
    def delete_old_files(self):
        try:
            requests = self.sheets_service.get_all_requests()
            one_week_ago = datetime.now() - timedelta(days=7)
            
            for request in requests:
                if request.get('Статус') == 'Готово':
                    date_str = request.get('Дата', '')
                    try:
                        request_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        if request_date < one_week_ago:
                            file_id = request.get('File ID', '')
                            if file_id:
                                self.drive_service.delete_file(file_id)
                                print(f"Удален файл {file_id} для заявки {request.get('ID')}")
                    except ValueError:
                        continue
        except Exception as e:
            print(f"Ошибка при удалении старых файлов: {e}")
    
    def create_weekly_backup(self):
        try:
            backup_dir = 'backups'
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f'{backup_dir}/backup_{timestamp}.csv'
            
            requests = self.sheets_service.get_all_requests()
            
            import csv
            with open(backup_filename, 'w', newline='', encoding='utf-8') as f:
                if requests:
                    writer = csv.DictWriter(f, fieldnames=requests[0].keys())
                    writer.writeheader()
                    writer.writerows(requests)
            
            print(f"Создан бэкап: {backup_filename}")
            
        except Exception as e:
            print(f"Ошибка при создании бэкапа: {e}")
    
    def delete_old_backups(self):
        try:
            backup_dir = 'backups'
            if not os.path.exists(backup_dir):
                return
            
            two_weeks_ago = datetime.now() - timedelta(weeks=2)
            
            for filename in os.listdir(backup_dir):
                filepath = os.path.join(backup_dir, filename)
                if os.path.isfile(filepath):
                    file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if file_time < two_weeks_ago:
                        os.remove(filepath)
                        print(f"Удален старый бэкап: {filename}")
                        
        except Exception as e:
            print(f"Ошибка при удалении старых бэкапов: {e}")
    
    def stop(self):
        self.scheduler.shutdown()
