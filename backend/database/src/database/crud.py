"""
Reusable create / read / update / delete on a :class:`sqlalchemy.orm.Session`.
By default these methods do **not** call ``commit``; commit in a route, service, or
a ``session_scope`` context. You can set ``autocommit=True`` on a call for
one-off scripts. ``create`` and ``update`` call ``session.flush`` by default so
primary keys and server defaults are set before the surrounding commit.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any, Generic, TypeVar, cast

from sqlalchemy import func, select, inspect as sa_inspect
from sqlalchemy.orm import Session

from .base import Base

ModelT = TypeVar("ModelT", bound=Base)
Key = int | str | object | tuple[object, ...]

_MAX_LIST = 10_000


def _merge_for_update(
    data: object | None, kwargs: dict[str, object]
) -> dict[str, Any]:
    """Omit key-value pairs with ``value is None`` so you can do partial updates."""
    d: dict[str, Any] = {}
    if data is not None:
        if isinstance(data, dict):
            d = {k: v for k, v in data.items() if v is not None}
        elif is_dataclass(data) and not isinstance(data, type):
            d = {k: v for k, v in asdict(data).items() if v is not None}  # type: ignore[call-overload]
        else:
            raise TypeError(
                "data must be a dict, a dataclass instance, or omit and use **kwargs"
            )
    d.update({k: v for k, v in kwargs.items() if v is not None})
    return d


def _merge_for_create(
    data: object | None, kwargs: dict[str, object]
) -> dict[str, Any]:
    """
    Allow ``None`` (for nullable columns). Unknown keys are still dropped
    in :func:`_set_columns`.
    """
    d: dict[str, Any] = {}
    if data is not None:
        if isinstance(data, dict):
            d = dict(data)
        elif is_dataclass(data) and not isinstance(data, type):
            d = asdict(data)  # type: ignore[call-overload]
        else:
            raise TypeError(
                "data must be a dict, a dataclass instance, or omit and use **kwargs"
            )
    d.update(dict(kwargs))
    return d


def _n_pk(model: type[Base]) -> int:
    m = sa_inspect(model, raiseerr=False)
    if m is None or not m.primary_key:
        return 0
    return len(m.primary_key)


def _primary_key_key_names(model: type[Base]) -> frozenset[str]:
    m = sa_inspect(model)
    return frozenset(c.key for c in m.primary_key)


def _set_columns(
    model: type[ModelT],
    data: dict[str, Any],
    db_obj: ModelT,
    *,
    skip: frozenset[str],
) -> None:
    col_keys = {c.key for c in sa_inspect(model).columns}
    for k, v in data.items():
        if k in skip or k not in col_keys:
            continue
        if isinstance(v, Enum):
            v = v.value
        setattr(db_obj, k, v)


class CRUD(Generic[ModelT]):
    """
    Generic repository-style operations for a single model class, e.g.
    ``user_crud = CRUD(User)`` then ``user_crud.get(session, 1)``,
    ``user_crud.create(session, data={...})``, and so on.

    For a **composite** primary key, pass a ``tuple`` to ``get``, ``update``,
    and ``delete`` in the same order as the table’s PK columns.
    """

    __slots__ = ("_model", "_n_pk", "_id_name")

    def __init__(self, model: type[ModelT], *, id_field: str | None = None) -> None:
        self._model = model
        self._n_pk = _n_pk(model)
        if self._n_pk < 1:
            raise TypeError(f"{model.__name__!r} has no primary key")
        pks = sa_inspect(model).primary_key
        if id_field is not None:
            if self._n_pk != 1:
                raise TypeError("id_field= is only for a single-column primary key")
            names = {c.key for c in pks}
            if id_field not in names:
                raise ValueError(
                    f"{id_field!r} is not a primary key of {model.__name__!r}"
                )
            self._id_name = id_field
        else:
            self._id_name = pks[0].key

    @property
    def model(self) -> type[ModelT]:
        return self._model

    def get(self, session: Session, key: Key) -> ModelT | None:
        if isinstance(key, tuple):
            if len(key) != self._n_pk:
                raise TypeError(
                    f"this model’s primary key has {self._n_pk} column(s);"
                    f" {len(key)} value(s) were given"
                )
            return session.get(self._model, key)
        if self._n_pk == 1:
            return session.get(self._model, key)
        raise TypeError("use a tuple for a composite primary key, e.g. (a, b)")

    def get_by(self, session: Session, /, **eq: object) -> ModelT | None:
        if not eq:
            raise ValueError(
                "get_by() requires at least one keyword argument (column=value)"
            )
        q = select(self._model)
        for name, value in eq.items():
            if not hasattr(self._model, name):
                raise ValueError(
                    f"{name!r} is not a mapped column on {self._model.__name__!r}"
                )
            c = getattr(self._model, name)
            v = value.value if isinstance(value, Enum) else value
            q = q.where(c == v)
        return session.scalars(q).first()

    def get_many(
        self,
        session: Session,
        *,
        offset: int = 0,
        limit: int = 100,
        order_by: str | None = None,
        descending: bool = False,
        **eq: object,
    ) -> list[ModelT]:
        q = select(self._model)
        for name, value in eq.items():
            if not hasattr(self._model, name):
                raise ValueError(
                    f"{name!r} is not a mapped column on {self._model.__name__!r}"
                )
            c = getattr(self._model, name)
            v = value.value if isinstance(value, Enum) else value
            q = q.where(c == v)
        if order_by is not None:
            if not hasattr(self._model, order_by):
                raise ValueError(
                    f"unknown column {order_by!r} for order_by on {self._model.__name__!r}"
                )
            c = getattr(self._model, order_by)
            q = q.order_by(c.desc() if descending else c.asc())
        n_off = max(0, offset)
        if limit < 0:
            raise ValueError("limit must be non-negative")
        if limit == 0:
            return []
        n_lim = min(limit, _MAX_LIST)
        q = q.offset(n_off).limit(n_lim)
        return list(session.scalars(q).all())

    def count(self, session: Session, /, **eq: object) -> int:
        q = select(func.count()).select_from(self._model)  # type: ignore[call-overload]
        for name, value in eq.items():
            if not hasattr(self._model, name):
                raise ValueError(
                    f"{name!r} is not a mapped column on {self._model.__name__!r}"
                )
            c = getattr(self._model, name)
            v = value.value if isinstance(value, Enum) else value
            q = q.where(c == v)
        r = session.execute(q).scalar_one()
        return int(r)

    def create(
        self,
        session: Session,
        /,
        *,
        data: object | None = None,
        flush: bool = True,
        autocommit: bool = False,
        **kwargs: object,
    ) -> ModelT:
        merged = _merge_for_create(
            data, cast(dict[str, object], dict(kwargs))
        )
        obj = self._model()  # type: ignore[call-arg]
        _set_columns(self._model, merged, obj, skip=frozenset())
        session.add(obj)
        if autocommit:
            session.commit()
        elif flush:
            session.flush()
        return obj

    def create_many(
        self,
        session: Session,
        /,
        *rows: dict[str, object],
        flush: bool = True,
        autocommit: bool = False,
    ) -> list[ModelT]:
        out: list[ModelT] = []
        for row in rows:
            m = _merge_for_create(row, {})
            obj = self._model()  # type: ignore[call-arg]
            _set_columns(self._model, m, obj, skip=frozenset())  # type: ignore[arg-type]
            session.add(obj)
            out.append(obj)
        if autocommit:
            session.commit()
        elif flush:
            session.flush()
        return out

    def update(
        self,
        session: Session,
        key: Key,
        /,
        *,
        data: object | None = None,
        flush: bool = True,
        autocommit: bool = False,
        **kwargs: object,
    ) -> ModelT | None:
        obj = self.get(session, key)
        if obj is None:
            return None
        merged = _merge_for_update(
            data, cast(dict[str, object], dict(kwargs))
        )
        skip = _primary_key_key_names(self._model)
        _set_columns(
            self._model,
            merged,
            obj,
            skip=skip,
        )
        if autocommit:
            session.commit()
        elif flush:
            session.flush()
        return obj

    def delete(
        self,
        session: Session,
        key: Key,
        /,
        *,
        flush: bool = True,
        autocommit: bool = False,
    ) -> bool:
        obj = self.get(session, key)
        if obj is None:
            return False
        session.delete(obj)
        if autocommit:
            session.commit()
        elif flush:
            session.flush()
        return True


def get_crud(model: type[ModelT]) -> CRUD[ModelT]:
    """Convenience alias: ``get_crud(User)`` is equivalent to ``CRUD(User)``."""
    return CRUD(model)
