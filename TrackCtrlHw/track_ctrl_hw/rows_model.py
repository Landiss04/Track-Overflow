"""A list model that updates its rows in place.

Assigning a new JavaScript array to a QML view rebuilds every delegate
and resets the view's scroll position. Tables here refresh up to ten
times a second while the clock runs, so they bind to this model
instead: rows that did not change are left alone, changed rows update
in place, and only a change in row count resets the view.
"""

from __future__ import annotations

from typing import Any, Union

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
    Signal,
)

_ROW_ROLE = Qt.ItemDataRole.UserRole + 1

_Index = Union[QModelIndex, QPersistentModelIndex]


class RowsModel(QAbstractListModel):
    """Rows of plain values, exposed to QML as the ``row`` role."""

    countChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[Any] = []

    def rowCount(self, parent: _Index = QModelIndex()) -> int:  # noqa: N802
        """Number of rows; a list model has no children."""
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: _Index, role: int = _ROW_ROLE) -> Any:
        """The row at ``index``, for the ``row`` role."""
        if role != _ROW_ROLE or not 0 <= index.row() < len(self._rows):
            return None
        return self._rows[index.row()]

    def roleNames(self) -> dict[int, QByteArray]:  # noqa: N802
        """Expose rows to QML delegates as ``row``."""
        return {_ROW_ROLE: QByteArray(b"row")}

    def _get_count(self) -> int:
        return len(self._rows)

    count = Property(int, _get_count, notify=countChanged)

    def set_rows(self, rows: list[Any]) -> None:
        """Show ``rows``, touching only what changed."""
        if len(rows) != len(self._rows):
            self.beginResetModel()
            self._rows = list(rows)
            self.endResetModel()
            self.countChanged.emit()
            return
        for row, value in enumerate(rows):
            if value != self._rows[row]:
                self._rows[row] = value
                index = self.index(row)
                self.dataChanged.emit(index, index, [_ROW_ROLE])
