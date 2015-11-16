# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.dispatch import receiver
from django.db.models.signals import post_save

#from .models import Waveform
__version__ = '0.0.1'


@receiver(post_save, sender='alibrary.Media')
def media_post_save(sender, instance, created, **kwargs):

    from .models import Waveform, Format

    #Waveform.objects.get_or_create_for_media(media=instance, type=Waveform.WAVEFORM)
    #Waveform.objects.get_or_create_for_media(media=instance, type=Waveform.SPECTROGRAM)

    Format.objects.get_or_create_for_media(media=instance, encoding=Format.MP3, quality=Format.DEFAULT)



