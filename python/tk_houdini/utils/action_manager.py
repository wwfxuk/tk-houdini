from functools import partial

from sgtk.platform.qt import QtCore, QtGui


class HoudiniActionManager(QtCore.QObject):
    """
    A shotgun workfiles action manager class for houdini.
    """

    on_action_triggered = QtCore.Signal()

    UI_AREA_MAIN = 0x1
    UI_AREA_DETAILS = 0x2
    UI_AREA_HISTORY = 0x3

    def __init__(self, handler, node):
        """
        Initialise the class.

        :param handler: A :class:`NodeHandlerBase` instance.
        :param node: A :class:`hou.Node` instance.
        """
        super(HoudiniActionManager, self).__init__()
        self._handler = handler
        self._node = node

    def _on_open(self, sg_data, policy=None):
        """
        Callback to run on open of an object. Populate the node from the
        publish data.

        Emits on_action_triggered event.

        :param dict sg_data: The publish data to load.
        :param policy: The version policy to apply.
        """
        if sg_data:
            self._handler.populate_node_from_publish_data(self._node, sg_data, policy)
        self.on_action_triggered.emit()

    def has_actions(self, publish_type):
        """
        Returns true if the given publish type has any actions associated with it.
        For the open dialog, this returns true if the file can be opened (is one of
        the valid publish types the action manager was initialised with).

        Is only valid if the settings have been set up accordingly.

        :param publish_type: A Shotgun publish type (e.g. 'Maya Render')
        :returns: True if the current actions setup knows how to
            handle this.
        """
        return publish_type in self._handler.valid_file_types

    def get_actions_for_publish(self, sg_data, ui_area):
        """
        See documentation for :func:`get_actions_for_publishes`. The functionality is the same,
        but only for a single publish.

        :param dict sg_data: Standard Shotgun entity dictionary with keys type, id and name.
        :param ui_area: Indicates which part of the UI the request is coming from.
            Currently one of `UI_AREA_MAIN`, `UI_AREA_DETAILS` and UI_AREA_HISTORY`.

        :returns: A :class:`list` of QAction instances.
        """
        actions = []
        open_action = QtGui.QAction("Open", self)
        cb_1 = partial(self._on_open, sg_data, policy=None)
        open_action.triggered.connect(cb_1)
        actions.append(open_action)
        if ui_area in [self.UI_AREA_DETAILS, self.UI_AREA_MAIN]:
            open_latest = QtGui.QAction("Open Latest", self)
            cb_2 = partial(self._on_open, sg_data, policy=self._handler.LATEST_POLICY)
            open_latest.triggered.connect(cb_2)
            open_latest_complete = QtGui.QAction("Open Latest Complete", self)
            cb_3 = partial(
                self._on_open, sg_data, policy=self._handler.LATEST_COMPLETE_POLICY
            )
            open_latest_complete.triggered.connect(cb_3)
            actions.append(open_latest)
            actions.append(open_latest_complete)
        return actions

    def get_actions_for_publishes(self, sg_data, ui_area):
        """
        Returns a list of actions for a list of publishes. Returns nothing
        because we don't want any regular actions presented in the open dialog.

        :param sg_data: Shotgun data for a publish
        :param ui_area: Indicates which part of the UI the request is coming from.
                        Currently one of UI_AREA_MAIN, UI_AREA_DETAILS and UI_AREA_HISTORY
        :returns:       List of QAction objects, ready to be parented to some QT Widgetry.
        """
        return self.get_actions_for_publish(sg_data, ui_area)

    def get_actions_for_folder(self, sg_data):
        """
        Returns a list of actions for a folder object.  Overrides the base
        implementation as we don't want any folder actions presented in the
        open dialog.

        :param sg_data: The data associated with this folder
        :returns:       A list of actions that are available for this folder
        """
        return []

    def get_default_action_for_publish(self, sg_data, ui_area):
        """
        Get the default action for the specified publish data.

        For the open dialog, the default action is to open the publish the action
        is triggered for.

        :param sg_data: Shotgun data for a publish
        :param ui_area: Indicates which part of the UI the request is coming from.
                        Currently one of UI_AREA_MAIN, UI_AREA_DETAILS and UI_AREA_HISTORY
        :returns:       The QAction object representing the default action for this publish
        """
        return self.get_actions_for_publish(sg_data, ui_area)[0]
