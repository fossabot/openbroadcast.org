#-*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import sys
import tqdm
from optparse import make_option
from django.contrib.auth.models import User
from django.conf import settings
from django.core.management.base import BaseCommand, NoArgsCommand

from massimporter.models import Massimport, MassimportFile

DEFAULT_LIMIT = 100
MEDIA_ROOT = getattr(settings, 'MEDIA_ROOT', None)

class Massimporter(object):

    def __init__(self, command, *args, **kwargs):

        self.directory = kwargs.get('directory')
        self.limit = kwargs.get('limit')
        self.rescan = kwargs.get('rescan')
        self.id = kwargs.get('id')
        self.reset_files = kwargs.get('reset_files')
        self.import_session = kwargs.get('import_session')
        self.username = kwargs.get('username')
        self.collection_name = kwargs.get('collection_name')
        self.verbosity = int(kwargs.get('verbosity', 1))

        if self.directory:
            if not self.directory.startswith(MEDIA_ROOT):
                print 'directory has to be inside MEDIA_ROOT: {}'.format(MEDIA_ROOT)
                sys.exit(2)


    def list(self):
        """
        returns a list with status information for all existing sessions
        """

        massimports = Massimport.objects.order_by('status').all()

        print '--------------------------------------------------------------------'
        print 'id\tstatus\tfiles\tuser\tdirectory\t'
        print '--------------------------------------------------------------------'
        for item in massimports:
            print '{id}\t{status}\t{num_files}\t{username}\t{directory}'.format(
                id=item.pk,
                status=item.get_status_display(),
                username=item.user,
                num_files=item.files.count(),
                directory=item.directory,
            )


    def scan(self):

        massimport = Massimport.objects.get(pk=int(self.id))
        massimport.scan()

    def delete(self):

        Massimport.objects.get(pk=int(self.id)).delete()

    def update(self):

        massimport = Massimport.objects.get(pk=int(self.id))
        massimport.update()

    def status(self):

        massimport = Massimport.objects.get(pk=int(self.id))
        massimport.update()

        print '--------------------------------------------------------------------'
        print 'Status'
        print '--------------------------------------------------------------------'

        for status in MassimportFile.STATUS_CHOICES:
            count = massimport.files.filter(status=status[0]).count()
            if count:
                print('{}:    \t{}'.format(
                    status[1],
                    count
                ))

        print '===================================================================='
        print('Total:    \t{}'.format(massimport.files.all().count()))



    def start(self):

        if not self.directory or not os.path.isdir(self.directory):
            print 'directory missing or does not exist'
            sys.exit(2)

        if not self.directory.endswith('/'):
            self.directory += '/'

        if Massimport.objects.filter(directory=self.directory).exists():
            print 'Massimport (ID: {}) already exists for: {}'.format(
                Massimport.objects.get(directory=self.directory).pk,
                self.directory
            )
            sys.exit(2)

        if not self.username or not User.objects.filter(username=self.username).exists():
            print 'username missing or user does not exist'
            sys.exit(2)

        massimport = Massimport(
            directory=self.directory,
            user=User.objects.get(username=self.username),
            collection_name=self.collection_name
        )

        massimport.save()
        massimport.scan()

    def enqueue(self):

        massimport = Massimport.objects.get(pk=int(self.id))

        print 'queing {} files'.format(self.limit)
        print 'got: {}'.format(len(massimport.files.filter(status=0)[0:self.limit]))

        for item in massimport.files.filter(status=0)[0:self.limit]:
            item.enqueue()




class Command(BaseCommand):

    def add_arguments(self, parser):

        parser.add_argument('action')

        parser.add_argument('-d', '--directory',
                            dest='directory',
                            default=False)

        parser.add_argument('-u', '--username',
                            dest='username',
                            default=False)

        parser.add_argument('-i', '--id',
                            dest='id',
                            default=False)

        parser.add_argument('-l', '--limit',
                            dest='limit',
                            default=DEFAULT_LIMIT)

        parser.add_argument('-c', '--collection',
                            dest='collection_name')

    def handle(self, *args, **options):

        action = options.get('action', None)

        worker = Massimporter(command=self, **options)
        command = getattr(worker, action)
        if command:
            command()


