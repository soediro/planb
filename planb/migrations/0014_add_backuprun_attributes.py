# Generated by Django 2.1.10 on 2019-07-08 12:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planb', '0013_optional_dutree_and_is_booleans'),
    ]

    operations = [
        migrations.AddField(
            model_name='backuprun',
            name='attributes',
            field=models.TextField(blank=True, help_text='YAML-safe dictionary of backup run attributes.'),
        ),
        migrations.AlterField(
            model_name='backuprun',
            name='success',
            field=models.BooleanField(blank=True, default=False, help_text='If the backup succeeded, the other values can be trusted.'),
        ),
        migrations.AlterField(
            model_name='fileset',
            name='do_snapshot_size_listing',
            field=models.BooleanField(blank=True, default=True, help_text='Summarize disk usage after the transport. This can be slow if there are many files.', verbose_name='Create disk usage summary'),
        ),
    ]
