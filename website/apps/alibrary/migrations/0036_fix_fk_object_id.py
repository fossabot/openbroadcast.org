# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('alibrary', '0035_auto_20170821_1728'),
    ]

    operations = [
        migrations.AlterField(
            model_name='relation',
            name='object_id',
            field=models.PositiveIntegerField(),
        ),
    ]
