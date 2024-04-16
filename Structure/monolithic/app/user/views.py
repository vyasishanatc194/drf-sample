# -*- coding: utf-8 -*-
import logging

from core.permissions import IsProfileOwner
from core.throttling import UserBurstThrottle, UserDefaultThrottle
from core.views import RetrievePatchOnlyAPIView
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.response import Response
from user.serializers import UserProfileBaseSerializer

from .docs import doc_user_self_get, doc_user_self_patch
from .drf_schema import user_profile_detail_view_schema, user_profile_patch_view_schema
from .utils_user import (
    delete_user_profile_cache,
    get_proxy_userprofile_model,
    get_proxy_userprofile_serializer,
)

User = get_user_model()

logger = logging.getLogger("django.eventlogger")


class UserSelfView(RetrievePatchOnlyAPIView):
    permission_classes = [permissions.IsAuthenticated & IsProfileOwner]
    serializer_class = UserProfileBaseSerializer

    def get_serializer_class(self):
        return get_proxy_userprofile_serializer(self.request.user)

    def get_throttles(self):
        if self.request.method == "GET":
            self.throttle_classes = [
                UserBurstThrottle,
            ]
        elif self.request.method == "PATCH":
            self.throttle_classes = [
                UserDefaultThrottle,
            ]
        return super().get_throttles()

    @doc_user_self_get
    @extend_schema(**user_profile_detail_view_schema)
    def get(self, request, *args, **kwargs):
        from .caches import UserProfileCache

        profile_cache = UserProfileCache().get(request.user.uuid)
        return Response(profile_cache)

    @doc_user_self_patch
    @extend_schema(**user_profile_patch_view_schema)
    def patch(self, request, *args, **kwargs):
        userprofile_model = get_proxy_userprofile_model(request.user)
        instance = userprofile_model.objects.get(user=request.user)
        serializer = self.get_serializer_class()(
            instance, data=request.data, partial=True
        )
        if serializer.is_valid(raise_exception=True):
            serializer.save()

        delete_user_profile_cache(request.user.uuid)
        from .caches import UserProfileCache

        profile_cache = UserProfileCache().get(request.user.uuid)

        return Response(profile_cache)
