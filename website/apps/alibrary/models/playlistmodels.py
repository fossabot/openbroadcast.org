# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging
import os
import uuid

import arating
import tagging
from alibrary import settings as alibrary_settings
from alibrary.models import MigrationMixin, Daypart
from alibrary.util.storage import get_dir_for_object, OverwriteStorage
from celery.task import task
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models.signals import post_save
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _
from django.utils import timezone
from django_extensions.db.fields import AutoSlugField
from django_extensions.db.fields.json import JSONField
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from lib.fields import extra
from tagging.registry import register as tagging_register

from ..util.mixdown_client import MixdownAPIClient


try:
    from urllib.request import urlopen # for python 3.0 and later
except ImportError:
    from urllib2 import urlopen # fall back to python 2's urllib2

log = logging.getLogger(__name__)

DURATION_MAX_DIFF = 2500  # ms


# TODO: remove. still referenced in migrations, so left here for the moment
def filename_by_uuid(instance, filename):
    filename, extension = os.path.splitext(filename)
    path = "playlists/"
    filename = str(instance.uuid).replace('-', '/') + extension
    return os.path.join(path, filename)


def upload_image_to(instance, filename):
    filename, extension = os.path.splitext(filename)
    return os.path.join(get_dir_for_object(instance), 'playlists{}'.format(extension.lower()))

def upload_mixdown_to(instance, filename):
    filename, extension = os.path.splitext(filename)
    return os.path.join(get_dir_for_object(instance), 'mixdown{}'.format(extension.lower()))


class Season(models.Model):
    name = models.CharField(max_length=200)
    date_start = models.DateField(null=True, blank=True)
    date_end = models.DateField(null=True, blank=True)

    class Meta:
        app_label = 'alibrary'
        verbose_name = _('Season')
        verbose_name_plural = _('Seasons')
        ordering = ('-name',)

    def __unicode__(self):
        return '%s' % (self.name)


class Weather(models.Model):
    name = models.CharField(max_length=200)

    class Meta:
        app_label = 'alibrary'
        verbose_name = _('Weather')
        verbose_name_plural = _('Weather')
        ordering = ('-name',)

    def __unicode__(self):
        return '%s' % (self.name)


class Series(models.Model):
    name = models.CharField(max_length=200)
    slug = AutoSlugField(populate_from='name', editable=True, blank=True, overwrite=True)
    # uuid = UUIDField()
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    description = extra.MarkdownTextField(blank=True, null=True)

    class Meta:
        app_label = 'alibrary'
        verbose_name = _('Series')
        verbose_name_plural = _('Series')
        ordering = ('-name',)

    def __unicode__(self):
        return '%s' % (self.name)




