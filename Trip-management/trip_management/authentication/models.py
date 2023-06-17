from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser


class Department(models.Model):
    """Stores all the available departments"""

    department_name = models.CharField(max_length=50)

    def __str__(self):
        return self.department_name


class BaseModel(models.Model):
    """Defines basic fields to be included in each and every class without reflecting in database."""

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        abstract = True


class Users(AbstractUser, BaseModel):
    """Stores user's information"""

    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="departments"
    )
    access_token = models.CharField(max_length=255, null=True, blank=True)
    flag = models.BooleanField(default=False)
    splitwise_id = models.CharField(max_length=255, null=True, blank=True)
