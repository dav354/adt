from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import blake2s
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
    UniqueConstraint,
)


ScalarType = str  # "boolean" | "integer" | "number" | "datetime" | "text"


@dataclass
class ScalarField:
    """Metadata for a scalar column derived from JSON."""

    name: str
    column_name: str
    scalar_type: ScalarType
    nullable: bool = True


@dataclass
class RelationSpec:
    """Describes a relationship between tables."""

    name: str
    target: "TableSpec"
    relation: str  # one | many | scalar_array
    ordered: bool = False


@dataclass
class TableSpec:
    """SQLAlchemy table + metadata used during persistence."""

    name: str
    path: Tuple[str, ...]
    table: Table
    scalars: Dict[str, ScalarField] = field(default_factory=dict)
    relations: List[RelationSpec] = field(default_factory=list)
    parent_fk: Optional[str] = None
    relation_to_parent: Optional[str] = None
    position_column: bool = False
    scalar_array_type: Optional[ScalarType] = None
    unique_columns: Tuple[str, ...] = ()


@dataclass
class SchemaSpec:
    """Container for the full SQLAlchemy metadata tree."""

    metadata: MetaData
    root: TableSpec



TYPE_ORDER: List[ScalarType] = [
    "boolean",
    "integer",
    "number",
    "datetime",
    "text",
]

JSON_SCHEMA_KEYS = {
    "$schema",
    "$id",
    "$comment",
    "title",
    "description",
    "comment",
    "type",
    "format",
    "default",
    "examples",
    "enum",
    "const",
    "required",
    "allOf",
    "anyOf",
    "oneOf",
    "not",
    "items",
    "properties",
    "patternProperties",
    "additionalProperties",
    "minItems",
    "maxItems",
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "uniqueItems",
    "nullable",
    "translations",
}


def _is_iso_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except Exception:
        return False


def _infer_scalar_type(value: Any) -> ScalarType:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "datetime" if ("T" in value and _is_iso_datetime(value)) else "text"
    return "text"


def _merge_scalar_type(a: ScalarType, b: ScalarType) -> ScalarType:
    if a == b:
        return a
    return TYPE_ORDER[max(TYPE_ORDER.index(a), TYPE_ORDER.index(b))]


def _schema_type(schema: Dict[str, Any]) -> Optional[str]:
    type_value = schema.get("type")
    if isinstance(type_value, list):
        candidates = [t for t in type_value if t != "null"]
        if not candidates:
            return None
        return candidates[0]
    if isinstance(type_value, str):
        return type_value
    if "enum" in schema:
        return "string"
    if "properties" in schema or "additionalProperties" in schema:
        return "object"
    if "items" in schema:
        return "array"
    return None


def _schema_scalar_type(schema: Dict[str, Any]) -> ScalarType:
    schema_type = _schema_type(schema)
    if schema_type == "integer":
        return "integer"
    if schema_type == "number":
        return "number"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "string" and schema.get("format") == "date-time":
        return "datetime"
    return "text"


def _collect_required(schema: Dict[str, Any]) -> set[str]:
    required = set(schema.get("required", []))
    for key in ("allOf", "anyOf", "oneOf"):
        subschemas = schema.get(key)
        if isinstance(subschemas, list):
            for subschema in subschemas:
                if isinstance(subschema, dict):
                    required |= _collect_required(subschema)
    return required


