"""通用能力路由：图片/文件上传。"""
from django.urls import path

from . import views

urlpatterns = [
    path("upload-image/", views.upload_image, name="common-upload-image"),
    path("upload/", views.upload_file, name="common-upload-file"),
]