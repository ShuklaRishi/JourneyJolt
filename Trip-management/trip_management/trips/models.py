from django.db import models

from authentication.models import Users, Department, BaseModel


# Create your models here.
class Trip(BaseModel):
    """Stores trip details."""
    departments = models.ManyToManyField(Department, related_name="trips")
    users = models.ManyToManyField(Users, through="TripUsers")
    title = models.CharField(max_length=300)
    description = models.TextField(max_length=700)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    location = models.JSONField()
    splitwise_group = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "trips"
        db_table = "trips"


class Attachments(models.Model):
    """Connected to trip for storing trip's attachments"""
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="attachments")
    attachment = models.FileField(upload_to="uploads/")

    class Meta:
        verbose_name = "attachments"
        db_table = "attachments"


class TripUsers(models.Model):
    """Stores users interested and not interested for a trip."""
    id = models.AutoField(primary_key=True)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="trip")
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name="user_trip")
    interested = models.BooleanField(default= True)

    class Meta:
        unique_together = (("user", "trip"),)
        verbose_name = "trip users"
        db_table = "trip_users"
