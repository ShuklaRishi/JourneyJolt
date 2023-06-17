from django.core.cache import cache
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from django.utils.crypto import get_random_string
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Users
from .serializers import (
    ChangePasswordSerializer,
    PasswordResetRequestSerializer,
    PasswordResetSerializer,
    ProfileUpdateSerializer,
    UserSerializer,
)


class UserSignUp(APIView):
    permission_classes = ()
    authentication_classes = ()
    serializer_class = UserSerializer

    def post(self, request):
        """Register user

        Returns:
            _type_1: user object OR error object
        """
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(status=status.HTTP_400_BAD_REQUEST)


class Profile(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProfileUpdateSerializer

    def put(self, request):
        """Update user profile

        Args:
            request (JSON): username, department, firstname, lastname

        Returns:
            _type_: Updated user object OR error object
        """
        username = request.user.username
        instance = Users.objects.get(username=username)
        serializer = ProfileUpdateSerializer(instance, data=request.data)
        if serializer.is_valid():
            serializer.update(instance, serializer.validated_data)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        """takes username and verifies authentication and deletes user profile

        Args:
            request (JSON): username

        Returns:
            _type_: success or error message
        """
        user = self.request.user
        username = user.username
        user = Users.objects.filter(username=username).first()
        if user:
            user.delete()
            return Response(
                {"message": "User deleted successfully."},
                status=status.HTTP_204_NO_CONTENT,
            )
        return Response(
            {"message": "User does not exist."}, status=status.HTTP_404_NOT_FOUND
        )


class PasswordOtpApi(APIView):
    authentication_classes = ()
    permission_classes = ()
    serializer_class = PasswordResetRequestSerializer

    def post(self, request):
        """Takes user email and sends random generated otp on it and stores it in cache.

        Args:
            request (JSON): user email

        Returns:
            _type_: Success message OR Error
        """
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        user = get_object_or_404(Users, email=email)

        otp = get_random_string(length=6, allowed_chars="0123456789")

        subject = "Password Reset Requested"
        message = f"Your OTP for resetting password is {otp}"
        from_email = "noreply@example.com"
        recipient_list = [user.email]
        send_mail(subject, message, from_email, recipient_list, fail_silently=False)

        cache.set(f"password_reset_otp:{email}", otp, timeout=900)

        return Response(
            {"message": "Password reset email sent"}, status=status.HTTP_200_OK
        )


class ResetPassword(APIView):
    authentication_classes = ()
    permission_classes = ()
    serializer_class = PasswordResetSerializer

    def post(self, request):
        """verifies user's email and otp and sets new password

        Args:
            request (JSON): email, otp, new password

        Returns:
            _type_: success message or error
        """
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            otp = serializer.validated_data["otp"]
            password = serializer.validated_data["password"]

        cached_otp = cache.get(f"password_reset_otp:{email}")
        if cached_otp:
            if cached_otp == otp:
                user = get_object_or_404(Users, email=email)
                user.set_password(password)
                user.save()
                cache.delete(f"password_reset_otp:{email}")
                return Response(
                    {"message": "Password reset success"}, status=status.HTTP_200_OK
                )
            return Response(
                {"message": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response({"message": "OTP Expired"}, status=status.HTTP_400_BAD_REQUEST)


class ChangePassword(generics.UpdateAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def get_object(self):
        """Fetch user object for given username

        Returns:
            _type_: user object
        """
        user = self.request.user
        username = user.username
        try:
            user = Users.objects.get(username=username)
            return user
        except Users.DoesNotExist:
            return None

    def put(self, request):
        """verifies current password and sets new password

        Args:
            request (JSON): old password, new password and confirm password

        Returns:
            _type_: success or error message
        """
        user_profile = self.get_object()

        if user_profile:
            serializer = self.get_serializer(user_profile, data=request.data)
            serializer.is_valid(raise_exception=True)

            new_password = serializer.validated_data["new_password"]

            user_profile.set_password(new_password)
            user_profile.save()

            return Response({"message": "Password updated successfully."})

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
