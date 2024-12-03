# utils/s3_uploader.py

import boto3
import os
from datetime import datetime
import uuid
from botocore.client import Config
from typing import BinaryIO

class S3FileUploader:
    def __init__(self):
        self.endpoint = "https://kr.object.iwinv.kr"
        self.access_key = 'VOIMAN28COSLO9J3HZJW'
        self.secret_key = 'MyvRsRvchNIMBS97XPq2fDIlaKlGhz8JA1K7FdLZ'
        self.bucket_name = 'itinerary'
        
        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=Config(signature_version='s3v4'),
            region_name='auto'
        )

    def generate_unique_path(self, original_filename: str) -> str:
        """시간 기반의 유니크한 파일 경로 생성"""
        now = datetime.now()
        
        # 년_월_일 형식의 단일 폴더명 생성
        date_folder = now.strftime('%Y_%m_%d')
        
        # 파일명 생성 (시간_UUID)
        timestamp = now.strftime('%H%M%S_%f')
        unique_id = str(uuid.uuid4())[:8]
        _, ext = os.path.splitext(original_filename)
        
        filename = f"{timestamp}_{unique_id}{ext}"
        
        # 최종 경로 (단일 폴더 구조)
        return f"{date_folder}/{filename}"

    def upload_file(self, file_obj: BinaryIO, original_filename: str) -> dict:
        try:
            #  파일 포인터를 처음으로 되돌림
            file_obj.seek(0)
            file_path = self.generate_unique_path(original_filename)
            
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                file_path,
                ExtraArgs={
                    'ContentType': self._get_content_type(original_filename),
                    'Metadata': {
                        'upload_date': datetime.now().strftime('%Y-%m-%d'),
                        'file_type': 'excel'
                    }
                }
            )
            
            file_url = f"{self.endpoint}/{self.bucket_name}/{file_path}"
            
            return {
                'status': 'success',
                'file_path': file_path,
                'file_url': file_url,
                'original_filename': original_filename
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }

    def _get_content_type(self, filename: str) -> str:
        content_types = {
            # '.jpg': 'image/jpeg',
            # '.jpeg': 'image/jpeg',
            # '.png': 'image/png',
            # '.gif': 'image/gif',
            # '.pdf': 'application/pdf',
            # '.doc': 'application/msword',
            # '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        
        _, ext = os.path.splitext(filename.lower())
        return content_types.get(ext, 'application/octet-stream')
    
    
    {
          "index": 59985,
          "name": "방콕",
          "iata_code": "BKK",
          "aliases": [
            "방콕", "bangkok", "bkk", "방콬", "방꼭", "방꽁", "방꾹",
            "수완나품", "수완나폼", "수완나붐", "수완나품공항",
            "suvarnabhumi", "수완나부미", "수완나프미",
            "방케", "방쾍", "방콕시티", "방곡", "방꺽"
          ],
          "related_keywords": [
            "카오산로드", "씨암", "아속", "짜뚜짝", "터미널21",
            "왓프라깨우", "왓아룬", "아시아티크", "수쿰빗", "프롬퐁"
          ],
          "full_name": "방콕(수완나품)",
          "airport_name": "수완나품 국제공항"
        },
    
    