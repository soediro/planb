import logging
import os
from datetime import datetime

from django.conf import settings
from django.db import connections, models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from planb.common.subprocess2 import (
    CalledProcessError, check_output)
from planb.fields import FilelistField


from .rsync import RSYNC_EXITCODES, RSYNC_HARMLESS_EXITCODES

logger = logging.getLogger(__name__)

BOGODATE = datetime(1970, 1, 2, tzinfo=timezone.utc)


class TransportChoices(models.PositiveSmallIntegerField):
    SSH = 0
    RSYNC = 1

    def __init__(self, *args, **kwargs):
        choices = (
            (self.SSH, _('ssh (default)')),
            (self.RSYNC, _('rsync (port 873)')),
        )
        super().__init__(default=self.SSH, choices=choices)


class Config(models.Model):
    fileset = models.OneToOneField('planb.Fileset', on_delete=models.CASCADE)

    host = models.CharField(max_length=254)

    src_dir = models.CharField(max_length=254, default='/')
    includes = FilelistField(
        max_length=1023, default=settings.PLANB_DEFAULT_INCLUDES)
    excludes = FilelistField(
        max_length=1023, blank=True)

    transport = TransportChoices()
    user = models.CharField(max_length=254, default='root')

    use_sudo = models.BooleanField(default=False)
    use_ionice = models.BooleanField(default=False)

    rsync_path = models.CharField(
        max_length=31, default=settings.PLANB_RSYNC_BIN)
    ionice_path = models.CharField(
        max_length=31, default='/usr/bin/ionice', blank=True)

    # When files have legacy/Latin-1 encoding, you'll get rsync exit
    # code 23 and this message:
    #   rsync: recv_generator: failed to stat "...":
    #   Invalid or incomplete multibyte or wide character (84)
    # Solution, add: --iconv=utf8,latin1
    flags = models.CharField(
        max_length=511, default='-az --numeric-ids --stats --delete',
        help_text=_(
            'Default "-az --delete", add "--no-perms --chmod=D0700,F600" '
            'for (windows) hosts without permission bits, add '
            '"--iconv=utf8,latin1" for hosts with files with legacy (Latin-1) '
            'encoding.'))

    def __str__(self):
        return '{}: rsync transport'.format(self.fileset)

    def create_exclude_string(self):
        exclude_list = []
        if self.excludes:
            for piece in self.excludes.split():
                exclude_list.append('--exclude=%s' % piece)
        return tuple(exclude_list)

    def create_include_string(self):
        # Create list of includes, with parent-paths included before the
        # includes.
        include_list = []
        for include in self.includes.split():
            included_parts = ''
            elems = include.split('/')

            # Add parent paths.
            for part in elems[0:-1]:
                included_parts = '/'.join([included_parts, part]).lstrip('/')
                include_list.append(included_parts + '/')

            # Add final path. If the basename contains a '*', we treat
            # it as file, otherwise we treat is as dir and add '/***'.
            included_parts = '/'.join([included_parts, elems[-1]]).lstrip('/')
            if '*' in included_parts:
                include_list.append(included_parts)
            else:
                include_list.append(included_parts + '/***')

        # Sorted/uniqued include list, removing duplicates.
        include_list = sorted(set(include_list))

        # Return values with '--include=' prepended.
        return tuple(('--include=' + i) for i in include_list)

    def get_transport_ssh_rsync_path(self):
        """
        Return --rsync-path=... for the ssh-transport.

        May optionally add 'sudo' and 'ionice'.
        """
        flag = ['--rsync-path=']
        if self.use_sudo:
            flag.append('sudo ')
        if self.use_ionice:
            flag.append(self.ionice_path)
            flag.append(' -c2 -n7 ')
        flag.append(self.rsync_path)
        return (''.join(flag),)

    def get_transport_ssh_options(self):
        """
        Get rsync '-e' option which specifies ssh binary and arguments,
        used to set a per-host known_hosts file, and ignore host checking
        on the first run.

        For compatibility with this, you may want this function in your
        planb user .bashrc::

            ssh() {
                for arg in "$@"; do
                    case $arg in
                    -*) ;;
                    *) break ;;
                    esac
                done
                if test -n "$arg"; then
                    host=${arg##*@}
                    /usr/bin/ssh -o HashKnownHosts=no \\
                      -o UserKnownHostsFile=$HOME/.ssh/known_hosts.d/$host "$@"
                else
                    /usr/bin/ssh "$@"
                fi
            }
        """
        option = '-e'
        binary = 'ssh'
        args = self.get_transport_ssh_known_hosts_args()
        return (
            '%(option)s%(binary)s %(args)s' % {
                'option': option, 'binary': binary, 'args': ' '.join(args)},)

    def get_transport_ssh_known_hosts_d(self):
        # FIXME: assert that there is no nastiness in $HOME? This value
        # is placed in the rsync ssh options call later on.
        known_hosts_d = (
            os.path.join(os.environ.get('HOME', ''), '.ssh/known_hosts.d'))
        try:
            os.makedirs(known_hosts_d, 0o755)
        except FileExistsError:
            pass
        return known_hosts_d

    def get_transport_ssh_known_hosts_args(self):
        known_hosts_d = self.get_transport_ssh_known_hosts_d()
        known_hosts_file = os.path.join(known_hosts_d, self.host)

        args = [
            '-o HashKnownHosts=no',
            '-o UserKnownHostsFile=%s' % (known_hosts_file,),
        ]
        if os.path.exists(os.path.join(known_hosts_d, self.host)):
            # If the file exists, check the keys.
            args.append('-o StrictHostKeyChecking=yes')
        else:
            # If the file does not exist, create it and don't care
            # about the fingerprint.
            args.append('-o StrictHostKeyChecking=no')

        return args

    def get_transport_ssh_uri(self):
        return ('%s@%s:%s' % (self.user, self.host, self.src_dir),)

    def get_transport_rsync_uri(self):
        return ('%s::%s' % (self.host, self.src_dir),)

    def get_transport_uri(self):
        if self.transport == TransportChoices.SSH:
            return (
                self.get_transport_ssh_rsync_path() +
                self.get_transport_ssh_options() +
                self.get_transport_ssh_uri())
        elif self.transport == TransportChoices.RSYNC:
            return self.get_transport_rsync_uri()
        else:
            raise NotImplementedError(
                'Unknown transport: %r' % (self.transport,))

    def generate_rsync_command(self):
        flags = tuple(self.flags.split())
        data_dir = self.get_storage_destination()

        args = (
            (settings.PLANB_RSYNC_BIN,) +
            # Work around rsync bug in 3.1.0:
            # https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=741628
            ('--block-size=65536',) +
            # Fix problems when we're not root, but we can download dirs
            # with improper perms because we're root remotely. Rsync
            # could set up dir structures where files inside cannot be
            # accessible anymore. Make sure our user has rwx access.
            ('--chmod=Du+rwx',) +
            flags +
            self.create_exclude_string() +
            self.create_include_string() +
            ('--exclude=*', '--bwlimit=10000') +
            self.get_transport_uri() +
            (data_dir,))

        return args

    def run_transport(self):
        cmd = self.generate_rsync_command()
        try:
            logger.info('Running %s: %s', self.friendly_name, ' '.join(cmd))
        except Exception:
            logger.error('[%s]', repr(cmd))
            raise

        # Close all DB connections before continuing with the rsync
        # command. Since it may take a while, the connection could get
        # dropped and we'd have issues later on.
        connections.close_all()

        try:
            output = check_output(cmd).decode('utf-8')
            returncode = 0
        except CalledProcessError as e:
            returncode, output = e.returncode, e.output
            errstr = RSYNC_EXITCODES.get(returncode, 'Return code not matched')
            logging.warning(
                'code: %s\nmsg: %s\nexception: %s', returncode, errstr, str(e))
            if returncode not in RSYNC_HARMLESS_EXITCODES:
                raise

        logger.info(
            'Rsync exited with code %s for %s. Output: %s',
            returncode, self.friendly_name, output)