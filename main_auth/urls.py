from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

urlpatterns = [
    path("continue/", views.continue_with_google),
    path("me/", views.get_details),
    path("refresh/", TokenRefreshView.as_view()),
    path("verify/", TokenVerifyView.as_view()),
    path('set/', views.set_detail),
    path('delete-account/', views.delete_account)
]
