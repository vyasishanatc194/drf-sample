from allauth.account import app_settings as allauth_settings
from allauth.account.utils import complete_signup
from auth.caches import PhonenumberVerificationCache
from core.serializers import BlankSerializer
from core.throttling import (
    AnonDefaultThrottle,
    AnonSuppressedThrottle,
    AuthCheckThrottle,
    SMSRequestThrottle,
)
from django.conf import settings
from django.contrib.auth import get_user_model, logout
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_auth.registration.views import LoginView, RegisterView
from rest_framework import generics, permissions, status
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from .drf_schema import (
    auth_phonenumber_check_view_schema,
    auth_signin_token_confirm_view_schema,
    auth_signin_token_request_view_schema,
    auth_signin_view_schema,
    auth_signout_view_schema,
    auth_signup_view_schema,
    auth_token_hearbeat_view_schema,
    auth_unregister_view_schema,
)
from .models import PhonenumberCheck, PhonenumberVerificationLog
from .serializers import (
    PhonenumberCheckSerializer,
    SigninSerializer,
    SigninTokenConfirmSerializer,
    SigninTokenRequestSerializer,
    SignoutTokenRefreshSerializer,
    SignupSerializer,
    TokenObtainPairFromUserSerializer,
)
from .utils_auth import bypass_token_request

USER = get_user_model()


class PhonenumberCheckView(generics.GenericAPIView):
    serializer_class = PhonenumberCheckSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [
        AuthCheckThrottle,
    ]

    @extend_schema(**auth_phonenumber_check_view_schema)
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if USER.objects.filter(phonenumber=serializer.data["phonenumber"]).exists():
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.data, status=status.HTTP_404_NOT_FOUND)


class BaseSignupView(RegisterView):
    serializer_class = SignupSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AnonSuppressedThrottle]

    def get_response_data(self, user):
        phonenumber = self.request.data["phonenumber"]
        user = get_object_or_404(USER, phonenumber=phonenumber)

        serializer = TokenObtainPairFromUserSerializer(
            data={}, context={"request": self.request, "user": user}
        )

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        ret = dict()
        from user.caches import UserProfileCache

        up = UserProfileCache().get(user.uuid)

        ret["uuid"] = user.uuid

        ret["user_profile"] = up
        ret.update(serializer.validated_data)
        return ret

    def perform_create(self, serializer):
        user = serializer.save(self.request)
        complete_signup(
            self.request._request, user, allauth_settings.EMAIL_VERIFICATION, None
        )
        up = {"uuid": user.uuid, "fullname": user.profile.fullname}  # noqa: F841
        return user


class SignupView(BaseSignupView):
    @extend_schema(**auth_signup_view_schema)
    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class SigninView(LoginView):
    serializer_class = SigninSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [
        AuthCheckThrottle,
    ]

    def login(self):
        self.user = self.serializer.validated_data["user"]

        if getattr(settings, "REST_SESSION_LOGIN", True):
            self.process_login()

    def get_response(self):
        serializer = TokenObtainPairFromUserSerializer(
            data={}, context={"request": self.request, "user": self.user}
        )
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        response = Response(serializer.validated_data, status=status.HTTP_200_OK)
        return response

    @extend_schema(**auth_signin_view_schema)
    def post(self, request, *args, **kwargs):
        self.request = request
        self.serializer = self.get_serializer(
            data=self.request.data, context={"request": request}
        )
        self.serializer.is_valid(raise_exception=True)

        self.login()
        return self.get_response()


class SigninTokenRequestView(generics.GenericAPIView):
    serializer_class = SigninTokenRequestSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [
        SMSRequestThrottle,
    ]

    @extend_schema(**auth_signin_token_request_view_schema)
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phonenumber = serializer.data["phonenumber"]

        if not bypass_token_request(phonenumber):
            phonenumber_check, created = PhonenumberCheck.objects.get_or_create(
                phonenumber=phonenumber
            )
            verification_success_count = PhonenumberVerificationCache().get(phonenumber)
            verification_success_count = int(verification_success_count or 0)
            # print(verification_success_count)
            if verification_success_count >= settings.PHONENUMBER_DAILY_SIGNIN_LIMIT:
                return Response(
                    "This number is blocked for 24 hours",
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            phonenumber_check.attempt_verification()
            PhonenumberVerificationLog.objects.create(
                phonenumber=phonenumber,
                type=PhonenumberVerificationLog.VerificationType.SIGNIN,
            )
            timestamp_expires = (
                None
                if phonenumber_check is None
                else phonenumber_check.get_expiration_time()
            )
            return Response(
                {"timestamp_expires": timestamp_expires}, status=status.HTTP_200_OK
            )

        else:
            return Response({}, status=status.HTTP_200_OK)


class SigninTokenConfirmView(LoginView):
    serializer_class = SigninTokenConfirmSerializer
    throttle_classes = (
        []
        if settings.TESTING
        else [
            AnonDefaultThrottle,
        ]
    )

    @extend_schema(**auth_signin_token_confirm_view_schema)
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def login(self):
        self.user = self.serializer.validated_data["user"]

        if self.user:
            if getattr(settings, "REST_SESSION_LOGIN", True):
                self.process_login()

    def get_response(self):
        is_verified = self.serializer.validated_data["is_verified"]
        if self.user and is_verified:
            serializer = TokenObtainPairFromUserSerializer(
                data={}, context={"request": self.request, "user": self.user}
            )
            try:
                serializer.is_valid(raise_exception=True)
            except TokenError as e:
                raise InvalidToken(e.args[0])
            return Response(serializer.validated_data, status=status.HTTP_200_OK)

        # token verification succeed, but fail authentication
        if is_verified:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        return Response("Invalid Token", status=status.HTTP_400_BAD_REQUEST)


class UnregisterView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SignoutTokenRefreshSerializer

    @extend_schema(**auth_unregister_view_schema)
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        # black list token
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:  # noqa: F841
            pass

        user = request.user
        user.date_unregistered = timezone.now()
        user.save()
        user.unregister()
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SignoutView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SignoutTokenRefreshSerializer

    @extend_schema(**auth_signout_view_schema)
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        # black list token
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:  # noqa: F841
            pass

        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TokenHeartbeatView(generics.GenericAPIView):
    serializer_class = BlankSerializer

    @extend_schema(**auth_token_hearbeat_view_schema)
    def post(self, request, *args, **kwargs):
        """
        Delete expired tokens and return their count.
        """
        from rest_framework_simplejwt.settings import api_settings

        if (
            api_settings.BLACKLIST_AFTER_ROTATION
            and "rest_framework_simplejwt.token_blacklist" in settings.INSTALLED_APPS
        ):
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
            from rest_framework_simplejwt.utils import aware_utcnow

            delete_count = OutstandingToken.objects.filter(
                expires_at__lte=aware_utcnow()
            ).delete()
            return Response({"delete_count": delete_count}, status=status.HTTP_200_OK)

        return Response(status=status.HTTP_204_NO_CONTENT)
