from split_settings.tools import optional, include
import os

include(
    'components/10-base.py',
    'components/11-apps.py',
    'components/12-identity.py',
    'components/13-credentials.py',
    'components/20-media.py',
    'components/21-messaging.py',
    'components/30-template_cms.py',
    'components/99-depreciated.py',

    # via local_settings.py
    optional(os.path.join(os.getcwd(), 'project/local_settings.py')),

    # via server based settings in etc (placed by ansible deployment tasks)
    optional('/etc/openbroadcast.org/application-settings.py'),
    optional('/etc/openbroadcast.org/application-secrets.py'),
    optional('/etc/openbroadcast.org/application-logging.py'),

    scope=locals()
)