# -*- coding: utf-8 -*-

"""
the filter functionality is implemented really badly.
TODO: so this part should definately be refactored at some point of time.
"""

import datetime
import django_filters
from django.utils.translation import ugettext as _
from alibrary import settings as alibrary_settings
from alibrary.models import Release, Playlist, Artist, Media, Label

ORDER_BY_FIELD = 'o'

from django.db import models


class CharListFilter(django_filters.Filter):
    def filter(self, qs, value):
        values = []
        if not value:
            return qs
        if isinstance(value, (list, tuple)):
            lookup = str(value[1])
            if not lookup:
                lookup = 'exact'
            value = value[0]
        else:
            values = value.split(',')
            lookup = self.lookup_type

        if value and values:

            if len(values) > 1:
                lookup = 'in'
                return qs.filter(**{'%s__%s' % (self.name, lookup): values})

            else:
                return qs.filter(**{'%s__%s' % (self.name, lookup): value})

        return qs


class DekadeFilter(django_filters.ChoiceFilter):
    pass


class DateRangeFilter(django_filters.Filter):

    range_start = None
    range_end = None

    def __init__(self, *args, **kwargs):
        super(DateRangeFilter, self).__init__(*args, **kwargs)

    @property
    def field(self):
        if not hasattr(self, '_field'):
            self._field = self.field_class(required=self.required,
                label=self.label, widget=self.widget, **self.extra)

        return self._field

    def filter(self, qs, value):

        range = value.split(':')
        range = range if len(range) == 2 else None

        if range:
            try:
                range_start = datetime.datetime.strptime(range[0], '%Y-%m-%d').date()
            except:
                range_start = None
            try:
                range_end = datetime.datetime.strptime(range[1], '%Y-%m-%d').date()
            except:
                range_end = None

            self.range_start = range_start
            self.range_end = range_end

            if range_start and range_end:
                return qs.filter(**{'%s__range' % self.name: (range_start, range_end)})

            if range_start and not range_end:
                return qs.filter(**{'%s__gte' % self.name: (range_start)})

            if not range_start and range_end:
                return qs.filter(**{'%s__lte' % self.name: (range_end)})

        return qs



class ReleaseFilter(django_filters.FilterSet):
    releasetype = CharListFilter(label="Release type")
    release_country__printable_name = CharListFilter(label="Release Country")
    #media_release__license__name = CharListFilter(label="License")
    #main_format__name = CharListFilter(label="Release Format")
    releasedate = DateRangeFilter(label="Release date")
    class Meta:
        model = Release
        fields = ['releasedate', 'releasetype', 'release_country__printable_name', 'label__type']

    @property
    def filterlist(self):

        flist = []

        if not hasattr(self, '_filterlist'):

            for name, filter_ in self.filters.iteritems():

                ds = self.queryset.values_list(name, flat=False).order_by(name).annotate(
                    n=models.Count("pk", distinct=True)).distinct()

                # TODO: extreme hackish...
                if name == 'releasetype_':
                    nd = []
                    for d in ds:
                        if d[0] == 'NULL':
                            pass
                        else:

                            if d[0] is not None:
                                for x in alibrary_settings.RELEASETYPE_CHOICES:

                                    if x[0] == d[0]:
                                        print x[1]
                                        nd.append([d[0], d[1], x[1]])

                    filter_.entries = nd


                # TODO: extreme hackish...
                if name == 'label__type':
                    nd = []
                    for d in ds:
                        if d[0] == 'NULL':
                            pass
                        else:
                            if d[0] is not None:
                                for x in alibrary_settings.LABELTYPE_CHOICES:
                                    if x[0] == d[0]:
                                        nd.append([d[0], d[1], x[1]])

                    filter_.entries = nd


                elif name == 'release_country__printable_name':
                    nd = []
                    for d in ds:
                        nd.append([d[0], d[1]])

                    nd.sort()
                    filter_.entries = nd

                else:
                    filter_.entries = ds

                if ds not in flist:
                    flist.append(filter_)


            """
            add some custom queries
            """
            cf = {
                'label': 'Extra filters',
                'name': 'extra_filter',
                'entries': [
                    ['no_cover', '', 'No cover'],
                    ['has_cover', '', 'With cover'],
                    ['possible_duplicates', '', 'Duplicate detection'],
                ]
            }
            flist.append(cf)


            self._filterlist = flist

        return self._filterlist


