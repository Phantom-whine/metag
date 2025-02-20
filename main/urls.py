# urls.py
from django.urls import path
from .views import (post_get_delete, post_create_text, post_create_url,
                     post_edit, post_edit_ai, post_create_youtube,
                   regenerate_post, get_topics, post_list, post_save_editor)

urlpatterns = [
    path('posts/<uuid:pk>/', post_get_delete, name='post-detail'),
    path('posts/create-text/', post_create_text, name='post-create'),
    path('posts/edit/<uuid:id>/', post_edit, name='post-edit'),
    path('posts/create-url/', post_create_url, name='post-url'),
    path('posts/create-youtube/', post_create_youtube, name='post-youtube'),
    path('posts/regenerate/<uuid:pk>/', regenerate_post, name='post-regenerate'),
    path('posts/topics/', get_topics, name='post-topics'),
    path('posts/', post_list, name='post-list'),
    path('posts/save-editor/', post_save_editor, name='post-save'),
    path('posts/edit-ai/', post_edit_ai, name='post-edit-ai'),
]