class Playlist(MigrationMixin, models.Model):
    name = models.CharField(max_length=200)
    slug = AutoSlugField(populate_from='name', editable=True, blank=True, overwrite=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)

    status = models.PositiveIntegerField(
        default=0,
        choices=alibrary_settings.PLAYLIST_STATUS_CHOICES
    )
    type = models.CharField(
        max_length=12,
        default='basket', null=True,
        choices=alibrary_settings.PLAYLIST_TYPE_CHOICES
    )
    broadcast_status = models.PositiveIntegerField(
        default=0,
        choices=alibrary_settings.PLAYLIST_BROADCAST_STATUS_CHOICES
    )
    broadcast_status_messages = JSONField(
        blank=True, null=True, default=None
    )

    EDIT_MODE_CHOICES = (
        (0, _('Compact')),
        (1, _('Medium')),
        (2, _('Extended')),
    )
    edit_mode = models.PositiveIntegerField(default=2, choices=EDIT_MODE_CHOICES)

    rotation = models.BooleanField(default=True)
    rotation_date_start = models.DateField(
        verbose_name=_('Rotate from'),
        blank=True, null=True
    )
    rotation_date_end = models.DateField(
        verbose_name=_('Rotate until'),
        blank=True, null=True
    )

    main_image = models.ImageField(
        verbose_name=_('Image'),
        upload_to=upload_image_to,
        storage=OverwriteStorage(),
        null=True, blank=True
    )

    # relations
    user = models.ForeignKey(
        User,
        null=True, blank=True, default=None
    )
    items = models.ManyToManyField(
        'PlaylistItem',
        through='PlaylistItemPlaylist',
        blank=True
    )

    # tagging (d_tags = "display tags")
    d_tags = tagging.fields.TagField(
        max_length=1024,
        verbose_name='Tags',
        blank=True, null=True
    )

    # updated/calculated on save
    duration = models.IntegerField(
        null=True, default=0)

    target_duration = models.PositiveIntegerField(
        default=0, null=True,
        choices=alibrary_settings.PLAYLIST_TARGET_DURATION_CHOICES
    )

    dayparts = models.ManyToManyField(
        Daypart,
        blank=True,
        related_name='daypart_plalists'
    )
    seasons = models.ManyToManyField(
        'Season',
        blank=True,
        related_name='season_plalists'
    )
    weather = models.ManyToManyField(
        'Weather',
        blank=True,
        related_name='weather_plalists'
    )

    # series
    series = models.ForeignKey(
        Series,
        null=True, blank=True,
        on_delete=models.SET_NULL
    )
    series_number = models.PositiveIntegerField(
        null=True, blank=True
    )

    # is currently selected as default?
    is_current = models.BooleanField(
        _('Currently selected?'),
        default=False
    )

    description = extra.MarkdownTextField(
        blank=True, null=True
    )

    # auto-update
    created = models.DateTimeField(
        auto_now_add=True, editable=False
    )
    updated = models.DateTimeField(
        auto_now=True, editable=False
    )

    mixdown_file = models.FileField(
        null=True, blank=True,
        upload_to=upload_mixdown_to
    )

    # meta
    class Meta:
        app_label = 'alibrary'
        verbose_name = _('Playlist')
        verbose_name_plural = _('Playlists')
        ordering = ('-updated',)

        permissions = (
            ('view_playlist', 'View Playlist'),
            ('edit_playlist', 'Edit Playlist'),
            ('schedule_playlist', 'Schedule Playlist'),
            ('admin_playlist', 'Edit Playlist (extended)'),
        )

    def __unicode__(self):
        return self.name

    @property
    def sorted_items(self):
        return self.items.order_by('playlistitemplaylist__position')

    def get_absolute_url(self):
        return reverse('alibrary-playlist-detail', kwargs={
            'slug': self.slug,
        })

    def get_edit_url(self):
        return reverse("alibrary-playlist-edit", args=(self.pk,))

    def get_delete_url(self):
        return reverse("alibrary-playlist-delete", args=(self.pk,))

    def get_admin_url(self):
        return reverse("admin:alibrary_playlist_change", args=(self.pk,))

    def get_duration(self):
        duration = 0
        try:
            for item in self.items.all():
                duration += item.content_object.get_duration()
                pip = PlaylistItemPlaylist.objects.get(playlist=self, item=item)
                duration -= pip.cue_in
                duration -= pip.cue_out
                duration -= pip.fade_cross
        except:
            pass

        return duration

    def get_emissions(self):
        from abcast.models import Emission
        ctype = ContentType.objects.get_for_model(self)
        emissions = Emission.objects.filter(content_type__pk=ctype.id, object_id=self.id).order_by('-time_start')
        return emissions

    def get_api_url(self):
        return reverse('api_dispatch_detail', kwargs={
            'api_name': 'v1',
            'resource_name': 'library/playlist',
            'pk': self.pk
        }) + ''

    def get_api_simple_url(self):
        return reverse('api_dispatch_detail', kwargs={
            'api_name': 'v1',
            'resource_name': 'library/simpleplaylist',
            'pk': self.pk
        }) + ''

    def can_be_deleted(self):

        can_delete = False
        reason = _('This playlist cannot be deleted.')

        if self.type == 'basket':
            can_delete = True
            reason = None

        if self.type == 'playlist':
            can_delete = False
            reason = _('Playlist "%s" is public. It cannot be deleted anymore.' % self.name)

        if self.type == 'broadcast':
            can_delete = False
            reason = _('Playlist "%s" published for broadcast. It cannot be deleted anymore.' % self.name)

        return can_delete, reason

    def get_transform_status(self, target_type):
        """
        check if transformation is possible /
        what needs to be done
        Not so nicely here - but...
        """

        status = False

        """
        criterias = [
            {
                'key': 'tags',
                'name': _('Tags'),
                'status': True,
                'warning': _('Please add some tags'),
            },
            {
                'key': 'description',
                'name': _('Description'),
                'status': False,
                'warning': _('Please add a description'),
            }
        ]
        """

        criterias = []

        # "basket" only used while dev...
        if target_type == 'basket':
            status = True

        if target_type == 'playlist':
            status = True
            # tags
            tag_count = self.tags.count()
            if tag_count < 1:
                status = False
            criteria = {
                'key': 'tags',
                'name': _('Tags'),
                'status': tag_count > 0,
                'warning': _('Please add some tags'),
            }
            criterias.append(criteria)
            # scheduled
            if self.type == 'broadcast':
                schedule_count = self.get_emissions().count()
                if schedule_count > 0:
                    status = False
                criteria = {
                    'key': 'scheduled',
                    'name': _('Playlist already scheduled') if schedule_count > 0 else _('Playlist not scheduled'),
                    'status': schedule_count < 1,
                    'warning': _(
                        'This playlist has already ben scheduled %s times. Remove all scheduler entries to "un-broadcast" this playlist.' % schedule_count),
                }
                if schedule_count > 0:
                    criterias.append(criteria)

        if target_type == 'broadcast':
            status = True
            # tags
            tag_count = self.tags.count()
            if tag_count < 1:
                status = False
            criteria = {
                'key': 'tags',
                'name': _('Tags'),
                'status': tag_count > 0,
                'warning': _('Please add some tags'),
            }
            criterias.append(criteria)

            # dayparts
            dp_count = self.dayparts.count()
            if not dp_count:
                status = False
            criteria = {
                'key': 'dayparts',
                'name': _('Dayparts'),
                'status': dp_count > 0,
                'warning': _('Please specify the dayparts'),
            }
            criterias.append(criteria)

            # duration
            if not self.broadcast_status == 1:
                status = False
            criteria = {
                'key': 'duration',
                'name': _('Duration'),
                'status': True if self.broadcast_status == 1 else False,
                'warning': _('Durations do not match'),
                # 'warning': ', '.join(self.broadcast_status_messages),
            }
            criterias.append(criteria)

        transformation = {
            'criterias': criterias,
            'status': status
        }

        return transformation

    def add_items_by_ids(self, ids, ct, timing=None):

        from alibrary.models.mediamodels import Media

        log = logging.getLogger('alibrary.playlistmodels.add_items_by_ids')
        log.debug('Media ids: %s' % (ids))
        log.debug('Content Type: %s' % (ct))

        for id in ids:
            id = int(id)

            co = None

            if ct == 'media':
                co = Media.objects.get(pk=id)

            if ct == 'jingle':
                from abcast.models import Jingle
                co = Jingle.objects.get(pk=id)

            if co:

                i = PlaylistItem(content_object=co)
                i.save()
                """
                ctype = ContentType.objects.get_for_model(co)
                item, created = PlaylistItem.objects.get_or_create(object_id=co.pk, content_type=ctype)
                """

                pi, created = PlaylistItemPlaylist.objects.get_or_create(item=i, playlist=self,
                                                                         position=self.items.count())

                if timing:
                    try:
                        pi.fade_in = timing['fade_in']
                        pi.fade_out = timing['fade_out']
                        pi.cue_in = timing['cue_in']
                        pi.cue_out = timing['cue_out']
                        pi.save()
                    except:
                        pass

        self.save()

    def reorder_items_by_uuids(self, uuids):

        i = 0

        for uuid in uuids:
            pi = PlaylistItemPlaylist.objects.get(uuid=uuid)
            pi.position = i
            pi.save()

            i += 1

        self.save()

    """
    old method - for non-generic playlists
    """

    # def add_media_by_ids(self, ids):
    #
    #     from alibrary.models.mediamodels import Media
    #
    #     log = logging.getLogger('alibrary.playlistmodels.add_media_by_id')
    #     log.debug('Media ids: %s' % (ids))
    #
    #     for id in ids:
    #         id = int(id)
    #
    #         m = Media.objects.get(pk=id)
    #         pm = PlaylistMedia(media=m, playlist=self, position=self.media.count())
    #         pm.save()
    #
    #         self.save()

    def convert_to(self, type):

        log.debug('requested to convert "%s" from %s to %s' % (self.name, self.type, type))

        if type == 'broadcast':
            self.broadcast_status, self.broadcast_status_messages = self.self_check()

        transformation = self.get_transform_status(type)
        status = transformation['status']

        if type == 'broadcast' and status:
            _status, messages = self.self_check()
            if _status == 1:
                status = True

        if status:
            self.type = type
            self.save()

        return self, status

    def get_items(self):
        pis = PlaylistItemPlaylist.objects.filter(playlist=self).order_by('position')
        items = []
        for pi in pis:
            item = pi.item
            item.cue_in = pi.cue_in
            item.cue_out = pi.cue_out
            item.fade_in = pi.fade_in
            item.fade_out = pi.fade_out
            item.fade_cross = pi.fade_cross
            # get the actual playout duration
            try:
                # print '// getting duration for:'
                # print '%s - %s' % (item.content_object.pk, item.content_object.name)
                # print 'obj duration: %s' % item.content_object.duration_s
                item.playout_duration = item.content_object.duration_ms - item.cue_in - item.cue_out - item.fade_cross
            except Exception as e:
                print 'unable to get duration: %s' % e
                item.playout_duration = 0

            items.append(item)
        return items

    def self_check(self):
        """
        check if everything is fine to be 'schedulable'
        """

        log.info('Self check requested for: %s' % self.name)

        status = 1  # set to 'OK'
        messages = []

        try:

            # check ready-status of related media

            for item in self.items.all():
                # log.debug('Self check content object: %s' % item.content_object)
                # log.debug('Self check master: %s' % item.content_object.master)
                # log.debug('Self check path: %s' % item.content_object.master.path)

                # check if file available
                try:
                    with open(item.content_object.master.path):
                        pass
                except IOError as e:
                    log.warning(_('File does not exists: %s | %s') % (e, item.content_object.master.path))
                    status = 99
                    messages.append(_('File does not exists: %s | %s') % (e, item.content_object.master.path))

                """
                pip = PlaylistItemPlaylist.objects.get(playlist=self, item=item)
                duration -= pip.cue_in
                duration -= pip.cue_out
                duration -= pip.fade_cross
                """

            # check duration & matching target_duration
            """
            compare durations. target: in seconds | calculated duration in milliseconds
            """
            diff = self.get_duration() - self.target_duration * 1000
            if abs(diff) > DURATION_MAX_DIFF:
                messages.append(_('durations do not match. difference is: %s seconds' % int(diff / 1000)))
                log.warning('durations do not match. difference is: %s seconds' % int(diff / 1000))
                status = 2

        except Exception as e:
            messages.append(_('Validation error: %s ' % e))
            log.warning('validation error: %s ' % e)
            status = 99

        if status == 1:
            log.info('Playlist "%s" checked - all fine!' % (self.name))

        return status, messages


    ###################################################################
    # playlist mixdown
    ###################################################################
    def get_mixdown(self):
        """
        get mixdown from api 
        """
        return MixdownAPIClient().get_for_playlist(self)


    def request_mixdown(self):
        """
        request (re-)creation of mixdown
        """
        return MixdownAPIClient().request_for_playlist(self)


    def download_mixdown(self):
        """
        download generated mixdown from api & store locally (in `mixdown_file` field)
        """
        if not self.mixdown:
            log.info('mixdown not available on api')
            return

        if not self.mixdown['status'] == 3:
            log.info('mixdown not ready on api')
            return

        url = self.mixdown['mixdown_file']

        log.debug('download mixdown from api: {} > {}'.format(url, self.name))

        f_temp = NamedTemporaryFile(delete=True)
        f_temp.write(urlopen(url).read())
        f_temp.flush()

        # wipe existing file
        try:
            self.mixdown_file.delete(False)
        except IOError:
            pass

        self.mixdown_file.save(url.split('/')[-1], File(f_temp))

        return MixdownAPIClient().request_for_playlist(self)


    @cached_property
    def mixdown(self):
        return self.get_mixdown()


    @cached_property
    def is_archived(self):
        if not self.type == 'broadcast':
            return
        if self.rotation_date_end and self.rotation_date_end < timezone.now().date():
            return True


    @cached_property
    def is_upcoming(self):
        if not self.type == 'broadcast':
            return
        if self.rotation_date_start and self.rotation_date_start > timezone.now().date():
            return True



    def save(self, *args, **kwargs):

        # status update
        if self.status == 0:
            self.status = 2

        duration = 0
        try:
            duration = self.get_duration()

        except Exception as e:
            pass

        self.duration = duration

        """
        TODO: maybe move
        """
        self.broadcast_status, self.broadcast_status_messages = self.self_check()
        # print '%s - %s (id: %s)' % (self.broadcast_status, self.name, self.pk)
        # print ', '.join(self.broadcast_status_messages)
        # map to object status (not extremly dry - we know...)
        if self.broadcast_status == 1:
            self.status = 1  # 'ready'
        else:
            self.status = 99  # 'error'

        # self.user = request.user
        super(Playlist, self).save(*args, **kwargs)