class ArtistFilter(django_filters.FilterSet):
    type = CharListFilter(label=_("Artist type"))
    country__printable_name = CharListFilter(label=_("Country"))

    class Meta:
        model = Artist
        fields = [
            'type',
            'country__printable_name',
            #'professions__name'
        ]

    @property
    def filterlist(self):
        flist = []
        if not hasattr(self, '_filterlist'):
            for name, filter_ in self.filters.iteritems():
                ds = self.queryset.values_list(name, flat=False).order_by(name).annotate(
                    n=models.Count("pk", distinct=True)).distinct()
                filter_.entries = ds

                if name == 'country__printable_name':
                    nd = []
                    for d in ds:
                        nd.append([d[0], d[1]])

                    nd.sort()
                    filter_.entries = nd


                if ds not in flist:
                    flist.append(filter_)

            """
            add some custom queries
            """
            cf = {
                'label': 'Extra filters',
                'name': 'extra_filter',
                'entries': [
                    ['possible_duplicates', '', 'Duplicate detection'],
                    ['mbid_duplicates', '', 'Duplicate MBID'],
                ]
            }
            flist.append(cf)

            self._filterlist = flist

        return self._filterlist


class LabelFilter(django_filters.FilterSet):

    type = CharListFilter(label=_("Label type"))
    country__printable_name = CharListFilter(label=_("Country"))

    class Meta:
        model = Label
        fields = [
            'type',
            'country__printable_name',
        ]

    @property
    def filterlist(self):
        flist = []
        if not hasattr(self, '_filterlist'):
            for name, filter_ in self.filters.iteritems():
                ds = self.queryset.values_list(name, flat=False).order_by(name).annotate(
                    n=models.Count("pk", distinct=True)).distinct()

                # TODO: extreme hackish...
                if name == 'type':
                    nd = []
                    for d in ds:
                        if d[0] == 'NULL':
                            pass
                        else:
                            if d[0] is not None:
                                for x in alibrary_settings.LABELTYPE_CHOICES:
                                    if x[0] == d[0]:
                                        nd.append([d[0], d[1], x[1]])

                    filter_.entries = nd



                elif name == 'country__printable_name':
                    nd = []
                    for d in ds:
                        nd.append([d[0], d[1]])

                    nd.sort()
                    filter_.entries = nd

                else:
                    filter_.entries = ds

                if ds not in flist:
                    flist.append(filter_)

            """
            add some custom queries
            """
            cf = {
                'label': 'Extra filters',
                'name': 'extra_filter',
                'entries': [
                    ['possible_duplicates', '', 'Duplicate detection'],
                ]
            }
            flist.append(cf)

            self._filterlist = flist

        return self._filterlist


class MediaFilter(django_filters.FilterSet):
    license__name = CharListFilter(label=_("License"))
    master_bitrate = CharListFilter(label=_("Bitrate (kbps)"))
    master_encoding = CharListFilter(label=_("Format / Codec"))
    master_samplerate = CharListFilter(label=_("Samplerate (Hz)"))
    mediatype = CharListFilter(label=_("Type"))

    class Meta:
        model = Media
        fields = [
            'license__name',
            'mediatype',
            'master_bitrate',
            'master_encoding',
            'master_samplerate',
            'tempo',
            'lyrics_language',
            'version'
        ]

    @property
    def filterlist(self):

        flist = []

        if not hasattr(self, '_filterlist'):

            for name, filter_ in self.filters.iteritems():

                ds = self.queryset.values_list(name, flat=False).order_by(name).annotate(
                    n=models.Count("pk", distinct=True)).distinct()

                if name == 'master_encoding':
                    nd = []
                    for d in ds:
                        if not d[0] or d[0] == 'NULL':
                            nd.append([d[0], d[1], _('Unknown')])
                        else:
                            nd.append([d[0], d[1], d[0].upper()])

                    filter_.entries = nd

                elif name == 'mediatype':
                    nd = []
                    for d in ds:
                        if d[0] == 'NULL':
                            nd.append([d[0], d[1], _('Unknown')])
                        else:
                            nd.append([d[0], d[1], u'%s' % d[0].replace('_', ' ').title()])

                    filter_.entries = nd


                elif name == 'lyrics_language':
                    from lib.fields.languages import LANGUAGES
                    nd = []
                    for d in ds:
                        for x in LANGUAGES:
                            if x[0] == d[0]:
                                nd.append([d[0], d[1], x[1]])


                    nd.sort()
                    filter_.entries = nd

                elif name == 'version':
                    from alibrary.models.mediamodels import VERSION_CHOICES
                    nd = []
                    for d in ds:
                        for x in VERSION_CHOICES:
                            if x[0] == d[0]:
                                nd.append([d[0], d[1], x[1]])


                    nd.sort()
                    filter_.entries = nd

                else:
                    filter_.entries = ds

                if ds not in flist:
                    flist.append(filter_)

            """
            add some custom queries
            """
            cf = {
                'label': 'Extra filters',
                'name': 'extra_filter',
                'entries': [
                    ['unassigned', '', 'Unassigned tracks'],
                    ['possible_duplicates', '', 'Duplicate detection'],
                    ['possible_duplicates_incl_artists', '', 'Duplicate (incl. Artist) detection'],
                ]
            }
            flist.append(cf)

            self._filterlist = flist

        return self._filterlist



