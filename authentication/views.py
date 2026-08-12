"""
Authentication views — thin controllers delegating to AuthService.
"""

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.serializers import (
    GoogleAuthSerializer,
    LoginSerializer,
    LogoutSerializer,
    RegisterSerializer,
    TokenRefreshSerializer,
)
from authentication.services import AuthService


class LoginView(APIView):
    """POST /auth/login/ — Authenticate with email and password."""

    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = AuthService.login(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        return Response(result, status=status.HTTP_200_OK)


class RegisterView(APIView):
    """POST /auth/register/ — Create a new account."""

    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = AuthService.register(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            first_name=serializer.validated_data["first_name"],
            last_name=serializer.validated_data.get("last_name", ""),
        )
        return Response(result, status=status.HTTP_201_CREATED)


class GoogleLoginView(APIView):
    """POST /auth/google/ — Authenticate via Google OAuth."""

    permission_classes = [permissions.AllowAny]
    serializer_class = GoogleAuthSerializer

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = AuthService.google_login(
            code=serializer.validated_data.get("code"),
            access_token=serializer.validated_data.get("access_token"),
        )
        return Response(result, status=status.HTTP_200_OK)


class TokenRefreshView(APIView):
    """POST /auth/token/refresh/ — Refresh access token."""

    permission_classes = [permissions.AllowAny]
    serializer_class = TokenRefreshSerializer

    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = AuthService.refresh_token(
            refresh=serializer.validated_data["refresh"],
        )
        return Response(result, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """POST /auth/logout/ — Blacklist refresh token."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LogoutSerializer

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        AuthService.logout(refresh=serializer.validated_data["refresh"])
        return Response(
            {"message": "Successfully logged out."},
            status=status.HTTP_200_OK,
        )
