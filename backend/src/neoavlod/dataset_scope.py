"""One archive boundary for current business queries; no HTTP opt-out exists."""

from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from neoavlod.models.common import DatasetFields


def current_dataset(state: ORMExecuteState) -> None:
    if state.session.info.get("include_archived"):
        return
    if state.is_select or state.is_update or state.is_delete:
        state.statement = state.statement.options(
            with_loader_criteria(
                DatasetFields, lambda row: row.archived_at.is_(None), include_aliases=True
            )
        )


def register_dataset_scope() -> None:
    if not event.contains(Session, "do_orm_execute", current_dataset):
        event.listen(Session, "do_orm_execute", current_dataset)
