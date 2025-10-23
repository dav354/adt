from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import blake2b
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import (BigInteger, Boolean, Column, DateTime, ForeignKey,
                        Integer, MetaData, Numeric, Table, Text)

SCALAR_TYPES = {"string", "integer", "number", "boolean"}
MAX_IDENTIFIER_LENGTH = 63


def to_snake_case(value: str) -> str:
    result = []
    prev_lower = False
    for char in value:
        if char.isupper() and prev_lower:
            result.append("_")
        result.append(char.lower() if char.isalnum() else "_")
        prev_lower = char.islower() or char.isdigit()
    snake = "".join(result)
    while "__" in snake:
        snake = snake.replace("__", "_")
    return snake.strip("_")


@dataclass
class ColumnInfo:
    prop_name: str
    column_name: str
    schema: Dict[str, Any]
    column: Column


@dataclass
class TableNode:
    name: str
    table: Table
    columns: Dict[str, ColumnInfo]
    parent: Optional["TableNode"]
    is_array: bool = False
    is_scalar_array: bool = False
    scalar_value: Optional[ColumnInfo] = None
    unique_columns: List[str] = field(default_factory=list)
    object_children: Dict[str, "TableNode"] = field(default_factory=dict)
    array_children: Dict[str, "TableNode"] = field(default_factory=dict)


@dataclass
class RootConfig:
    name: str
    schema_name: str
    unique_props: List[str]


@dataclass
class SchemaBuildResult:
    metadata: MetaData
    root_nodes: Dict[str, TableNode]
    nodes: Dict[Tuple[str, ...], TableNode]


