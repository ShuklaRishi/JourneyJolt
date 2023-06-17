from rest_framework import serializers
from .models import Users, Department


class UserSerializer(serializers.ModelSerializer):
    """Serializes user data for user registration and storing"""

    password = serializers.CharField(write_only=True)

    class Meta:
        model = Users
        fields = (
            "id",
            "username",
            "password",
            "email",
            "first_name",
            "last_name",
            "department",
        )
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        """Creates user object and saves and returns it.

        Args:
            validated_data (dictionary): dictionary of user data

        Returns:
            Object: user object
        """
        user = Users.objects.create(
            username=validated_data["username"],
            email=validated_data["email"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            department=validated_data["department"],
        )
        user.set_password(validated_data["password"])
        user.save()
        return user


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Takes updatable fields to update them"""

    class Meta:
        model = Users
        fields = ("username", "first_name", "last_name", "department")

    def update(self, instance, validated_data):
        """takes validated of fields to be updated and creates user object and returns it.

        Args:
            instance (object): gets user instance
            validated_data (dictionary): user dictionary of new data

        Returns:
            _type_: _description_
        """
        instance.username = validated_data.get("username", instance.username)
        instance.first_name = validated_data.get("first_name", instance.first_name)
        instance.last_name = validated_data.get("last_name", instance.last_name)
        instance.department = validated_data.get("department", instance.department)
        instance.save()
        return instance


class PasswordResetRequestSerializer(serializers.Serializer):
    """Takes email in order to send otp to set new password"""

    email = serializers.EmailField()

    def validate_email(self, value):
        """Takes email and verifies if it exists in database.

        Args:
            value (string): Email string

        Raises:
            serializers.ValidationError: Raises if email is not found

        Returns:
            value: returns email if it exists
        """
        if not Users.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email not found")
        return value


class PasswordResetSerializer(serializers.Serializer):
    """Takes email, otp and new password"""

    email = serializers.EmailField()
    otp = serializers.CharField()
    password = serializers.CharField(max_length=124, write_only=True)


class ChangePasswordSerializer(serializers.Serializer):
    """Takes old password, new password and confirm password and verifies old password in order to verify and change password"""

    old_password = serializers.CharField(max_length=124, write_only=True)
    new_password = serializers.CharField(max_length=124, write_only=True)
    confirm_password = serializers.CharField(max_length=124, write_only=True)

    def validate_old_password(self, value):
        """validates old_password with password of that profile in database

        Args:
            value (password): current password

        Raises:
            serializers.ValidationError: raises error if invalid

        Returns:
            value: returns old password
        """
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Invalid password")
        return value

    def validate(self, data):
        """Validates if new password and confirm password are same and if new password and previous passwords are not same.

        Args:
            data (dictionary): gets new password, old password and confirm password.

        Raises:
            serializers.ValidationError: raises if new password and confirm password does not matches.
            serializers.ValidationError: raises if new password and previous passwords are the same.

        Returns:
            data: returns new password, old password and confirm password if valid.
        """
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError(
                "New password and confirm password does not match."
            )

        if data["new_password"] == data["old_password"]:
            raise serializers.ValidationError(
                "New password and old password cannot be the same."
            )

        return data