def _collect_properties(schema: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    properties: Dict[str, Dict[str, Any]] = {}
    schema_props = schema.get("properties")
    if isinstance(schema_props, dict):
        properties.update(schema_props)
    for key in ("allOf", "anyOf", "oneOf"):
        subschemas = schema.get(key)
        if isinstance(subschemas, list):
            for subschema in subschemas:
                if isinstance(subschema, dict):
                    properties.update(_collect_properties(subschema))
    return properties


def _infer_schema_object(schema: Dict[str, Any], path: Tuple[str, ...]) -> NodeObject:
    node = NodeObject(path=path)
    properties = _collect_properties(schema)
    required = _collect_required(schema)

    for prop_name, prop_schema in properties.items():
        if not isinstance(prop_schema, dict):
            continue

        schema_type = _schema_type(prop_schema)
        if schema_type == "object":
            node.objects[prop_name] = _infer_schema_object(
                prop_schema, path + (prop_name,)
            )
        elif schema_type == "array":
            node.arrays[prop_name] = _infer_schema_array(prop_schema, path + (prop_name,))
        else:
            node.scalars[prop_name] = NodeScalar(
                scalar_type=_schema_scalar_type(prop_schema),
                nullable=prop_name not in required,
            )

    return node


def _infer_schema_array(schema: Dict[str, Any], path: Tuple[str, ...]) -> NodeArray:
    items = schema.get("items")
    if isinstance(items, dict):
        item_type = _schema_type(items)
        if item_type == "object":
            return NodeArray(kind="object", object_node=_infer_schema_object(items, path))
        if item_type == "array":
            return _infer_schema_array(items, path)
        return NodeArray(kind="scalar", scalar_type=_schema_scalar_type(items))
    return NodeArray(kind="scalar", scalar_type="text")


def _to_snake_case(value: str) -> str:
    result: List[str] = []
    prev_lower = False
    for char in value:
        if char.isupper() and prev_lower:
            result.append("_")
        if char.isalnum():
            result.append(char.lower())
        else:
            result.append("_")
        prev_lower = char.islower() or char.isdigit()
    snake = "".join(result)
    while "__" in snake:
        snake = snake.replace("__", "_")
    return snake.strip("_")


def make_identifier(parts: Iterable[str]) -> str:
    cleaned = [_to_snake_case(p) for p in parts if p]
    if len(cleaned) > 4:
        cleaned = cleaned[-4:]
    base = "_".join(p for p in cleaned if p)
    if len(base) <= 63:
        return base or "unnamed"
    digest = blake2s(base.encode("utf-8"), digest_size=4).hexdigest()
    prefix = base[: 63 - len(digest) - 1]
    prefix = prefix.rstrip("_") or base[: 63 - len(digest) - 1]
    return f"{prefix}_{digest}"


@dataclass
class NodeScalar:
    scalar_type: ScalarType
    nullable: bool = True


@dataclass
class NodeArray:
    kind: str  # scalar | object
    scalar_type: Optional[ScalarType] = None
    object_node: Optional["NodeObject"] = None


@dataclass
class NodeObject:
    path: Tuple[str, ...]
    scalars: Dict[str, NodeScalar] = field(default_factory=dict)
    objects: Dict[str, "NodeObject"] = field(default_factory=dict)
    arrays: Dict[str, NodeArray] = field(default_factory=dict)


def _merge_objects(target: NodeObject, other: NodeObject) -> NodeObject:
    for name, scalar in other.scalars.items():
        if name in target.scalars:
            merged = _merge_scalar_type(
                target.scalars[name].scalar_type, scalar.scalar_type
            )
            target.scalars[name].scalar_type = merged
            target.scalars[name].nullable = (
                target.scalars[name].nullable or scalar.nullable
            )
        else:
            target.scalars[name] = scalar

    for name, obj in other.objects.items():
        if name in target.objects:
            _merge_objects(target.objects[name], obj)
        else:
            target.objects[name] = obj

    for name, arr in other.arrays.items():
        if name in target.arrays:
            existing = target.arrays[name]
            if existing.kind == "scalar" and arr.kind == "scalar":
                existing.scalar_type = _merge_scalar_type(
                    existing.scalar_type or "text", arr.scalar_type or "text"
                )
        else:
            target.arrays[name] = arr

    return target


def _infer_object(value: Dict[str, Any], path: Tuple[str, ...]) -> NodeObject:
    node = NodeObject(path=path)
    for key, val in value.items():
        if isinstance(val, dict):
            node.objects[key] = _infer_object(val, path + (key,))
        elif isinstance(val, list):
            node.arrays[key] = _infer_array(val, path + (key,))
        else:
            node.scalars[key] = NodeScalar(
                scalar_type=_infer_scalar_type(val), nullable=True
            )
    return node


def _infer_array(values: List[Any], path: Tuple[str, ...]) -> NodeArray:
    if not values:
        return NodeArray(kind="scalar", scalar_type="text")

    array_kind: Optional[str] = None
    scalar_type: Optional[ScalarType] = None
    object_node: Optional[NodeObject] = None

    for item in values:
        if isinstance(item, dict):
            array_kind = "object"
            obj = _infer_object(item, path)
            object_node = (
                obj if object_node is None else _merge_objects(object_node, obj)
            )
        else:
            array_kind = "scalar"
            typed = _infer_scalar_type(item)
            scalar_type = (
                typed if scalar_type is None else _merge_scalar_type(scalar_type, typed)
            )

    if array_kind == "object" and object_node is not None:
        return NodeArray(kind="object", object_node=object_node)

    return NodeArray(kind="scalar", scalar_type=scalar_type or "text")


def _infer_schema(sample: Dict[str, Any], root_name: str) -> NodeObject:
    if (
        isinstance(sample, dict)
        and "properties" in sample
        and (sample.get("type") == "object" or _schema_type(sample) in {"object", None})
    ):
        return _infer_schema_object(sample, (root_name,))
    return _infer_object(sample, (root_name,))


def _scalar_type_to_sa(scalar_type: ScalarType):
    if scalar_type == "boolean":
        return Boolean
    if scalar_type == "integer":
        return BigInteger
    if scalar_type == "number":
        return Numeric
    if scalar_type == "datetime":
        return DateTime(timezone=True)
    return Text


def _build_table(
    metadata: MetaData,
    current: NodeObject,
    tables_by_name: Dict[str, TableSpec],
    tables_by_path: Dict[Tuple[str, ...], TableSpec],
    parent: Optional[TableSpec],
    relation_to_parent: Optional[str],
) -> TableSpec:
    if current.path in tables_by_path:
        return tables_by_path[current.path]

    table_name = make_identifier(current.path)
    counter = 1
    while table_name in tables_by_name:
        table_name = make_identifier(list(current.path) + [str(counter)])
        counter += 1
    columns: List[Column] = [Column("id", Integer, primary_key=True)]
    parent_fk_name: Optional[str] = None

    if parent is not None:
        parent_segment = parent.path[-1] if parent.path else parent.name
        parent_fk_name = make_identifier((parent_segment, "id"))
        columns.append(
            Column(
                parent_fk_name,
                Integer,
                ForeignKey(f"{parent.name}.id", ondelete="CASCADE"),
                nullable=False,
            )
        )

    scalar_fields: Dict[str, ScalarField] = {}
    for prop, info in current.scalars.items():
        column_name = make_identifier((prop,))
        existing_names = {col.name for col in columns}
        if column_name in existing_names:
            column_name = make_identifier((prop, "value"))
        col_type = _scalar_type_to_sa(info.scalar_type)
        columns.append(Column(column_name, col_type, nullable=info.nullable))
        scalar_fields[prop] = ScalarField(
            name=prop,
            column_name=column_name,
            scalar_type=info.scalar_type,
            nullable=info.nullable,
        )

    table = Table(table_name, metadata, *columns)
    spec = TableSpec(
        name=table_name,
        path=current.path,
        table=table,
        scalars=scalar_fields,
        parent_fk=parent_fk_name,
        relation_to_parent=relation_to_parent,
    )
    tables_by_name[table_name] = spec
    tables_by_path[current.path] = spec

    for prop, obj in current.objects.items():
        child_spec = _build_table(
            metadata, obj, tables_by_name, tables_by_path, spec, "one"
        )
        spec.relations.append(
            RelationSpec(name=prop, target=child_spec, relation="one", ordered=False)
        )

    for prop, arr in current.arrays.items():
        if arr.kind == "object" and arr.object_node is not None:
            child_spec = _build_table(
                metadata,
                arr.object_node,
                tables_by_name,
                tables_by_path,
                spec,
                "many",
            )
            if "position" not in child_spec.table.c:
                child_spec.table.append_column(
                    Column("position", Integer, nullable=False)
                )
                child_spec.position_column = True
            spec.relations.append(
                RelationSpec(
                    name=prop, target=child_spec, relation="many", ordered=True
                )
            )
        elif arr.kind == "scalar":
            scalar_type = arr.scalar_type or "text"
            array_table_name = make_identifier(current.path + (prop,))
            arr_columns = [
                Column("id", Integer, primary_key=True),
            ]
            parent_segment = spec.path[-1] if spec.path else spec.name
            parent_fk_name = make_identifier((parent_segment, "id"))
            arr_columns.append(
                Column(
                    parent_fk_name,
                    Integer,
                    ForeignKey(f"{spec.name}.id", ondelete="CASCADE"),
                    nullable=False,
                )
            )
            arr_columns.append(Column("position", Integer, nullable=False))
            arr_columns.append(
                Column("value", _scalar_type_to_sa(scalar_type), nullable=True)
            )
            counter = 1
            while array_table_name in tables_by_name:
                array_table_name = make_identifier(current.path + (prop, str(counter)))
                counter += 1

            arr_table = Table(array_table_name, metadata, *arr_columns)
            arr_spec = TableSpec(
                name=array_table_name,
                path=current.path + (prop,),
                table=arr_table,
                scalars={
                    "value": ScalarField(
                        name="value",
                        column_name="value",
                        scalar_type=scalar_type,
                        nullable=True,
                    )
                },
                parent_fk=parent_fk_name,
                relation_to_parent="scalar_array",
                position_column=True,
                scalar_array_type=scalar_type,
            )
            tables_by_name[array_table_name] = arr_spec
            tables_by_path[arr_spec.path] = arr_spec
            spec.relations.append(
                RelationSpec(
                    name=prop,
                    target=arr_spec,
                    relation="scalar_array",
                    ordered=True,
                )
            )

    return spec


def build_schema_from_sample(
    sample_path: Path, root_name: str = "register_entries"
) -> SchemaSpec:
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    node = _infer_schema(sample, root_name)
    metadata = MetaData()
    tables_by_name: Dict[str, TableSpec] = {}
    tables_by_path: Dict[Tuple[str, ...], TableSpec] = {}

    root_spec = _build_table(
        metadata,
        node,
        tables_by_name,
        tables_by_path,
        parent=None,
        relation_to_parent=None,
    )

    register_column = root_spec.scalars.get("registerNumber")
    if register_column and register_column.column_name in root_spec.table.c:
        column_name = register_column.column_name
        root_spec.table.append_constraint(
            UniqueConstraint(column_name, name=f"uq_{root_spec.name}_{column_name}")
        )
        root_spec.table.c[column_name].nullable = False
        register_column.nullable = False
        root_spec.unique_columns = (column_name,)

    return SchemaSpec(metadata=metadata, root=root_spec)


def load_schema(sample_path: Path) -> SchemaSpec:
    """Load the relational schema representation from the sample JSON file."""

    return build_schema_from_sample(sample_path)
