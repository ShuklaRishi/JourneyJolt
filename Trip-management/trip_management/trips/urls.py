from rest_framework.routers import DefaultRouter, SimpleRouter
from django.urls import path, include
from .views import (
    TripViewSet,
    MyTripsViewSet,
    TripUsersView,
    # DeleteTripsViewSet,
    TripSearchViewSet,
    SplitwiseConnectView,
    SplitwiseOAuth2CallbackView,
    SplitwiseAccountView,
    CreateGroupView,
    GroupExpense,
)

router = DefaultRouter()
router.register(r"filter/dates", TripSearchViewSet, basename="trip-search-on-date")
# router.register(r"delete", DeleteTripsViewSet, basename="delete-trips")
router.register("my-trips", MyTripsViewSet, basename="my-trips")
router.register("", TripViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("interest/<int:id>", TripUsersView.as_view(), name="trip-user-interest"),
    path(
        "<int:trip_id>/group/",
        CreateGroupView.as_view(),
        name="create-splitwise-group",
    ),
    path(
        "interest/<str:interested>/",
        TripViewSet.as_view({"get": "interest"}),
        name="trip-interest",
    ),
    path(
        "splitwise/initiate/",
        SplitwiseConnectView.as_view(),
        name="splitwise_oauth2_initiate",
    ),
    path(
        "splitwise/callback/",
        SplitwiseOAuth2CallbackView.as_view(),
        name="splitwise_oauth2_callback",
    ),
    path(
        "splitwise/account/", SplitwiseAccountView.as_view(), name="splitwise_account"
    ),
    path(
        "group/expenses/",
        GroupExpense.as_view(),
        name="add-expense-equally",
    ),
]
