"""Local mypy stubs for the PyQt6 modules this UI imports.

The bundled PyQt6 6.11 ``QtCore.pyi`` omits ``pyqtProperty``, so mypy does not
recognise the property-setter pattern and flags every editable signal. These
stubs declare only the surface this codebase uses, typed so ``pyqtProperty``
behaves like a settable property for the type checker. They are dev-only and
add no runtime dependency.
"""
