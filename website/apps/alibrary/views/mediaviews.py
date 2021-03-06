# -*- coding: utf-8 -*-
import os

from django.views.generic import DetailView, ListView, UpdateView
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, HttpResponseForbidden, Http404, HttpResponseRedirect, HttpResponseBadRequest
from django.core.exceptions import PermissionDenied
from django.views.decorators.cache import never_cache
from django.db.models import Q, Case, When
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext as _
from django.contrib import messages
from haystack.backends import SQ
from haystack.query import SearchQuerySet
from haystack.inputs import AutoQuery

from tagging.models import Tag
from sendfile import sendfile

from pure_pagination.mixins import PaginationMixin
from braces.views import PermissionRequiredMixin, LoginRequiredMixin
import actstream
from alibrary.models import Media, Playlist, PlaylistItem, Artist, Release
from alibrary.forms import MediaForm, MediaActionForm, MediaRelationFormSet, ExtraartistFormSet, MediaartistFormSet
from alibrary.filters import MediaFilter

from tagging_extra.utils import calculate_cloud
from lib.util import change_message
from lib.util.form_errors import merge_form_errors

import logging
log = logging.getLogger(__name__)

ALIBRARY_PAGINATE_BY = getattr(settings, 'ALIBRARY_PAGINATE_BY', (12,24,36,120))
ALIBRARY_PAGINATE_BY_DEFAULT = getattr(settings, 'ALIBRARY_PAGINATE_BY_DEFAULT', 12)

ORDER_BY = [
    {
        'key': 'name',
        'name': _('Name')
    },
    {
        'key': 'artist__name',
        'name': _('Artist name')
    },
    {
        'key': 'master_duration',
        'name': _('Duration')
    },
    {
        'key': 'tempo',
        'name': _('BPM')
    },
    {
        'key': 'updated',
        'name': _('Last modified')
    },
    {
        'key': 'created',
        'name': _('Creation date')
    },
]

class MediaListView(PaginationMixin, ListView):

    object = Media
    paginate_by = ALIBRARY_PAGINATE_BY_DEFAULT

    model = Media
    extra_context = {}

    def get_paginate_by(self, queryset):

        ipp = self.request.GET.get('ipp', None)
        if ipp:
            try:
                if int(ipp) in ALIBRARY_PAGINATE_BY:
                    return int(ipp)
            except Exception as e:
                pass

        return self.paginate_by

    def get_context_data(self, **kwargs):
        context = super(MediaListView, self).get_context_data(**kwargs)

        self.extra_context['filter'] = self.filter
        self.extra_context['relation_filter'] = self.relation_filter
        self.extra_context['tagcloud'] = self.tagcloud
        # for the ordering-box
        self.extra_context['order_by'] = ORDER_BY

        # active tags
        if self.request.GET.get('tags', None):
            tag_ids = []
            for tag_id in self.request.GET['tags'].split(','):
                tag_ids.append(int(tag_id))
            self.extra_context['active_tags'] = tag_ids

        self.extra_context['list_style'] = self.request.GET.get('list_style', 's')
        self.extra_context['get'] = self.request.GET
        context.update(self.extra_context)

        return context


    def get_queryset(self, **kwargs):

        kwargs = {}
        self.tagcloud = None
        q = self.request.GET.get('q', None)

        # haystack version
        if q:
            #sqs = SearchQuerySet().models(Media).filter(SQ(content__contains=q) | SQ(content_auto=q))
            #sqs = SearchQuerySet().models(Media).filter(content=AutoQuery(q))
            sqs = SearchQuerySet().models(Media).filter(text_auto=AutoQuery(q))

            pk_list = [result.object.pk for result in sqs]
            preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(pk_list)])
            qs = Media.objects.filter(id__in=pk_list).order_by(preserved).distinct()
        else:
            qs = Media.objects.all()

        # if q:
        #     #qs = Media.objects.filter(Q(name__icontains=q)\
        #     #| Q(release__name__icontains=q)\
        #     #| Q(artist__name__icontains=q))\
        #     #.distinct()
        #     qs = Media.objects.filter(name__icontains=q).distinct()
        # else:
        #     qs = Media.objects.all()


        order_by = self.request.GET.get('order_by', 'created')
        direction = self.request.GET.get('direction', 'descending')

        if order_by and direction:
            if direction == 'descending':
                qs = qs.order_by('-%s' % order_by)
            else:
                qs = qs.order_by('%s' % order_by)


        # special relation filters
        self.relation_filter = []

        artist_filter = self.request.GET.get('artist', None)
        if artist_filter:

            a = get_object_or_404(Artist, slug=artist_filter)
            qs = qs.filter(pk__in=(r.id for r in a.get_media())).distinct()

            f = {'item_type': 'artist' , 'item': a, 'label': _('Artist')}
            self.relation_filter.append(f)

        release_filter = self.request.GET.get('release', None)
        if release_filter:

            r = get_object_or_404(Release, slug=release_filter)
            qs = qs.filter(release__pk=r.pk).distinct()

            f = {'item_type': 'release' , 'item': r, 'label': _('Release')}
            self.relation_filter.append(f)

        # filter by import session
        import_session = self.request.GET.get('import', None)
        if import_session:
            from importer.models import Import
            from django.contrib.contenttypes.models import ContentType
            import_session = get_object_or_404(Import, pk=int(import_session))
            ctype = ContentType.objects.get(model='media')
            ids = import_session.importitem_set.filter(content_type=ctype.pk).values_list('object_id',)
            qs = qs.filter(pk__in=ids).distinct()

        # filter by user
        creator_filter = self.request.GET.get('creator', None)
        if creator_filter:
            from django.contrib.auth.models import User
            creator = get_object_or_404(User, username='%s' % creator_filter)
            qs = qs.filter(creator=creator).distinct()
            f = {'item_type': 'release' , 'item': creator, 'label': _('Added by')}
            self.relation_filter.append(f)


        # "extra-filters" (to provide some arbitary searches)
        extra_filter = self.request.GET.get('extra_filter', None)
        if extra_filter:
            if extra_filter == 'unassigned':
                qs = qs.filter(release=None).distinct()

            if extra_filter == 'possible_duplicates':
                from django.db.models import Count
                dupes = Media.objects.values('name').annotate(Count('id')).filter(id__count__gt=1)
                qs = qs.filter(name__in=[item['name'] for item in dupes])
                if not order_by:
                    qs = qs.order_by('name')

            if extra_filter == 'possible_duplicates_incl_artists':
                from django.db.models import Count
                dupes = Media.objects.values('name').annotate(Count('id')).filter(id__count__gt=1)
                qs = qs.filter(name__in=[item['name'] for item in dupes])
                if not order_by:
                    qs = qs.order_by('name')




        # apply filters
        self.filter = MediaFilter(self.request.GET, queryset=qs)
        # self.filter = ReleaseFilter(self.request.GET, queryset=Release.objects.active().filter(**kwargs))
        qs = self.filter.qs




        stags = self.request.GET.get('tags', None)
        tstags = []
        if stags:
            stags = stags.split(',')
            for stag in stags:
                #print int(stag)
                tstags.append(int(stag))

        if stags:
            qs = Media.tagged.with_all(tstags, qs)


        # rebuild filter after applying tags
        self.filter = MediaFilter(self.request.GET, queryset=qs)


        # tagging / cloud generation
        if qs.exists():
            tagcloud = Tag.objects.usage_for_queryset(qs, counts=True, min_count=0)
            self.tagcloud = calculate_cloud(tagcloud)


        return qs


