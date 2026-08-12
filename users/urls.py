"""
Users URL configuration.
"""

from django.urls import path

from users.views import CurrencyListView, OnboardingView, UserMeView, UserProfileView

urlpatterns = [
    path("me/", UserMeView.as_view(), name="user-me"),
    path("me/profile/", UserProfileView.as_view(), name="user-profile"),
    path("onboarding/", OnboardingView.as_view(), name="user-onboarding"),
    path("currencies/", CurrencyListView.as_view(), name="currency-list"),
]
