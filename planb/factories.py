import factory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice

from planb.storage import pools


class UserFactory(DjangoModelFactory):
    class Meta:
        model = 'auth.User'
        inline_args = ('username', 'email', 'password')

    username = factory.Faker('user_name')
    email = factory.Faker('email')
    password = factory.Faker('password')
    is_active = True

    @classmethod
    def _create(cls, model_class, username, email, password, **kwargs):
        instance = model_class.objects._create_user(
            username, email, password, **kwargs)
        instance.raw_password = password
        return instance


class HostGroupFactory(DjangoModelFactory):
    name = factory.Faker('domain_word')

    class Meta:
        model = 'planb.HostGroup'
        django_get_or_create = ('name',)


class FilesetFactory(DjangoModelFactory):
    host_prefix = factory.Faker('hostname', levels=0)
    host_suffix = factory.Faker('domain_word')
    tld = factory.Faker('tld')

    @factory.lazy_attribute
    def friendly_name(self):
        # Set friendly name as the full hostname within the hostgroup domain.
        return '.'.join((
            self.host_prefix, self.host_suffix, self.hostgroup.name, self.tld))

    storage_alias = FuzzyChoice(pools)
    hostgroup = factory.SubFactory(HostGroupFactory)

    class Meta:
        model = 'planb.Fileset'
        exclude = ['host_prefix', 'host_suffix', 'tld']


class BackupRunFactory(DjangoModelFactory):
    fileset = factory.SubFactory(FilesetFactory)

    duration = factory.Faker('pyint')
    success = factory.Faker('pybool')
    total_size_mb = factory.Faker('pyint')

    @factory.lazy_attribute
    def snapshot_size_mb(self):
        return factory.Faker('pyint', max_value=self.total_size_mb).generate()

    attributes = 'do_snapshot_size_listing: false'
    snapshot_size_listing = ''

    class Meta:
        model = 'planb.BackupRun'
