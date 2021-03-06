# -*- coding: utf-8 -*-
import logging

from django.conf.urls import url
from django.db.models import Q
from easy_thumbnails.files import get_thumbnailer
from profiles.models import Profile
from tastypie.authentication import Authentication
from tastypie.authorization import Authorization
from tastypie.resources import ModelResource
from tastypie.utils import trailing_slash
from haystack.backends import SQ
from haystack.query import SearchQuerySet

log = logging.getLogger(__name__)

THUMBNAIL_OPT = dict(size=(240, 240), crop=True, bw=False, quality=80)


class ProfileResource(ModelResource):
    class Meta:
        queryset = Profile.objects.all()
        list_allowed_methods = ['get', ]
        detail_allowed_methods = ['get', ]
        resource_name = 'profile'
        fields = [
            'pseudonym',
            'biography',
            'biography_html',
            'description',
            'image',
            'gender',
            'city',
            'zip',
            'enable_alpha_features',
        ]
        authentication = Authentication()
        authorization = Authorization()
        always_return_data = True
        filtering = {
        }

    def dehydrate(self, bundle):

        if bundle.obj.user:
            bundle.data['username'] = bundle.obj.user.username
            bundle.data['pseudonym'] = bundle.obj.pseudonym
            bundle.data['display_name'] = bundle.obj.get_display_name()
            bundle.data['full_name'] = bundle.obj.get_full_name()
            bundle.data['groups'] = [g.name for g in bundle.obj.user.groups.all()]
            bundle.data['date_joined'] = bundle.obj.user.date_joined

        else:
            bundle.data['username'] = None
            bundle.data['pseudonym'] = None
            bundle.data['display_name'] = None
            bundle.data['display_name'] = None

        bundle.data['country'] = bundle.obj.country.printable_name if bundle.obj.country else None

        bundle.data['get_absolute_url'] = bundle.obj.get_absolute_url()
        bundle.data['image'] = None
        try:
            bundle.data['image'] = get_thumbnailer(bundle.obj.image).get_thumbnail(THUMBNAIL_OPT).url
        except:
            pass

        bundle.data['tags'] = [tag.name for tag in bundle.obj.tags]

        return bundle

    def obj_update(self, bundle, request, **kwargs):
        return super(ProfileResource, self).obj_update(bundle, request, **kwargs)

    # additional methods
    def prepend_urls(self):

        return [
            url(r"^(?P<resource_name>%s)/autocomplete%s$" % (self._meta.resource_name, trailing_slash()),
                self.wrap_view('autocomplete'), name="profiles-profile_api-autocomplete"),
            url(r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/stats%s$" % (self._meta.resource_name, trailing_slash()),
                self.wrap_view('stats'), name="profiles-profile_api-stats"),

        ]

    def autocomplete(self, request, **kwargs):

        self.method_check(request, allowed=['get'])
        # self.is_authenticated(request)
        self.throttle_check(request)

        q = request.GET.get('q', None)
        result = []
        object_list = []
        qs = None
        if q and len(q) > 1:

            # haystack version
            sqs = SearchQuerySet().models(Profile).filter(SQ(content__contains=q) | SQ(content_auto=q))
            qs = Profile.objects.filter(id__in=[result.object.pk for result in sqs]).distinct()

            # ORM version
            # qs = Profile.objects.filter(Q(user__username__istartswith=q) \
            #                             | Q(user__first_name__istartswith=q) \
            #                             | Q(user__last_name__istartswith=q))

        if qs:
            object_list = qs.distinct()[0:20]

        objects = []
        for result in object_list:
            bundle = self.build_bundle(obj=result, request=request)
            bundle = self.full_dehydrate(bundle)
            objects.append(bundle)

        if qs:
            meta = {
                'query': q,
                'total_count': qs.distinct().count()
            }

            data = {
                'meta': meta,
                'objects': objects,
            }
        else:
            meta = {
                'query': q,
                'total_count': 0
            }

            data = {
                'meta': meta,
                'objects': {},
            }

        self.log_throttled_access(request)
        return self.create_response(request, data)

    def autocomplete_dehydrate(self, bundle, q):

        bundle.data['get_absolute_url'] = bundle.obj.get_absolute_url()
        # bundle.data['resource_uri'] = bundle.obj.get_api_url()
        bundle.data['main_image'] = None
        try:
            opt = THUMBNAIL_OPT
            main_image = get_thumbnailer(bundle.obj.main_image).get_thumbnail(opt)
            bundle.data['main_image'] = main_image.url
        except:
            pass

        return bundle

    def stats(self, request, **kwargs):

        self.method_check(request, allowed=['get'])
        self.is_authenticated(request)
        self.throttle_check(request)

        profile = Profile.objects.get(**self.remove_api_resource_names(kwargs))

        from statistics.util import ObjectStatistics

        ostats = ObjectStatistics(user=profile.user)

        stats = ostats.generate(actions=['stream', 'download', ])

        self.log_throttled_access(request)
        return self.create_response(request, stats)
