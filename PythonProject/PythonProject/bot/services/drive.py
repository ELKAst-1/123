from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import os
import json
import io

class DriveService:
    def __init__(self, folder_id):
        self.folder_id = folder_id
        self.service = None
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
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/drive.file'
        ]
        
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        self.service = build('drive', 'v3', credentials=creds)
    
    def upload_file(self, file_path, file_name):
        file_metadata = {
            'name': file_name,
            'parents': [self.folder_id]
        }
        
        media = MediaFileUpload(file_path, resumable=True)
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        file_id = file.get('id')
        
        self.service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
        
        return file.get('webViewLink'), file_id
    
    def delete_file(self, file_id):
        try:
            self.service.files().delete(fileId=file_id).execute()
            return True
        except Exception as e:
            print(f"Ошибка при удалении файла {file_id}: {e}")
            return False
    
    def list_files_in_folder(self):
        query = f"'{self.folder_id}' in parents and trashed=false"
        results = self.service.files().list(
            q=query,
            fields="files(id, name, createdTime, webViewLink)"
        ).execute()
        return results.get('files', [])
    
    def get_file_info(self, file_id):
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, createdTime, webViewLink'
            ).execute()
            return file
        except Exception as e:
            print(f"Ошибка при получении информации о файле {file_id}: {e}")
            return None