class MediaDetailView(DetailView):

    model = Media
    extra_context = {}

    def get_context_data(self, **kwargs):

        context = super(MediaDetailView, self).get_context_data(**kwargs)
        obj = kwargs.get('object', None)

        self.extra_context['history'] = []

        # foreign appearance
        ps = []
        try:
            pis = PlaylistItem.objects.filter(object_id=obj.id, content_type=ContentType.objects.get_for_model(obj))
            ps = Playlist.objects.exclude(type='basket').filter(items__in=pis)
        except:
            pass

        self.extra_context['appearance'] = ps
        context.update(self.extra_context)

        return context




class MediaEditView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):

    model = Media
    form_class = MediaForm
    template_name = "alibrary/media_edit.html"
    permission_required = 'alibrary.change_media'
    raise_exception = True
    success_url = '#'

    def __init__(self, *args, **kwargs):
        self.created_artists = {}
        super(MediaEditView, self).__init__(*args, **kwargs)

    def get_initial(self):
        self.initial.update({
            'user': self.request.user,
            'd_tags': ','.join(t.name for t in self.object.tags)
        })
        return self.initial

    def get_context_data(self, **kwargs):
        ctx = super(MediaEditView, self).get_context_data(**kwargs)
        ctx['named_formsets'] = self.get_named_formsets()
        # TODO: is this a good way to pass the instance main form?
        ctx['form_errors'] = self.get_form_errors(form=ctx['form'])

        return ctx

    def get_named_formsets(self):

        return {
            'action': MediaActionForm(self.request.POST or None, prefix='action'),
            'relation': MediaRelationFormSet(self.request.POST or None, instance=self.object, prefix='relation'),
            'extraartist': ExtraartistFormSet(self.request.POST or None, instance=self.object, prefix='extraartist'),
            'mediaartists': MediaartistFormSet(self.request.POST or None, instance=self.object, prefix='mediaartists'),
        }

    def get_form_errors(self, form=None):

        named_formsets = self.get_named_formsets()
        named_formsets.update({'form': form})
        form_errors = merge_form_errors([formset for name, formset in named_formsets.items()])

        return form_errors

    def form_valid(self, form):

        named_formsets = self.get_named_formsets()

        if not all((x.is_valid() for x in named_formsets.values())):
            return self.render_to_response(self.get_context_data(form=form))

        self.object = form.save(commit=False)

        for name, formset in named_formsets.items():
            formset_save_func = getattr(self, 'formset_{0}_valid'.format(name), None)
            if formset_save_func is not None:
                formset_save_func(formset)
            else:
                formset.save()

        msg = change_message.construct(self.request, form, [named_formsets['relation'], named_formsets['extraartist'],])

        d_tags = form.cleaned_data['d_tags']
        if d_tags:
            msg = change_message.parse_tags(obj=self.object, d_tags=d_tags, msg=msg)
            self.object.tags = d_tags


        self.object.last_editor = self.request.user
        actstream.action.send(self.request.user, verb=_('updated'), target=self.object)

        # revisions disabled -> needs refactoring
        self.object = form.save()
        messages.add_message(self.request, messages.INFO, 'Object updated')

        return HttpResponseRedirect(self.object.get_edit_url())
        # return HttpResponseRedirect('')




# @never_cache
# def media_download(request, slug, format, version):
#
#     return sendfile(request, cache_file, attachment=True, attachment_filename=filename)