DAY_CHOICES = (
    (0, _('Mon')),
    (1, _('Tue')),
    (2, _('Wed')),
    (3, _('Thu')),
    (4, _('Fri')),
    (5, _('Sat')),
    (6, _('Sun')),
)

class PlaylistFilter(django_filters.FilterSet):
    type = CharListFilter(label=_("Type"))
    status = CharListFilter(label=_("Status"))
    target_duration = CharListFilter(label=_("Target Duration"))
    dayparts = CharListFilter(label="Dayparts")
    weather__name = CharListFilter(label="Weather")
    seasons__name = CharListFilter(label="Season")
    class Meta:
        model = Playlist
        fields = [
            'type',
            'status',
            'target_duration',
            'dayparts',
            'weather__name',
            'seasons__name',
            'rotation'
        ]

    def __init__(self, *args, **kwargs):
        super(PlaylistFilter, self).__init__(*args, **kwargs)


    @property
    def filterlist(self):

        flist = []

        if not hasattr(self, '_filterlist'):

            for name, filter_ in self.filters.iteritems():

                ds = self.queryset.values_list(name, flat=False).order_by(name).annotate(
                    n=models.Count("pk", distinct=True)).distinct()


                if name == 'type':
                    nd = []
                    for d in ds:
                        if d[0] == 'NULL':
                            nd.append([d[0], d[1], _('Unknown')])
                        else:
                            if d[0] is not None:
                                for x in alibrary_settings.PLAYLIST_TYPE_CHOICES:
                                    if x[0] == d[0]:
                                        nd.append([d[0], d[1], '%s' % x[1]])

                    filter_.entries = nd

                elif name == 'status':
                    nd = []
                    for d in ds:
                        if d[0] == 'NULL':
                            pass
                        else:
                            if d[0] is not None:
                                for x in alibrary_settings.PLAYLIST_STATUS_CHOICES:
                                    if x[0] == d[0]:
                                        nd.append([d[0], d[1], '%s' % x[1]])

                    filter_.entries = nd

                elif name == 'target_duration':
                    nd = []
                    for d in ds:
                        if d[0] == 'NULL':
                            pass
                        else:
                            if d[0] is not None:
                                for x in alibrary_settings.PLAYLIST_TARGET_DURATION_CHOICES:
                                    if x[0] == d[0]:
                                        nd.append([d[0], d[1], _('%s minutes') % x[1]])

                    nd.sort()
                    filter_.entries = nd

                elif name == 'dayparts':
                    from alibrary.models import Daypart
                    nd = []
                    for d in ds:
                        try:
                            dp = Daypart.objects.get(pk=int(d[0]))
                            nd.append([d[0], d[1], dp])

                        except:
                            pass

                    nd.sort()
                    filter_.entries = nd

                else:
                    filter_.entries = ds

                if ds not in flist:
                    flist.append(filter_)

            """
            add some custom queries
            TODO: just temporary. refactor to propper solution...
            """
            cf = {
                'label': 'Archive',
                'name': 'archived_filter',
                'entries': [
                    ['no', '', 'Not archived'],
                    ['yes', '', 'Archived'],
                ]
            }
            flist.append(cf)

            self._filterlist = flist

        return self._filterlist
