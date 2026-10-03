from sqlalchemy import func, select, tuple_


def copy_table(source, target, source_table, target_table, *, apply=False, batch_size=500):
    """Copy by primary key, preserve IDs, and reject conflicting rows on retries."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    keys = [column.name for column in target_table.primary_key.columns]
    columns = list(target_table.columns.keys())
    if not keys or not set(columns).issubset(source_table.columns.keys()):
        raise ValueError(f"Cannot safely map {source_table.name} to {target_table.name}")
    count = source.execute(select(func.count()).select_from(source_table)).scalar_one()
    if not apply:
        return count
    statement = select(*(source_table.c[name] for name in columns)).order_by(
        *(source_table.c[key] for key in keys)
    ).execution_options(stream_results=True)
    copied = 0
    with source.execute(statement) as cursor:
        while batch := cursor.fetchmany(batch_size):
            rows = [dict(row._mapping) for row in batch]
            ids = [tuple(row[key] for key in keys) for row in rows]
            existing = {tuple(row._mapping[key] for key in keys): dict(row._mapping)
                        for row in target.execute(select(target_table).where(
                            tuple_(*(target_table.c[key] for key in keys)).in_(ids)
                        ))}
            missing = []
            for row, key in zip(rows, ids):
                if key in existing and existing[key] != row:
                    raise ValueError(f"Conflicting row in {target_table.name}, primary key {key}")
                if key not in existing:
                    missing.append(row)
            if missing:
                target.execute(target_table.insert(), missing)
            actual = {tuple(row._mapping[key] for key in keys): dict(row._mapping)
                      for row in target.execute(select(target_table).where(
                          tuple_(*(target_table.c[key] for key in keys)).in_(ids)
                      ))}
            if any(actual[key] != row for row, key in zip(rows, ids)):
                raise ValueError(f"Verification failed for {target_table.name}")
            copied += len(rows)
    if copied != count:
        raise ValueError(f"Source changed during copy of {source_table.name}; stop writers and retry")
    return copied
