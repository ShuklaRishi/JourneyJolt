from django.shortcuts import get_object_or_404, render

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from datetime import datetime

from .models import Poll, Choice, Vote
from authentication.models import Users, Department
from .serializers import PollSerializer, ChoiceSerializer
from .permissions import IsCreator


class Polls(generics.ListAPIView):
    """For creating and listing polls."""

    queryset = Poll.objects.all()
    serializer_class = PollSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """gets user object and fetches department to filter polls of that department.

        Returns:
            Objects: matching poll objects
        """
        user = self.request.user
        department_id = user.department
        return Poll.objects.filter(
            department=department_id, expiry__gt=datetime.now()
        ).prefetch_related("choices")

    def get_serializer_context(self):
        """Takes all the context data from parent class and adds department_id to the dictionary

        Returns:
            Objects: context data with department_id added to the dictionary
        """
        context = super().get_serializer_context()
        context["department_id"] = self.request.user.department
        return context

    def list(self, request, *args, **kwargs):
        """Intantiate serializer for all the objects in queryset

        Returns:
            JSON: serializer data
        """
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        """gets poll data and serializes it to save it.

        Args:
            request (JSON): poll data

        Returns:
            JSON: serialized data or error
        """
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MyPolls(generics.ListAPIView):
    """Returns all the polls created by requesting user with their respective choices."""

    serializer_class = PollSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Gets polls and choices where creator is requesting user

        Returns:
            Objects: poll objects with their respective choices
        """
        user = self.request.user
        return Poll.objects.filter(created_by=user).prefetch_related("choices")

    def list(self, request, *args, **kwargs):
        """Serialize all the poll objects and returns them

        Returns:
            JSON: Poll data
        """
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class PollDetail(generics.RetrieveUpdateAPIView, generics.DestroyAPIView):
    """To get detail view of poll, update poll and delete."""

    queryset = Poll.objects.all()
    serializer_class = PollSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsCreator]

    def get_serializer_context(self):
        """returns poll data based on poll id.

        Returns:
            Object: context
        """
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def destroy(self, request, *args, **kwargs):
        """deletes poll and its respective choices based on poll id in kwargs

        kwargs:
            request (keyword argument): poll_id

        Returns:
            JSON: success or error message for deletion
        """
        poll_id = kwargs.get("pk")
        poll = get_object_or_404(Poll, pk=poll_id)
        if poll.created_by == request.user:
            try:
                choice = Choice.objects.filter(poll=poll)
                choice.delete()
                poll.delete()
                return Response(
                    {"detail": "Poll deleted"}, status=status.HTTP_204_NO_CONTENT
                )
            except:
                return Response(
                    {"detail": "Poll not found"}, status=status.HTTP_404_NOT_FOUND
                )
        else:
            return Response(
                {"detail": "You are not the creator of the poll"},
                status=status.HTTP_403_FORBIDDEN,
            )


class VoteAPI(APIView):
    """Manages adding, updating and undo voting on poll choices"""

    authentication_classes = [JWTAuthentication]
    permissions_classes = [permissions.IsAuthenticated]

    def post(self, request, **kwargs):
        """gets choice id and adds vote to that choice and if already added, undo the vote and if other choice of same poll id is added then vote is updated to the current choice

        Args:
            request (choice_id): takes choice id in url

        Returns:
            JSON: vote added or removed or updated message or error message
        """
        choice_id = kwargs.get("pk")
        choice = get_object_or_404(Choice, pk=choice_id)
        poll = choice.poll
        user = request.user
        poll_departments = poll.department.all()
        if user.department in poll_departments:
            try:
                vote = Vote.objects.get(user=request.user, choice__poll=poll)
                if vote.choice == choice:
                    vote.delete()
                    choice.votes -= 1
                    choice.save()
                    return Response(
                        {"detail": "Vote removed."}, status=status.HTTP_200_OK
                    )
                else:
                    # breakpoint()
                    old_choice = vote.choice
                    vote.choice = choice
                    vote.save()
                    old_choice.votes -= 1
                    old_choice.save()
                    choice.votes += 1
                    choice.save()
                    return Response(
                        {"detail": "Vote updated."}, status=status.HTTP_200_OK
                    )
            except Vote.DoesNotExist:
                vote = Vote(user=request.user, choice=choice)
                vote.save()
                choice.votes += 1
                choice.save()
                return Response(
                    {"detail": "Vote added."}, status=status.HTTP_201_CREATED
                )
        return Response(
            {"message": "You are not authorized to vote in poll"},
            status=status.HTTP_400_BAD_REQUEST,
        )
