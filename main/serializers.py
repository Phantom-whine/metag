from rest_framework import serializers
from .models import Post
from django.utils import timezone

class PostSerializer(serializers.ModelSerializer):
    time_ago = serializers.SerializerMethodField()
    class Meta:
        model = Post
        fields = ['id', 'title', 'created', 'content', 'user', 'length', 'time_ago', 'edited']
        read_only_fields = ['user', 'created', 'length']

    def get_time_ago(self, obj):
        now = timezone.now()
        delta = now - obj.created
        seconds = delta.total_seconds()

        if seconds < 60:
            return "just now"
        elif seconds < 3600:  # 1 hour
            minutes = int(seconds // 60)
            return f"{minutes} mins ago"
        elif seconds < 86400:  # 1 day
            hours = int(seconds // 3600)
            return f"{hours} hours ago"
        elif seconds < 2592000:  # 30 days
            days = int(seconds // 86400)
            return f"{days} days ago"
        elif seconds < 31536000:  # 365 days
            months = int(seconds // 2592000)
            return f"{months} months ago"
        else:
            years = int(seconds // 31536000)
            return f"{years} years ago"
