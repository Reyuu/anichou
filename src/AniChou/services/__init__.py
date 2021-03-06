# -*- coding: utf-8 -*-

import logging
import os

from AniChou import settings
from AniChou import signals
from AniChou.utils import notify
from AniChou.db.models import Anime
from AniChou.services.default import DefaultService
from datetime import datetime



def chooser(name, classname=None):
    if not name:
        return DefaultService
    try:
        service = getattr(__import__('AniChou.services.%s' % name,
                fromlist=[name,]), classname or name.capitalize())
    except ImportError, e:
        logging.error(e)
        service = DefaultService
    return service


class Manager(object):
    ERROR_MESSAGES = {
        'bad_service': 'Service {0} not found in loaded services. Skipped.',
        'bad_file': 'Path {0} is not a file. Skipped.',
    }

    services = []

    def __init__(self):
        self.main = None
        self.update_slot = signals.Slot('manager_sync', self.sync)
        self.update_slot = signals.Slot('manager_update_config', self.updateConfig)

    def __enter__(self):
        self.loadServices()
        return self

    def __exit__(self, type, value, traceback):
        Anime.objects.save()

    def _setLastSync(self, date):
        Anime.objects.db.setdefault('sync', {}
            )['manager'] = date
    def _getLastSync(self):
        try:
            sync = Anime.objects.db['sync']['manager']
        except KeyError:
            self.last_sync = sync = datetime.now()
        return sync
    last_sync = property(_getLastSync, _setLastSync)

    def setConfig(self, config):
        self.config = config
        self.updateConfig()
        if hasattr(config, 'files'):
            self.syncFiles()
            del config['files']

    def syncFiles(self):
        files = {}
        for s, fn in self.config.files.items():
            try:
                service = filter(lambda x: x.internalname == s,
                                    self.services)[0]
                if not os.path.isfile(fn):
                    raise OSError(self.ERROR_MESSAGES['bad_file'].format(fn))
            except IndexError:
                logging.warning(self.ERROR_MESSAGES['bad_service'].format(service))
                continue
            except OSError, e:
                logging.warning(e)
                continue
            files[service] = fn
        # Sync with files after app is ready.
        if files:
            signals.emit(signals.Signal('manager_sync'), None, files)

    def loadServices(self):
        """
        Reload all services in manager.
        """
        self.removeService()
        self.addMainService()
        for name in settings.SERVICES:
            if getattr(self.config.services, name).get('enabled'):
                self.addService(name)
        self.updateConfig()

    def addMainService(self):
        """
        Reload main service from config.
        """
        if self.main:
            self.main.stop()
            self.services.remove(self.main)
        service = chooser(self.config.services['default'])
        self.main = service(self.config)
        self.services.append(self.main)

    def addService(self, name):
        """
        Load new service in manager.
        """
        service = chooser(name)
        if type(service) != DefaultService:
            if not filter(lambda s: s.name == service.name, self.services):
                self.services.append(service(self.config))

    def removeService(self, name=None):
        """
        Stop service and unload it from manager.
        Stops all except main if no arguments passed.
        """
        if name:
            service = chooser(name)
            services = filter(lambda s: s.name == service.name, self.services)
        else:
            services = filter(lambda s: s is not self.main, self.services)
        for s in services:
            service.stop()
            self.services.remove(s)

    def getService(self, name):
        for s in self.services:
            if s.internalname == name:
                return s

    def sync(self, files={}):
        for service in self.services:
            notify('Syncing with {0}..'.format(service.name))
            if not service.sync(filename=files.get(service)):
                notify('Syncing failed..')
        notify('Syncing Done.')
        self.last_sync = datetime.now()
        Anime.objects.save()
        signals.emit(signals.Signal('gui_tables_update'))

    def search(self, string):
        result = set()
        for service in self.services:
            result |= service.search(string)
        signals.emit(signals.Signal('gui_search_create'), None, result)

    def updateConfig(self):
        """Reload config"""
        for service in self.services:
            service.setConfig(self.config)



ServiceManager = Manager()
