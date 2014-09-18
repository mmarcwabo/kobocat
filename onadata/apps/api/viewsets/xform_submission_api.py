import pytz

from datetime import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _

from rest_framework import permissions
from rest_framework import status
from rest_framework import viewsets
from rest_framework import mixins
from rest_framework.response import Response

from onadata.apps.logger.models import Instance
from onadata.apps.main.models.user_profile import UserProfile
from onadata.libs import filters
from onadata.libs.authentication import DigestAuthentication
from onadata.libs.renderers.renderers import TemplateXMLRenderer
from onadata.libs.serializers.data_serializer import SubmissionSerializer
from onadata.libs.utils.logger_tools import safe_create_instance


# 10,000,000 bytes
DEFAULT_CONTENT_LENGTH = getattr(settings, 'DEFAULT_CONTENT_LENGTH', 10000000)


class XFormSubmissionApi(mixins.CreateModelMixin, viewsets.GenericViewSet):
    authentication_classes = (DigestAuthentication,)
    filter_backends = (filters.AnonDjangoObjectPermissionFilter,)
    model = Instance
    permission_classes = (permissions.AllowAny,)
    renderer_classes = (TemplateXMLRenderer,)
    serializer_class = SubmissionSerializer
    template_name = 'submission.xml'

    def get_openrosa_headers(self, request):
        tz = pytz.timezone(settings.TIME_ZONE)
        dt = datetime.now(tz).strftime('%a, %d %b %Y %H:%M:%S %Z')

        return {
            'Date': dt,
            'Location': request.build_absolute_uri(request.path),
            'X-OpenRosa-Version': '1.0',
            'X-OpenRosa-Accept-Content-Length': DEFAULT_CONTENT_LENGTH
        }

    def create(self, request, *args, **kwargs):
        username = self.kwargs.get('username')
        if username is None and self.request.user.is_anonymous():
            # raises a permission denied exception, forces authentication
            self.permission_denied(self.request)
        elif username is not None and self.request.user.is_anonymous():
            user = get_object_or_404(
                User, username=username.lower())

            profile, created = UserProfile.objects.get_or_create(user=user)
            if profile.require_auth:
                # raises a permission denied exception, forces authentication
                self.permission_denied(self.request)

        xml_file = request.FILES.get('xml_submission_file')
        media_files = request.FILES.values()

        error, instance = safe_create_instance(
            username, xml_file, media_files, None, request)

        if error:
            return error

        if instance is None:
            return Response(_(u"Unable to create submission."))

        context = self.get_serializer_context()
        serializer = SubmissionSerializer(instance, context=context)

        return Response(serializer.data,
                        headers=self.get_openrosa_headers(request),
                        status=status.HTTP_201_CREATED,
                        template_name=self.template_name)
