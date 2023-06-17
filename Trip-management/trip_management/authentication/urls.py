from django.contrib import admin
from django.urls import include, path

from .views import (ChangePassword, PasswordOtpApi, Profile,
                    ResetPassword, UserSignUp)

urlpatterns = [
    path("signup/", UserSignUp.as_view(), name="signup"),
    path("password/otp/", PasswordOtpApi.as_view(), name="password_reset"),
    path("password/new-password/", ResetPassword.as_view(), name = "set_new_password"),
    path("profile/", Profile.as_view(), name = "profile"),
    path("change-password/", ChangePassword.as_view(), name = "change_password"),
    # path("profile/delete/", DeleteProfile.as_view(), name = "delete_profile"),
]