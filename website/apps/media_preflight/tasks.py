# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import absolute_import

import logging

from celery import shared_task

from .api_client import MediaPreflightAPIClient

log = logging.getLogger(__name__)


@shared_task
def request_check_for_media(obj):

    client = MediaPreflightAPIClient()
    result = client.request_check_for_media(obj)

    if result:
        log.info('Media id: {} - requested preflight check'.format(obj.pk))
    else:
        log.warning('Media id: {} - unable to request preflight check'.format(obj.pk))


@shared_task
def delete_check_for_media(obj):

    client = MediaPreflightAPIClient()
    result = client.delete_check_for_media(obj)

    if result:
        log.info('Media id: {} - deleted preflight check'.format(obj.pk))
    else:
        log.warning('Media id: {} - unable to delete preflight check'.format(obj.pk))



