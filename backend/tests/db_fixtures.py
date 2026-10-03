from sqlalchemy import ForeignKeyConstraint, MetaData


def create_source_tables(engine, *models):
    """External schema includes unmodeled tables; SQLite fixtures only need query columns."""
    metadata = MetaData()
    for model in models:
        table = model.__table__.to_metadata(metadata)
        for constraint in list(table.constraints):
            if isinstance(constraint, ForeignKeyConstraint):
                table.constraints.remove(constraint)
        table.create(engine)
