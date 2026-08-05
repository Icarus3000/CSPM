from __future__ import annotations

from services.paths import AppPaths


class LazyRepoFacade:
    """Lazy repository wiring so controller startup does not hydrate Excel immediately."""

    def __init__(self, paths: AppPaths):
        self._paths = paths
        self._db = None
        self._client = None
        self._finance = None
        self._docket = None
        self._ip = None

    def _resolve(self, item):
        if self._db is None:
            from repositories.excel_repo import ExcelRepo
            from repositories.client_repo import ClientRepo
            from repositories.finance_repo import FinanceRepo
            from repositories.docket_repo import DocketRepo
            from repositories.ip_repo import IPRepo

            self._db = ExcelRepo(self._paths)
            self._client = ClientRepo(self._db)
            self._finance = FinanceRepo(self._db)
            self._docket = DocketRepo(self._db)
            self._ip = IPRepo(self._db)

        if hasattr(self._client, item):
            return getattr(self._client, item)
        if hasattr(self._finance, item):
            return getattr(self._finance, item)
        if hasattr(self._docket, item):
            return getattr(self._docket, item)
        if hasattr(self._ip, item):
            return getattr(self._ip, item)
        if hasattr(self._db, item):
            return getattr(self._db, item)
        raise AttributeError(f"RepoFacade has no attribute '{item}'")

    def __getattr__(self, item):
        return self._resolve(item)

