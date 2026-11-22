"""Parse the YAML source file and build a NetworkX DiGraph."""

from pathlib import Path

import networkx as nx
import yaml

from src.schema import SchemaError, validate_edge_type, validate_node_type


def default_label(node_id: str) -> str:
    """Readable fallback label for a node that declares none."""
    return node_id.replace("_", " ")


def load_graph(path: str | Path) -> nx.DiGraph:
    """Load graph.yaml and return a validated NetworkX DiGraph.

    Node attributes kept: type, landmark (optional), label, description,
    aliases. label/description/aliases are optional in the YAML and are used
    by the AI layer (src/ai) to match questions to nodes and to narrate paths.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "nodes" not in data or "edges" not in data:
        raise SchemaError("Source file must have top-level 'nodes' and 'edges' keys.")

    G = nx.DiGraph()

    for node in data["nodes"]:
        node_id = node["id"]
        node_type = node["type"]
        validate_node_type(node_type)
        attrs = {
            "type": node_type,
            "label": node.get("label") or default_label(node_id),
            "description": node.get("description", ""),
            "aliases": list(node.get("aliases") or []),
        }
        if "landmark" in node:
            attrs["landmark"] = node["landmark"]
        G.add_node(node_id, **attrs)

    for edge in data["edges"]:
        source = edge["source"]
        target = edge["target"]
        edge_type = edge["type"]
        validate_edge_type(edge_type)
        if source not in G:
            raise SchemaError(f"Edge source '{source}' is not a declared node.")
        if target not in G:
            raise SchemaError(f"Edge target '{target}' is not a declared node.")
        G.add_edge(source, target, type=edge_type)

    return G
