from datetime import datetime, timedelta
from django.utils import timezone
from celery import shared_task
from django.core.mail import send_mail
from .models import Trip, TripUsers
from django.conf import settings
from authentication.models import Users
import logging
import pytz


@shared_task(name="email_reminder")
def send_trip_reminder_emails():
    """Takes date of next day and fetches all the trips of that day to send mail. Scheduled to run at 1am daily."""
    india_timezone = pytz.timezone("Asia/Kolkata")
    now = datetime.now(india_timezone)
    date_today = now.date()
    date_tomorrow = date_today + timedelta(days=1)
    trips = Trip.objects.filter(start_date__date=date_tomorrow)
    for trip in trips:
        trip_users = TripUsers.objects.filter(trip_id=trip.id, interested=True)
        for trip_user in trip_users:
            user = Users.objects.get(id=trip_user.user_id)
            subject = f"Trip Reminder: {trip.title}"
            message = f"Dear {user.username}, your trip '{trip.title}' is scheduled to start at '{trip.start_date}'."
            logging.info(
                "current processing trip user is %s, trip id is %d",
                trip_user.id,
                trip.id,
            )
            send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email])
