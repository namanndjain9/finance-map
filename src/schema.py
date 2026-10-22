"""Schema constants and validation for the finance knowledge graph."""

NODE_TYPES = frozenset([
    "domain",
    "concept",
    "quantity",
    "instrument",
    "method",
    "activity",
    "regulatory-item",
    "route",
    "credential",
    "build",
])

EDGE_TYPES = frozenset([
    "precedes",
    "belongs-to",
    "flows-to",
    "permitted-as-study",
    "requires-registration",
    "requires",
    "prices",
    "exercised-by",
])



class SchemaError(Exception):
    """Raised when a node or edge type is not in the vocabulary."""
    pass


def validate_node_type(node_type: str) -> None:
    if node_type not in NODE_TYPES:
        raise SchemaError(f"Invalid node type: '{node_type}'. Allowed: {sorted(NODE_TYPES)}")


def validate_edge_type(edge_type: str) -> None:
    if edge_type not in EDGE_TYPES:
        raise SchemaError(f"Invalid edge type: '{edge_type}'. Allowed: {sorted(EDGE_TYPES)}")