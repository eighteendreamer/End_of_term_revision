"""
MinIO 客户端工具
用于文件上传、下载、删除等操作
"""
from minio import Minio
from minio.error import S3Error
from typing import Optional, BinaryIO
import os
from datetime import timedelta


class MinIOClient:
    """MinIO客户端封装"""
    
    def __init__(
        self,
        endpoint: str = "localhost:9000",
        access_key: str = "minioadmin",
        secret_key: str = "minioadmin",
        secure: bool = False,
        bucket_name: str = "endreversion"
    ):
        """
        初始化MinIO客户端
        :param endpoint: MinIO服务地址
        :param access_key: 访问密钥
        :param secret_key: 密钥
        :param secure: 是否使用HTTPS
        :param bucket_name: 存储桶名称
        """
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        self.bucket_name = bucket_name
        
        # 确保bucket存在
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """确保bucket存在，不存在则创建"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                print(f"✓ 创建bucket: {self.bucket_name}")
            else:
                print(f"✓ Bucket已存在: {self.bucket_name}")
        except S3Error as e:
            print(f"✗ Bucket检查失败: {e}")
            raise
    
    def upload_file(
        self,
        file_data: BinaryIO,
        object_name: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """
        上传文件到MinIO
        :param file_data: 文件数据流
        :param object_name: 对象名称（路径）
        :param content_type: 内容类型
        :param metadata: 元数据
        :return: 对象路径
        """
        try:
            # 获取文件大小
            file_data.seek(0, os.SEEK_END)
            file_size = file_data.tell()
            file_data.seek(0)
            
            # 上传文件
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=file_data,
                length=file_size,
                content_type=content_type,
                metadata=metadata
            )
            
            return object_name
        except S3Error as e:
            print(f"✗ 文件上传失败: {e}")
            raise
    
    def download_file(self, object_name: str) -> bytes:
        """
        从MinIO下载文件
        :param object_name: 对象名称
        :return: 文件内容（字节）
        """
        try:
            response = self.client.get_object(self.bucket_name, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            print(f"✗ 文件下载失败: {e}")
            raise
    
    def delete_file(self, object_name: str) -> bool:
        """
        从MinIO删除文件
        :param object_name: 对象名称
        :return: 是否成功
        """
        try:
            self.client.remove_object(self.bucket_name, object_name)
            return True
        except S3Error as e:
            print(f"✗ 文件删除失败: {e}")
            return False
    
    def get_file_url(self, object_name: str, expires: int = 3600) -> str:
        """
        获取文件的预签名URL
        :param object_name: 对象名称
        :param expires: 过期时间（秒）
        :return: 预签名URL
        """
        try:
            url = self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                expires=timedelta(seconds=expires)
            )
            return url
        except S3Error as e:
            print(f"✗ 获取URL失败: {e}")
            raise
    
    def file_exists(self, object_name: str) -> bool:
        """
        检查文件是否存在
        :param object_name: 对象名称
        :return: 是否存在
        """
        try:
            self.client.stat_object(self.bucket_name, object_name)
            return True
        except S3Error:
            return False
    
    def list_files(self, prefix: str = "") -> list:
        """
        列出文件
        :param prefix: 前缀过滤
        :return: 文件列表
        """
        try:
            objects = self.client.list_objects(
                bucket_name=self.bucket_name,
                prefix=prefix,
                recursive=True
            )
            return [obj.object_name for obj in objects]
        except S3Error as e:
            print(f"✗ 列出文件失败: {e}")
            return []


# 创建全局MinIO客户端实例
minio_client = MinIOClient(
    endpoint="localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False,
    bucket_name="endreversion"
)
