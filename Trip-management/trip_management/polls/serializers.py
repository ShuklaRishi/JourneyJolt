from datetime import datetime
from rest_framework import serializers
from .models import Choice, Poll, Vote
from authentication.models import Users, Department


class ChoiceSerializer(serializers.ModelSerializer):
    """Takes choice_text, id and votes and returns them by calculating percentage as well based on vote counts."""
    id = serializers.IntegerField(required=False)
    percentage = serializers.SerializerMethodField()

    class Meta:
        model = Choice
        fields = ("id", "choice_text", "votes", "percentage")

    def get_percentage(self, obj):
        """Takes vote counts and calculates percentage of each of them based on counts.

        Args:
            obj (object): gets poll object to extract choices from it

        Returns:
            int: returns vote percent or default zero  
        """        
        choices = obj.poll.choices.all()
        total_votes = 0
        for i in choices:
            total_votes += i.votes
        if total_votes:
            return round(obj.votes / total_votes * 100, 2)
        else:
            return 0.0


class VoteSerializer(serializers.ModelSerializer):
    """Takes choice field in order to manage vote"""
    class Meta:
        model = Vote
        fields = ["choice"]


class PollSerializer(serializers.ModelSerializer):
    """Takes poll data and validates it before serializing"""
    choices = ChoiceSerializer(many=True)
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), many=True
    )

    class Meta:
        model = Poll
        fields = ("id", "title", "department", "expiry", "choices", "created_by")
        read_only_fields = ["id", "created_by"]

    def get_user_choice(self, obj):
        """fetches user's voted choice

        Args:
            obj (object): gets choice object

        Returns:
            object : choice that have been voted or none
        """        
        user = self.context["request"].user
        try:
            return obj.choices.get(votes__voter=user)
        except Choice.DoesNotExist:
            return None

    def validate_expiry(self, data):
        """validates expiry date with current date

        Raises:
            serializers.ValidationError: raises if expiry date is not valid

        Returns:
            date:valid expiry date
        """        
        expiry = self.initial_data.get("expiry")
        expiry = datetime.strptime(expiry, "%Y-%m-%dT%H:%M:%SZ")
        if expiry <= datetime.now():
            raise serializers.ValidationError("Expiry date must be in the future")
        return expiry

    def create(self, validated_data):
        """creates poll and choices object to add given data

        Args:
            validated_data (dictionary): dictionary containing poll data and it's choices data

        Returns:
            Object: Poll object
        """        
        departments_data = validated_data.pop("department", [])
        choices_data = validated_data.pop("choices", [])
        poll = Poll.objects.create(**validated_data)
        for choice_data in choices_data:
            Choice.objects.create(poll=poll, **choice_data)

        for department_data in departments_data:
            poll.department.add(department_data)

        return poll

    def update(self, instance, validated_data, **kwargs):
        """Takes data to be updated and validates it nad returns the instance.

        Args:
            instance (object): contains data to be updated
            validated_data (dictionary): contains new data

        Raises:
            serializers.ValidationError: raised when data is invalid.

        Returns:
            object: instance of new data
        """        
        choices_data = self.context["request"].data.get("choices", [])
        if validated_data.get("department"):
            instance.department.set(validated_data.get("department", []))
        expiry = validated_data.get("expiry")
        if expiry <= datetime.now():
            raise serializers.ValidationError("Expiry date must be in the future")
        instance.expiry = expiry or instance.expiry
        title = validated_data.get("title")
        instance.title = title or instance.title

        for choice_data in choices_data:
            choice_id = choice_data.get("id", None)
            if choice_id:
                choice = Choice.objects.get(id=choice_id, poll=instance)
                choice.choice_text = choice_data.get("choice_text", choice.choice_text)
                choice.votes = 0
                choice.save()
            else:
                Choice.objects.create(poll=instance, **choice_data)
        if expiry or title:
            instance.save()
        return instance
