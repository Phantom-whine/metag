from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser) :
    email = models.EmailField(unique=True)
    fullname = models.CharField(max_length=500)
    profile = models.URLField(max_length=2000, null=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f'Account for - {self.email}'
