from datetime import datetime
from .models import Trip, Attachments, TripUsers
from authentication.models import Users, Department
from rest_framework import serializers


class AttachmentSerializer(serializers.ModelSerializer):
    """gets attachments and trip id for adding attachment to trip"""
    class Meta:
        model = Attachments
        fields = ("id", "attachment", "trip")


class TripSerializer(serializers.ModelSerializer):
    """Gets trip data to perform validation checks and trip creation"""
    files = serializers.ListField(
        child=serializers.FileField(allow_empty_file=True, use_url=False),
        write_only=True,
    )
    departments = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), many=True
    )

    class Meta:
        model = Trip
        fields = (
            "id",
            "title",
            "description",
            "start_date",
            "end_date",
            "location",
            "departments",
            "users",
            "files",
        )
        read_only_fields = ["id", "created_by"]

    def validate_start_date(self, data):
        """validates start date with current and end date

        Raises:
            serializers.ValidationError: raises if start date is not valid

        Returns:
            Date: start_date
        """        
        start_date = self.initial_data.get("start_date")
        start_date = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%SZ")
        if start_date <= datetime.now(): 
            raise serializers.ValidationError("Start date must be in future.")
        return start_date

    def validate_end_date(self, data):
        """validates end date with current and Start date

        Raises:
            serializers.ValidationError: raises if end date is not valid

        Returns:
            Date: end_date
        """        
        end_date = self.initial_data.get("end_date")
        end_date = datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%SZ")
        start_date = self.initial_data.get("start_date")
        start_date = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%SZ")
        if start_date >= end_date:
            raise serializers.ValidationError("End date should be after start date.")
        return end_date

    def validate(self, data):
        """validates all the Trip data.

        Args:
            data (dictionary): data of trip to be created 

        Returns:
            object: validated trip data 
        """
        return data

    def create(self, validated_data):
        """Takes validated data and creates an instance of trip and returns it

        Args:
            validated_data (Dictionary): validated data to create a trip

        Returns:
            object: trip object containing all the data to create trip. 
        """        
        attachments = validated_data.pop("files", [])
        departments_data = validated_data.pop("departments", [])
        trips = Trip.objects.create(**validated_data)
        for attachment in attachments:
            Attachments.objects.create(trip=trips, attachment=attachment)

        for department_data in departments_data:
            trips.departments.add(department_data)

        return trips


class TripUserSerializer(serializers.ModelSerializer):
    """Takes user id, trip id and their preference for being in trip or not"""
    class Meta:
        model = TripUsers
        fields = ("id", "trip", "user", "interested")


class AuthorizationUrlSerializer(serializers.Serializer):
    """Takes authorization url to authorize user of Trip with splitwise"""
    authorization_url = serializers.CharField()


class AccessTokenSerializer(serializers.Serializer):
    """Serializes the message to be shown after execution of access token generation"""
    message = serializers.CharField()


class SplitwiseUserSerializer(serializers.Serializer):
    """Used as nested serializer to get each user's paid share and owed share while creating an expense"""
    user_id = serializers.IntegerField()
    paid_share = serializers.DecimalField(max_digits=10, decimal_places=2)
    owed_share = serializers.DecimalField(max_digits=10, decimal_places=2)


class ExpenseSerializer(serializers.Serializer):
    """defines fields required to generate an expense"""
    split_equally = serializers.BooleanField(default=True)
    group_id = serializers.IntegerField()
    description = serializers.CharField()
    cost = serializers.DecimalField(max_digits=10, decimal_places=2)
    users = SplitwiseUserSerializer(many=True)