try:
    tagging_register(Playlist)
except Exception as e:
    pass

arating.enable_voting_on(Playlist)


def playlist_post_save(sender, **kwargs):
    # obj = kwargs['instance']
    pass


post_save.connect(playlist_post_save, sender=Playlist)


class PlaylistItemPlaylist(models.Model):

    playlist = models.ForeignKey(
        'Playlist', on_delete=models.CASCADE
    )
    item = models.ForeignKey(
        'PlaylistItem', on_delete=models.CASCADE
    )

    # uuid = UUIDField()
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)

    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    position = models.PositiveIntegerField(default=0)
    #
    cue_in = models.PositiveIntegerField(default=0)
    cue_out = models.PositiveIntegerField(default=0)
    fade_in = models.PositiveIntegerField(default=0)
    fade_out = models.PositiveIntegerField(default=0)
    fade_cross = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'alibrary'
        ordering = ('position',)

    def save(self, *args, **kwargs):

        # catch invalid cases

        if int(self.fade_cross) > int(self.fade_out):
            self.fade_cross = int(self.fade_out) - 1

        if int(self.fade_cross) < 0:
            self.fade_cross = 0

        if int(self.cue_in) < 0:
            self.cue_in = 0

        if int(self.cue_out) < 0:
            self.cue_out = 0

        if int(self.fade_in) < 0:
            self.fade_in = 0

        if int(self.fade_out) < 0:
            self.fade_out = 0

        super(PlaylistItemPlaylist, self).save(*args, **kwargs)