class SchemaBuilder:
    def __init__(self, spec: Dict[str, Any], root_configs: List[RootConfig]) -> None:
        self.spec = spec
        self.components = spec.get("components", {}).get("schemas", {})
        self.metadata = MetaData()
        self.nodes: Dict[Tuple[str, ...], TableNode] = {}
        self.root_nodes: Dict[str, TableNode] = {}
        self.root_configs = root_configs
        self._table_names: Dict[Tuple[str, ...], str] = {}

    def build(self) -> SchemaBuildResult:
        for config in self.root_configs:
            schema = self.resolve(
                {"$ref": f"#/components/schemas/{config.schema_name}"}
            )
            path = (config.name,)
            node = self.process_schema(schema, path, parent_node=None, is_array=False)
            node.unique_columns = [
                node.columns[prop].column_name
                for prop in config.unique_props
                if prop in node.columns
            ]
            if node.unique_columns:
                from sqlalchemy import UniqueConstraint

                constraint = UniqueConstraint(
                    *node.unique_columns, name=f"uq_{node.table.name}_unique_cols"
                )
                node.table.append_constraint(constraint)
            self.root_nodes[config.name] = node
        return SchemaBuildResult(
            metadata=self.metadata, root_nodes=self.root_nodes, nodes=self.nodes
        )

    def resolve(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        if "$ref" in schema:
            ref_path = schema["$ref"]
            if not ref_path.startswith("#/"):
                raise ValueError(f"Unsupported $ref path: {ref_path}")
            parts = ref_path[2:].split("/")
            target: Any = self.spec
            for part in parts:
                target = target[part]
            return self.resolve(target)

        result = dict(schema)
        if "allOf" in result:
            merged: Dict[str, Any] = {"type": result.get("type")}
            properties: Dict[str, Any] = {}
            required_set: set[str] = set(result.get("required", []))
            for item in result["allOf"]:
                resolved = self.resolve(item)
                properties.update(resolved.get("properties", {}))
                required_set |= set(resolved.get("required", []))
            merged["properties"] = properties
            merged["required"] = list(required_set)
            return merged
        return result

    def map_type(self, prop_schema: Dict[str, Any]):
        p_type = prop_schema.get("type")
        fmt = prop_schema.get("format")
        if p_type == "integer":
            return BigInteger
        if p_type == "number":
            return Numeric
        if p_type == "boolean":
            return Boolean
        if p_type == "string" and fmt == "date-time":
            return DateTime(timezone=True)
        return Text

    def process_schema(
        self,
        schema: Dict[str, Any],
        path: Tuple[str, ...],
        parent_node: Optional[TableNode],
        is_array: bool,
    ) -> TableNode:
        path_tuple = tuple(path)
        if path_tuple in self.nodes:
            node = self.nodes[path_tuple]
            if parent_node and node.parent is None:
                node.parent = parent_node
            node.is_array = node.is_array or is_array
            return node

        resolved = self.resolve(schema)
        description = resolved.get("description")

        columns: List[Column] = []
        column_infos: Dict[str, ColumnInfo] = {}

        columns.append(Column("id", Integer, primary_key=True))
        if parent_node is not None:
            columns.append(
                Column(
                    "parent_id",
                    Integer,
                    ForeignKey(f"{parent_node.table.name}.id", ondelete="CASCADE"),
                    nullable=False,
                )
            )
        if is_array:
            columns.append(Column("position", Integer, nullable=False))

        for prop_name, prop_schema in resolved.get("properties", {}).items():
            resolved_prop = self.resolve(prop_schema)
            prop_type = resolved_prop.get("type")
            if prop_type in SCALAR_TYPES:
                column_name = to_snake_case(prop_name)
                column_type = self.map_type(resolved_prop)
                column = Column(column_name, column_type)
                columns.append(column)
                column_infos[prop_name] = ColumnInfo(
                    prop_name=prop_name,
                    column_name=column_name,
                    schema=resolved_prop,
                    column=column,
                )

        table_name = self._table_name(path_tuple)
        table = Table(table_name, self.metadata, *columns, comment=description)

        node = TableNode(
            name=table_name,
            table=table,
            columns=column_infos,
            parent=parent_node,
            is_array=is_array,
        )
        self.nodes[path_tuple] = node

        for prop_name, prop_schema in resolved.get("properties", {}).items():
            resolved_prop = self.resolve(prop_schema)
            prop_type = resolved_prop.get("type")

            if prop_type == "object":
                child_path = path + (to_snake_case(prop_name),)
                child_node = self.process_schema(
                    resolved_prop, child_path, parent_node=node, is_array=False
                )
                node.object_children[prop_name] = child_node
            elif prop_type == "array":
                items = self.resolve(prop_schema.get("items", {}))
                child_path = path + (to_snake_case(prop_name),)
                item_type = items.get("type")
                if item_type in SCALAR_TYPES:
                    child_node = self.create_scalar_array_node(
                        child_path, node, items, prop_schema.get("description")
                    )
                elif item_type == "object":
                    child_node = self.process_schema(
                        items, child_path, parent_node=node, is_array=True
                    )
                else:
                    fallback_items = {"type": "string"}
                    child_node = self.create_scalar_array_node(
                        child_path, node, fallback_items, prop_schema.get("description")
                    )
                node.array_children[prop_name] = child_node

        return node

    def create_scalar_array_node(
        self,
        path: Tuple[str, ...],
        parent_node: TableNode,
        item_schema: Dict[str, Any],
        description: Optional[str],
    ) -> TableNode:
        path_tuple = tuple(path)
        if path_tuple in self.nodes:
            node = self.nodes[path_tuple]
            if node.parent is None:
                node.parent = parent_node
            node.is_array = True
            node.is_scalar_array = True
            return node

        columns = [
            Column("id", Integer, primary_key=True),
            Column(
                "parent_id",
                Integer,
                ForeignKey(f"{parent_node.table.name}.id", ondelete="CASCADE"),
                nullable=False,
            ),
            Column("position", Integer, nullable=False),
        ]
        column_type = self.map_type(item_schema)
        value_column = Column("value", column_type)
        columns.append(value_column)

        table_name = self._table_name(path_tuple)
        table = Table(table_name, self.metadata, *columns, comment=description)
        column_info = ColumnInfo(
            prop_name="value",
            column_name="value",
            schema=item_schema,
            column=value_column,
        )

        node = TableNode(
            name=table_name,
            table=table,
            columns={"value": column_info},
            parent=parent_node,
            is_array=True,
            is_scalar_array=True,
            scalar_value=column_info,
        )
        self.nodes[path_tuple] = node
        return node

    def _table_name(self, path: Tuple[str, ...]) -> str:
        if path in self._table_names:
            return self._table_names[path]

        base = "__".join(path)
        if len(base) <= MAX_IDENTIFIER_LENGTH:
            result = base
        else:
            digest = blake2b(base.encode("utf-8"), digest_size=4).hexdigest()
            prefix_limit = MAX_IDENTIFIER_LENGTH - len(digest) - 1
            prefix = base[:prefix_limit].rstrip("_")
            if not prefix:
                prefix = base[:prefix_limit]
            result = f"{prefix}_{digest}"

        self._table_names[path] = result
        return result


def build_schema_from_openapi(spec: Dict[str, Any]) -> SchemaBuildResult:
    root_configs = [
        RootConfig("register_entries", "RegisterEntry", ["registerNumber"]),
        RootConfig(
            "register_entry_versions", "RegisterEntry", ["registerNumber", "version"]
        ),
        RootConfig(
            "statistics_register_entries", "RegisterEntryStatistics", ["sourceDate"]
        ),
    ]

    builder = SchemaBuilder(spec, root_configs)
    return builder.build()
