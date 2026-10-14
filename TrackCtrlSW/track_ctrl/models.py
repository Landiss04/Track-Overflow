"""List models that update in place.

A QML ``Repeater`` or ``ListView`` fed a plain list rebuilds every
delegate each time the list is replaced, even when almost nothing
changed. A controller owns dozens of block tiles and the views refresh
several times a second, so that rebuilding dominated the UI thread.

These models keep their rows and report only the rows that changed, so
a refresh in which one block became occupied touches one tile.
"""

from __future__ import annotations

import functools
from typing import Any, Sequence

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    Property,
    QModelIndex,
    QPersistentModelIndex,
    QObject,
    Qt,
)

#: Role names a block tile binds to, in role-number order.
BLOCK_ROLES: tuple[str, ...] = (
    "blockId",
    "label",
    "section",
    "number",
    "occupied",
    "closed",
    "train",
    "feature",
    "speedLimit",
    "station",
)


class BlockListModel(QAbstractListModel):
    """The blocks of the selected controller, one row per block."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, Any]] = []

    def roleNames(self) -> dict[int, QByteArray]:  # noqa: N802  (Qt API)
        """Map each role number to the name QML binds to."""
        return {
            Qt.ItemDataRole.UserRole + 1 + index: QByteArray(name.encode())
            for index, name in enumerate(BLOCK_ROLES)
        }

    def rowCount(  # noqa: N802  (Qt API)
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        """How many blocks there are."""
        return 0 if parent.isValid() else len(self._rows)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """One field of one block."""
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        position = role - Qt.ItemDataRole.UserRole - 1
        if not 0 <= position < len(BLOCK_ROLES):
            return None
        return self._rows[index.row()][BLOCK_ROLES[position]]

    def update(self, rows: Sequence[dict[str, Any]]) -> None:
        """Make the model show ``rows``, touching only what changed.

        If the set of blocks is different, as when another controller is
        selected, the model is reset. Otherwise only the rows whose
        values differ are reported.
        """
        new_ids = [row["blockId"] for row in rows]
        if new_ids != [row["blockId"] for row in self._rows]:
            self.beginResetModel()
            self._rows = [dict(row) for row in rows]
            self.endResetModel()
            return

        for position, (old, new) in enumerate(zip(self._rows, rows)):
            if old == new:
                continue
            changed = [
                Qt.ItemDataRole.UserRole + 1 + index
                for index, name in enumerate(BLOCK_ROLES)
                if old[name] != new[name]
            ]
            self._rows[position] = dict(new)
            where = self.index(position)
            self.dataChanged.emit(where, where, changed)


def list_property(notify: Any) -> Any:
    """Expose a list-returning getter to QML as ``{"rows": [...]}``.

    A list property read from QML is a live reference: every ``.length``
    or element access inside ``filter`` or ``map`` calls the Python getter
    again, once per element. A view that filters a 30-row list in eight
    places made over two hundred getter calls per refresh. A list nested
    in a map is copied into the JavaScript engine in one call, so QML
    reads ``wayside.outputs.rows`` instead.
    """
    def decorate(function: Any) -> Any:
        @functools.wraps(function)
        def wrapper(self: Any) -> dict[str, Any]:
            return {"rows": function(self)}

        return Property("QVariantMap", wrapper, notify=notify)

    return decorate
