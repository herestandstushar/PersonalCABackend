"""
Users views — thin controllers that delegate to services.
"""

from rest_framework import generics, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from users.models import Currency
from users.serializers import (
    CurrencySerializer,
    OnboardingSerializer,
    ProfileUpdateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from users.services import UserService


class UserMeView(generics.RetrieveUpdateAPIView):
    """
    GET /users/me/ — Get current user profile
    PATCH /users/me/ — Update current user profile
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return UserUpdateSerializer
        return UserSerializer

    def get_object(self):
        return UserService.get_user_with_profile(self.request.user.id)


class UserProfileView(generics.UpdateAPIView):
    """
    PATCH /users/me/profile/ — Update user profile preferences
    """

    serializer_class = ProfileUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        user = self.request.user
        from users.models import UserProfile

        profile, _ = UserProfile.objects.get_or_create(user=user)
        return profile


class OnboardingView(generics.CreateAPIView):
    """
    POST /users/onboarding/ — Complete user onboarding
    """

    serializer_class = OnboardingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.validate(request.data)
        serializer.is_valid(raise_exception=True)

        user = UserService.complete_onboarding(
            user=request.user,
            currency_code=serializer.validated_data["currency_code"],
            monthly_income=serializer.validated_data.get("monthly_income"),
        )

        return Response(
            UserSerializer(user).data,
            status=status.HTTP_200_OK,
        )


class CurrencyListView(generics.ListAPIView):
    """
    GET /users/currencies/ — List all supported currencies
    """

    serializer_class = CurrencySerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None
    queryset = Currency.objects.filter(is_active=True)
