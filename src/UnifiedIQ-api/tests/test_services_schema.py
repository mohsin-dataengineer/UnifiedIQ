from app.models.domain import ColumnInfo, TableInfo
from app.services.schema import SchemaService


def _t(name: str, cols: list[str], schema: str = "default") -> TableInfo:
    return TableInfo(
        catalog="workspace",
        schema=schema,
        table=name,
        columns=[ColumnInfo(name=c, data_type="STRING") for c in cols],
    )


def test_relevant_tables_keyword_match():
    settings_obj = type("S", (), {"schema_ttl_seconds": 60})()
    svc = SchemaService(settings_obj, warehouse=None)  # type: ignore[arg-type]
    tables = [
        _t("sales", ["region", "revenue"]),
        _t("customers", ["id", "name", "city"]),
        _t("inventory", ["sku", "qty"]),
    ]
    picked = svc.relevant_tables(tables, "total revenue by region", top_k=2)
    names = [t.table for t in picked]
    assert "sales" in names
    assert "inventory" not in names


def test_relevant_tables_falls_back_when_no_match():
    settings_obj = type("S", (), {"schema_ttl_seconds": 60})()
    svc = SchemaService(settings_obj, warehouse=None)  # type: ignore[arg-type]
    tables = [_t("a", ["x"]), _t("b", ["y"])]
    picked = svc.relevant_tables(tables, "????", top_k=5)
    assert len(picked) == 2  # full set when nothing matches
