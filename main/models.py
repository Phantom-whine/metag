from django.db import models
import uuid
from django.contrib.auth import get_user_model

User = get_user_model()

class Post(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    content = models.TextField()  # HTML content
    created = models.DateTimeField(auto_now_add=True)
    length = models.PositiveIntegerField()
    edited = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        self.length = len(self.content)
        super().save(*args, **kwargs)