class PlaylistItem(models.Model):
    # uuid = UUIDField()
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)

    class Meta:
        app_label = 'alibrary'
        verbose_name = _('Playlist Item')
        verbose_name_plural = _('Playlist Items')
        # ordering = ('-created', )

    ct_limit = models.Q(app_label='alibrary', model='media') | models.Q(app_label='alibrary',
                                                                        model='release') | models.Q(app_label='abcast',
                                                                                                    model='jingle')

    content_type = models.ForeignKey(ContentType, limit_choices_to=ct_limit)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    def __unicode__(self):
        return '%s' % (self.pk)

    def save(self, *args, **kwargs):
        super(PlaylistItem, self).save(*args, **kwargs)


"""
maintenance tasks
(called via management command)
"""
def self_check_playlists():
    """
    (0, _('Undefined')),
    (1, _('OK')),
    (2, _('Warning')),
    (99, _('Error')),
    """

    # do check
    ps = Playlist.objects.filter(type='broadcast')
    for p in ps:
        p.broadcast_status, p.broadcast_status_messages = p.self_check()

        # map to object status (not extremly dry - we know...)
        if p.broadcast_status == 1:
            p.status = 1  # 'ready'
        else:
            p.status = 99  # 'error'

        p.save()

    # display summary
    ps = Playlist.objects.filter(type='broadcast').order_by('-broadcast_status')
    for p in ps:
        print '------------------------------------------------------------'
        print '%s - %s (id: %s)' % (p.broadcast_status, p.name, p.pk)
        print ', '.join(p.broadcast_status_messages)
        print

    print '============================================================'
    print 'Total plalyists (broadcast): %s' % ps.count()
    print 'Undefined:                   %s' % ps.filter(broadcast_status=0).count()
    print 'OK:                          %s' % ps.filter(broadcast_status=1).count()
    print 'Warning:                     %s' % ps.filter(broadcast_status=2).count()
    print 'Error:                       %s' % ps.filter(broadcast_status=99).count()
    print
