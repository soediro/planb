# Generated by Django 2.0.2 on 2018-04-05 11:59

import datetime
from django.db import migrations, models
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('planb', '0006_last_monthly_report'),
    ]

    operations = [
        migrations.RenameField(
            model_name='hostconfig',
            old_name='date_complete', new_name='last_ok',
        ),
        migrations.RenameField(
            model_name='hostconfig',
            old_name='failure_datetime', new_name='first_fail',
        ),
        migrations.RemoveField(
            model_name='hostconfig',
            name='file_to_check',
        ),
        migrations.RemoveField(
            model_name='hostconfig',
            name='priority',
        ),
        migrations.AlterField(
            model_name='hostconfig',
            name='first_fail',
            field=models.DateTimeField(blank=True, null=True, verbose_name='First backup failure'),
        ),
        migrations.AlterField(
            model_name='hostconfig',
            name='last_ok',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Last backup success'),
        ),
        migrations.AddField(
            model_name='hostconfig',
            name='last_run',
            field=models.DateTimeField(default=datetime.datetime(1970, 1, 2, 0, 0, tzinfo=utc), verbose_name='Last backup attempt'),
        ),
    ]
