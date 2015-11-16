from django.apps import AppConfig
from models import setup_generic_relations

class ActstreamConfig(AppConfig):
    name = 'actstream'
    verbose_name = "Actstream"

    def ready(self):
        pass
        setup_generic_relations()