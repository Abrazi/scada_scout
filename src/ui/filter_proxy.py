from PySide6.QtCore import QSortFilterProxyModel, Qt

class ColumnFilterProxy(QSortFilterProxyModel):
    """
    User-requested Column-based Filter Proxy.
    Filters rows based on text matches in specific columns.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.filters = {} # column -> text

    def set_filter(self, column, text):
        self.filters[column] = text.lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, row, parent):
        model = self.sourceModel()
        # If no filters, accept all
        if not self.filters:
            return True
            
        for col, text in self.filters.items():
            if not text:
                continue
                
            idx = model.index(row, col, parent)
            data = model.data(idx)
            
            # Robust string conversion
            if data is None:
                val = ""
            else:
                val = str(data).lower()
                
            if text not in val:
                return False
        return True
