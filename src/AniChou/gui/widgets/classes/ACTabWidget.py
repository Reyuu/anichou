# -*- coding: utf-8 -*-

import logging
from AniChou import settings
from AniChou import signals
from AniChou.db.models import Anime
from AniChou.gui.widgets import ( ACStatusTab, ACStandardItemModel,
                            ACSortFilterProxyModel, ACStandardItem )
from AniChou.services.data.base import LOCAL_STATUS
from PyQt4 import QtCore, QtGui




class ACTabWidget(QtGui.QTabWidget):

    def __init__(self, parent=None):
        QtGui.QTabWidget.__init__(self, parent)
        #self.setTabsClosable(True)
        self.removedTabs = {}

        self.model = ACStandardItemModel()

        self.createTabs()
        signals.Slot('gui_tables_update', self.updateFromDB)
        signals.Slot('gui_search_create', self.updateSearchTab)

        # Context menu
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.contextMenuShow)

    def contextMenuShow(self, pos):
        menu = QtGui.QMenu()
        tabs_menu = self.contextMenuTabs(menu)
        menu.addMenu(tabs_menu)
        menu.exec_(self.mapToGlobal(pos))

    def createTabs(self):
        for number, title in LOCAL_STATUS:
            self.showTab(number, title)

    def contextMenuTabs(self, menu):
        tabs_menu = QtGui.QMenu(menu)
        tabs_menu.setTitle("Show tabs")
        for number, title in LOCAL_STATUS:
            action = tabs_menu.addAction(title)
            action.setCheckable(True)
            try:
                tab_index = filter(lambda i: self.tabText(i) == title, \
                                range(0, self.count()))[0]
            except IndexError:
                self.connect(action, QtCore.SIGNAL('triggered()'),
                    lambda n=number, t=title: self.showTab(n, t))
            else:
                action.setChecked(True)
                self.connect(action, QtCore.SIGNAL('triggered()'),
                    lambda i=tab_index: self.hideTab(i))
        return tabs_menu

    def showTab(self, number, title):
        title = unicode(title)
        if title not in self.removedTabs.keys():
            parentItem = self.model.invisibleRootItem()
            model = ACSortFilterProxyModel(model=self.model, stindex=number)
            # Add model group
            try:
                item = self.model.findItems(QtCore.QString(unicode(number)))[0]
            except IndexError:
                item = QtGui.QStandardItem(QtCore.QString(unicode(number)))
                parentItem.appendRow(item)
                style = settings.GUI_COLUMNS.get_by_index(number)
                columns = len(style['name']) - 1
                item.insertColumns(1, columns)
            # Create tab and set its model
            #index = model.index(model.rowCount() - 1, 0)
            index = model.index(item.row(), 0)
            tab = ACStatusTab(self, model, index, number)
            tab.status = number
            logging.debug('Tab with number {0} and label {1} added.'.format(number, title))
        else:
            tab = self.removedTabs.pop(title)
        self.addTab(tab, title)

    def hideTab(self, index):
        text = self.tabText(index)
        utext = unicode(text)
        if utext in self.removedTabs.keys():
            logging.error(
                'Tab {0} is already removed or collide with other tab name.'.format(text))
            return
        widget = self.widget(index)
        self.removedTabs[utext] = widget
        self.removeTab(index)

    #@signals.Slot('gui_tables_update')
    def updateFromDB(self):
        """
        Update all anime tables views from database.
        This is used on initialization and after syncronization.
        """
        leafs = {}
        statuses = list(dict(LOCAL_STATUS).keys())
        objects = set(Anime.objects.all())
        orphans = {}
        for number in statuses:
            leafs[int(number)] = parent = self.model.findItems(QtCore.QString(unicode(number)))[0]
            for row in range(0, parent.rowCount()):
                child = parent.child(row)
                # Remove item from model list
                try:
                    objects.remove(child.dbmodel)
                except KeyError:
                    # Item not in the model, remove it.
                    parent.takeRow(row)
                    continue
                # Check if we need to move it to another
                model_status = int(child.dbmodel.my_status)
                if number != model_status:
                    if model_status not in orphans.keys():
                        orphans[model_status] = []
                    # Remove rows with changed status
                    orphans[model_status].append(parent.takeRow(row))

        # Move old rows to new place
        for key, values in orphans.items():
            if not key in leafs:
                logging.error('Bad status {}. Items removed.'.format(key))
                continue
            for row in values:
                leafs[key].appendRow(row)

        # Create new rows
        for item in objects:
            status = item.my_status
            label = QtCore.QString(
                '{0}:{1}'.format(item.__class__.__name__, item.pk))
            leafs[status].appendRow(ACStandardItem(label, item))

    def updateSearchTab(self, data):
        index = settings.GUI_FIRST_CUSTOM_TAB_INDEX
        self.showTab(index, 'Search')
        parent = self.model.findItems(QtCore.QString(unicode(index)))[0]
        parent.removeRows(0, parent.rowCount())
        for item in data:
            label = QtCore.QString(
                '{0}:{1}'.format(item.__class__.__name__, item.pk))
            parent.appendRow(ACStandardItem(label, item))
