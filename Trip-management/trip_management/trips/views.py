from django.shortcuts import get_object_or_404, render
from django.db.models import Q
from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError

from datetime import datetime, timezone

from requests import session
from splitwise import Splitwise, SplitwiseError
from splitwise.group import Group
from splitwise.user import User, ExpenseUser
from splitwise.expense import Expense
import pytz
import json

from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.parsers import FormParser, MultiPartParser, FileUploadParser
from rest_framework import permissions, generics
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from rest_framework import filters


from .models import Trip, Attachments, TripUsers
from authentication.models import Users, Department
from .serializers import (
    TripSerializer,
    TripUserSerializer,
    AuthorizationUrlSerializer,
    AccessTokenSerializer,
    ExpenseSerializer,
)


class TripViewSet(viewsets.ModelViewSet):
    """The viewset overrides multiple methods to perform create, update, search operations on trips"""

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TripSerializer
    queryset = Trip.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ["title", "description"]

    def perform_create(self, serializer):
        """gets the serialized data and adds "created_by" to validated_data dictionary and adds requesting user in it.

        Args:
            serializer (object): serialized data to create trip.
        """
        serializer.validated_data["created_by"] = self.request.user
        serializer.save()

    def get_queryset(self):
        """performs search on title and description fields based on string passed in url

        Returns:
            object: object of queryset having search results.
        """
        queryset = super().get_queryset()

        search_query = self.request.query_params.get("search", None)
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query)
                | Q(description__icontains=search_query)
            )

        user_department = self.request.user.department
        queryset = queryset.filter(departments=user_department)

        return queryset

    def update(self, request, *args, **kwargs):
        """gets trip id and tries getting and updating trip based on given id and user id of requesting user

        Args:
            request (Object): Object containing user data.

        Returns:
            JSON: Updated data or error message
        """
        trip_id = kwargs.get("pk")
        try:
            trip = self.get_queryset().get(id=trip_id, created_by=request.user)
        except:
            return Response(
                {"message": "Trip not found."}, status=status.HTTP_404_NOT_FOUND
            )

        serializer = self.serializer_class(trip, data=request.data, partial=True)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
        return Response(serializer.errors, status=status.HTTP_304_NOT_MODIFIED)

    @action(detail=False, methods=["get"], url_path="interest/(?P<interested>\w+)")
    def interest(self, request, interested=None):
        """filter trips based on user's selected preference

        Args:
            request (object): contains object of requesting user
            interested (string): Default none, contains user preference for filtering.

        Returns:
            JSON: Contains Trip object if found else returns error.
        """

        if interested == "interested":
            trips = Trip.objects.filter(
                Q(trip__user=request.user) & Q(trip__interested=True)
            )
        elif interested == "not-interested":
            trips = Trip.objects.filter(
                Q(trip__user=request.user) & Q(trip__interested=False)
            )
        else:
            return Response(
                {
                    "message": "Invalid URL parameter. Use 'interested' or 'not_interested'."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(trips, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        """Fetches trip using trip_id passed and deletes it if it exists.

        Args:
            request (object): object of requesting user

        Returns:
            JSON: deletion or error message
        """
        trip_id = kwargs.get("pk")
        try:
            trip = Trip.objects.get(id=trip_id)
        except Trip.DoesNotExist:
            return Response(
                {"detail": "Trip not found"}, status=status.HTTP_403_FORBIDDEN
            )
        else:
            if trip.created_by == request.user:
                try:
                    attachments = Attachments.objects.filter(trip=trip)
                    attachments.delete()
                    trip.delete()
                    return Response(
                        {"detail": "Trip deleted"}, status=status.HTTP_204_NO_CONTENT
                    )
                except:
                    return Response(
                        {"detail": "Trip not found"}, status=status.HTTP_404_NOT_FOUND
                    )
            return Response(
                {"detail": "Trip not found"}, status=status.HTTP_403_FORBIDDEN
            )


class TripUsersView(generics.CreateAPIView, generics.RetrieveUpdateAPIView):
    """Manages user preference for trip and add them to corresponding splitwise group if preference is True"""

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TripUserSerializer
    queryset = TripUsers.objects.all()

    def post(self, request, *args, **kwargs):
        """gets trip id and user's preference for trip. If preference is true then adds user to corresponding trip's splitwise group.

        Args:
            request (object): contains requesting user object.

        Returns:
            JSON: success or error message.
        """
        trip_id = kwargs.get("id")
        trip = Trip.objects.get(id=trip_id)
        local_datetime = datetime.now()
        utc_datetime = local_datetime.astimezone(timezone.utc)
        if trip.start_date <= utc_datetime:
            return Response(
                {"message": "Trip have already started or completed"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user_id = request.user.id
        interested = request.data.get("interested")
        data = request.data.copy()
        data["user"] = user_id
        data["trip"] = trip_id

        try:
            trip = Trip.objects.get(id=trip_id)
            creator = trip.created_by
            creator_user = Users.objects.get(id=creator.id)
            if request.user.department in trip.departments.all():
                try:
                    trip_user = TripUsers.objects.create(
                        trip_id=trip_id, user_id=user_id, interested=interested
                    )
                except IntegrityError:
                    return Response({"message":"Can't make a new entry for same user id and trip id"})
                # breakpoint()
                if trip.splitwise_group and interested == "True":
                    splitwise = Splitwise(
                        consumer_key=settings.SPLITWISE_CONSUMER_KEY,
                        consumer_secret=settings.SPLITWISE_CONSUMER_SECRET,
                    )
                    access_dict = {
                        "access_token": creator_user.access_token,
                        "token_type": "bearer",
                    }
                    splitwise.setOAuth2AccessToken(access_dict)
                    user = User()
                    user.setFirstName(request.user.first_name)
                    user.setEmail(request.user.email)

                    success, user, errors = splitwise.addUserToGroup(
                        user, trip.splitwise_group
                    )
                    return Response(
                        {"message": "Interest added and you have been added to expense group of the trip"}, status=status.HTTP_200_OK
                    )
                return Response(
                    {"message": "Interest added."}, status=status.HTTP_201_CREATED
                )
            else:
                return Response(
                    {"message": "Invalid user or department."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Trip.DoesNotExist:
            return Response(
                {"message": "Invalid trip id."}, status=status.HTTP_400_BAD_REQUEST
            )

    def update(self, request, *args, **kwargs):
        """Updates user preference if given before trip start date is arrived and if updated to trip adds user to splitwise group

        Args:
            request (object): requesting user object.

        Returns:
            JSON: success or error message.
        """
        trip_id = kwargs.get("id")
        trip = Trip.objects.get(id=trip_id)
        local_datetime = datetime.now()
        utc_datetime = local_datetime.astimezone(timezone.utc)
        if trip.start_date <= utc_datetime:
            return Response(
                {"message": "Trip have already started or completed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        trip_user = TripUsers.objects.get(trip=trip_id, user=request.user.id)

        if trip_user:
            creator = trip.created_by
            creator_user = Users.objects.get(id=creator.id)
            user_interest = request.data
            if user_interest["interested"] == "True" and trip.splitwise_group:
                splitwise = Splitwise(
                    consumer_key=settings.SPLITWISE_CONSUMER_KEY,
                    consumer_secret=settings.SPLITWISE_CONSUMER_SECRET,
                )
                access_dict = {
                    "access_token": creator_user.access_token,
                    "token_type": "bearer",
                }
                splitwise.setOAuth2AccessToken(access_dict)
                user = User()
                user.setFirstName(request.user.first_name)
                user.setEmail(request.user.email)

                success, user, errors = splitwise.addUserToGroup(
                    user, trip.splitwise_group
                )
            serializer = self.serializer_class(
                instance=trip_user, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "Invalid user or trip id."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class MyTripsViewSet(viewsets.ModelViewSet):
    """Gets list of trips created by requesting user."""

    serializer_class = TripSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """gets Trip object containing creator as requesting user's id.

        Returns:
            Object: Trip objects
        """
        user = self.request.user
        return Trip.objects.filter(created_by=user).prefetch_related("attachments")

    def list(self, request, *args, **kwargs):
        """takes queryset containing multiple trip objects to serialize them and return.

        Returns:
            JSON: list of trips created by requesting user
        """
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class TripSearchViewSet(viewsets.ModelViewSet):
    """Searches trips based on given range of date."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TripSerializer
    filter_backends = [filters.SearchFilter]

    def get_queryset(self):
        """gets query parameter of start date and end date if provided and fetches trips based on them.

        Returns:
            object: trip objects of matching search results.
        """
        start_date = self.request.query_params.get("start_date", None)
        end_date = self.request.query_params.get("end_date", None)
        query = Q(departments=self.request.user.department)
        if not start_date and not end_date:
            return Trip.objects.filter(query)
        elif start_date and not end_date:
            query &= Q(start_date__gte=start_date)
        elif not start_date and end_date:
            return Trip.objects.filter(start_date__lte=end_date)
        else:
            query &= Q(start_date__range=[start_date, end_date])

        return Trip.objects.filter(query)


class SplitwiseConnectView(APIView):
    """Initiates authentication of user with splitwise"""

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Gets state and url and stores it in cache.

        Args:
            request (object): requesting user's object

        Returns:
            JSON: Authorization url
        """
        splitwise = Splitwise(
            consumer_key=settings.SPLITWISE_CONSUMER_KEY,
            consumer_secret=settings.SPLITWISE_CONSUMER_SECRET,
        )

        url, state = splitwise.getOAuth2AuthorizeURL(settings.SPLITWISE_REDIRECT_URI)
        cache.set(state, request.user)
        serializer = AuthorizationUrlSerializer({"authorization_url": url})
        return Response(serializer.data)


class SplitwiseOAuth2CallbackView(APIView):
    """Gets code from redirect url and generates access code and saves it to database"""

    authentication_classes = ()
    permission_classes = ()

    def get(self, request):
        """gets authorization code and generates access code and updates status in database

        Args:
            request (object): data of user authenticating to splitwise

        Returns:
            JSON: successful or error message.
        """
        authorization_code = request.GET.get("code")
        state = request.GET.get("state")
        splitwise = Splitwise(
            consumer_key=settings.SPLITWISE_CONSUMER_KEY,
            consumer_secret=settings.SPLITWISE_CONSUMER_SECRET,
        )

        access_token_dict = splitwise.getOAuth2AccessToken(
            authorization_code, settings.SPLITWISE_REDIRECT_URI
        )
        access_token = access_token_dict["access_token"]
        access_dict = {"access_token": access_token, "token_type": "bearer"}
        splitwise.setOAuth2AccessToken(access_dict)
        user_detail = splitwise.getCurrentUser()
        splitwise_id = user_detail.id
        user = cache.get(state)
        user.access_token = access_token
        user.splitwise_id = splitwise_id
        user.flag = True
        user.save()

        serializer = AccessTokenSerializer(
            {"message": "Access token stored successfully."}
        )
        return Response(serializer.data)


class SplitwiseAccountView(APIView):
    """Gets user details by calling splitwise api and serialize them prior returning"""

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Gets user data using user's access token and returns serialized data.

        Args:
            request (object): requesting user's data

        Returns:
            JSON: user data of splitwise account.
        """
        splitwise = Splitwise(
            consumer_key=settings.SPLITWISE_CONSUMER_KEY,
            consumer_secret=settings.SPLITWISE_CONSUMER_SECRET,
        )
        access_token = request.user.access_token
        access_dict = {"access_token": access_token, "token_type": "bearer"}
        splitwise.setOAuth2AccessToken(access_dict)
        user_detail = splitwise.getCurrentUser()
        if user_detail is None:
            return Response({"message": "User details not found"})
        data = {
            "first_name": user_detail.first_name,
            "last_name": user_detail.last_name,
            "id": user_detail.id,
            "email": user_detail.email,
            "registration_status": user_detail.registration_status,
            "picture": str(user_detail.picture),
            "default_currency": user_detail.default_currency,
            "locale": user_detail.locale,
            "date_format": user_detail.date_format,
            "default_group_id": user_detail.default_group_id,
        }
        return Response(data)


class CreateGroupView(APIView):
    """Creates expense group corresponding to its trip."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, trip_id):
        """Takes trip id and generates expense group by calling splitwise api using required data.

        Args:
            request (object): requesting user's data
            trip_id (int): id of trip for which expense group is to be made.

        Returns:
            JSON: created group id or error message
        """
        access_token = request.user.access_token
        access_dict = {"access_token": access_token, "token_type": "bearer"}
        splitwise = Splitwise(
            consumer_key=settings.SPLITWISE_CONSUMER_KEY,
            consumer_secret=settings.SPLITWISE_CONSUMER_SECRET,
        )
        splitwise.setOAuth2AccessToken(access_dict)
        trip_obj = Trip.objects.get(id=trip_id)
        if not trip_obj:
            return Response({"message": "Invalid trip id"})
        group_name = trip_obj.title
        group = Group()
        group.setName(group_name)

        trip_users = TripUsers.objects.filter(Q(trip_id=trip_id) & Q(interested=True))
        members = []
        for trip_user in trip_users:
            user = User()
            group_member = Users.objects.get(id=trip_user.user_id)
            user.setFirstName(group_member.first_name)
            user.setLastName(group_member.last_name)
            user.setEmail(group_member.email)
            members.append(user)

        group.setMembers(members)
        try:
            group, error = splitwise.createGroup(group)
            group_id = group.getId()
            trip = Trip.objects.get(id=trip_id)
            trip.splitwise_group = group_id
            trip.save()
            return Response({"group_id": group_id})
        except SplitwiseError as e:
            return Response({"error": str(e)})


class GroupExpense(APIView):
    """Adds expense to the group"""

    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete"]

    def post(self, request):
        """Adds expense to group using required data and based on user preference of splitting equally or not.

        Args:
            request (object): requesting user's data

        Returns:
            JSON: Data of expense added in the group or error message
        """
        serializer = ExpenseSerializer(data=request.data)

        if serializer.is_valid():
            expense_data = serializer.validated_data
            split_equally = expense_data["split_equally"]
            group_id = expense_data["group_id"]
            description = expense_data["description"]
            cost = expense_data["cost"]
            users = expense_data["users"]

            access_token = request.user.access_token
            access_dict = {"access_token": access_token, "token_type": "bearer"}
            splitwise = Splitwise(
                consumer_key=settings.SPLITWISE_CONSUMER_KEY,
                consumer_secret=settings.SPLITWISE_CONSUMER_SECRET,
            )
            splitwise.setOAuth2AccessToken(access_dict)
            expense = Expense()
            expense.setGroupId(group_id)
            expense.setDescription(description)
            expense.setCost(cost)
            breakpoint()
            if split_equally == False:
                for user_details in users:
                    user_id = user_details["user_id"]
                    User = Users.objects.get(id=user_id)
                    expenseUser = ExpenseUser()
                    expenseUser.setFirstName(User.first_name)
                    expenseUser.setLastName(User.last_name)
                    expenseUser.setEmail(User.email)
                    expenseUser.setPaidShare(user_details["paid_share"])
                    expenseUser.setOwedShare(user_details["owed_share"])
                    expense.addUser(expenseUser)
            else:
                equal_shares = cost / (len(users))
                for user_details in users:
                    user_id = user_details["user_id"]
                    User = Users.objects.get(id=user_id)
                    expenseUser = ExpenseUser()
                    expenseUser.setFirstName(User.first_name)
                    expenseUser.setLastName(User.last_name)
                    expenseUser.setEmail(User.email)
                    expenseUser.setPaidShare(user_details["paid_share"])
                    expenseUser.setOwedShare(equal_shares)
                    expense.addUser(expenseUser)

            nExpense, errors = splitwise.createExpense(expense)

            if errors:
                errors = vars(errors)
                return Response(errors)

            users_list = []
            repayment_list = []
            data = {
                "expense_id": nExpense.id,
                "cost": nExpense.cost,
                "description": nExpense.description,
                "group_id": nExpense.group_id,
            }
            for i in nExpense.users:
                user_json = vars(i)
                user_dict = {
                    "id": user_json["id"],
                    "first_name": user_json["first_name"],
                    "last-name": user_json["last_name"],
                    "paid_share": user_json["paid_share"],
                    "owed_share": user_json["owed_share"],
                    "balance": user_json["net_balance"],
                }
                users_list.append(user_dict)

            data["users"] = users_list

            for i in nExpense.repayments:
                repayments_json = vars(i)
                repayments_dict = {
                    "from_user": repayments_json["fromUser"],
                    "to_user": repayments_json["toUser"],
                    "amount": repayments_json["amount"],
                }
                repayment_list.append(repayments_dict)

            data["repayments"] = repayment_list
            return Response(data)

        else:
            return Response(
                {"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )

    def patch(self, request, *args, **kwargs):
        """Updates expense using expense id

        Args:
            request (object): requesting user's data

        Returns:
            JSON: Updated expense of the group.
        """
        serializer = ExpenseSerializer(data=request.data)

        if serializer.is_valid():
            expense_data = serializer.validated_data
            group_id = expense_data["group_id"]
            description = expense_data["description"]
            cost = expense_data["cost"]
            users = expense_data["users"]

            access_token = request.user.access_token
            access_dict = {"access_token": access_token, "token_type": "bearer"}
            splitwise = Splitwise(
                consumer_key=settings.SPLITWISE_CONSUMER_KEY,
                consumer_secret=settings.SPLITWISE_CONSUMER_SECRET,
            )
            splitwise.setOAuth2AccessToken(access_dict)

            expense_id = request.GET.get("expense_id")
            expense = Expense()
            expense.id = expense_id

            for user_details in users:
                user_id = user_details["user_id"]
                User = Users.objects.get(id=user_id)
                expenseUser = ExpenseUser()
                expenseUser.setFirstName(User.first_name)
                expenseUser.setLastName(User.last_name)
                expenseUser.setEmail(User.email)
                expenseUser.setPaidShare(user_details["paid_share"])
                expenseUser.setOwedShare(user_details["owed_share"])
                expense.addUser(expenseUser)

            nExpense, errors = splitwise.updateExpense(expense)
            if errors:
                errors = vars(errors)
                return Response(errors)

            users_list = []
            repayment_list = []
            data = {
                "expense_id": nExpense.id,
                "cost": nExpense.cost,
                "description": nExpense.description,
                "group_id": nExpense.group_id,
            }
            for i in nExpense.users:
                user_json = vars(i)
                user_dict = {
                    "id": user_json["id"],
                    "first_name": user_json["first_name"],
                    "last-name": user_json["last_name"],
                    "paid_share": user_json["paid_share"],
                    "owed_share": user_json["owed_share"],
                    "balance": user_json["net_balance"],
                }
                users_list.append(user_dict)

            data["users"] = users_list

            for i in nExpense.repayments:
                repayments_json = vars(i)
                repayments_dict = {
                    "from_user": repayments_json["fromUser"],
                    "to_user": repayments_json["toUser"],
                    "amount": repayments_json["amount"],
                }
                repayment_list.append(repayments_dict)

            data["repayments"] = repayment_list
            return Response(data)

        else:
            return Response(
                {"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )

    def delete(self, request):
        """deletes expense based on expense id passed in url parameter.

        Args:
            request (object): requesting user's data

        Returns:
            JSON: Success or error message.
        """
        access_token = request.user.access_token
        access_dict = {"access_token": access_token, "token_type": "bearer"}
        splitwise = Splitwise(
            consumer_key=settings.SPLITWISE_CONSUMER_KEY,
            consumer_secret=settings.SPLITWISE_CONSUMER_SECRET,
        )
        splitwise.setOAuth2AccessToken(access_dict)
        expense_id = request.GET.get("expense_id")

        success, errors = splitwise.deleteExpense(expense_id)

        if errors:
            return Response(errors)

        return Response(success)
