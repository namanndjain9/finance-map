import { useEffect, useMemo, useRef, useState } from "react";
import cytoscape from "cytoscape";
import type { Core } from "cytoscape";
import type { EdgeInfo, NodeInfo } from "../api";

const TYPES = [
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
];

type Props = { nodes: NodeInfo[]; edges: EdgeInfo[]; path: string[]; focus: string | null };
type Tip = { x: number; y: number; node: NodeInfo };
type Badge = { id: string; n: number; x: number; y: number };

/** Mark path / neighbour / faded classes. Label text never changes (see note on styles). */
function highlight(c: Core, path: string[], showAll: boolean) {
  c.batch(() => {
    c.elements().removeClass("onpath near faded");
    if (path.length === 0) return;

    const onPath = c.collection();
    path.forEach((id) => onPath.merge(c.getElementById(id)));
    const pathEdges = c.edges().filter((e) => {
      const a = path.indexOf(e.source().id());
      const b = path.indexOf(e.target().id());
      return a !== -1 && b !== -1 && Math.abs(a - b) === 1;
    });

    if (!showAll) {
      const nearNodes = onPath.neighborhood().nodes().difference(onPath);
      const nearEdges = onPath.connectedEdges().difference(pathEdges);
      c.elements().addClass("faded");
      nearNodes.union(nearEdges).removeClass("faded").addClass("near");
    }
    onPath.union(pathEdges).removeClass("faded").addClass("onpath");
  });
}

/** Frame the path (its neighbours stay visible around it), or everything. */
function frame(c: Core, path: string[], showAll: boolean, animate: boolean) {
  const onPath = c.collection();
  path.forEach((id) => onPath.merge(c.getElementById(id)));
  const all = path.length === 0 || showAll;
  const eles = all ? c.elements() : onPath;
  const padding = all ? 30 : 90;
  if (animate) c.animate({ fit: { eles, padding }, duration: 350 });
  else c.fit(eles, padding);
}

/** Screen positions for the step-number badges drawn over path nodes. */
function badgesFor(c: Core, path: string[]): Badge[] {
  return path.map((id, i) => {
    const p = c.getElementById(id).renderedPosition();
    return { id, n: i + 1, x: p.x, y: p.y };
  });
}

export default function GraphView({ nodes, edges, path, focus }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);
  const view = useRef({ path, showAll: false });
  const raf = useRef(0);
  const [showAll, setShowAll] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [tip, setTip] = useState<Tip | null>(null);
  const [badges, setBadges] = useState<Badge[]>([]);
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  view.current = { path, showAll };
  const pathKey = path.join("|");

  /** Recompute badge positions on the next frame (cheap; called on every viewport change). */
  const placeBadges = () => {
    cancelAnimationFrame(raf.current);
    raf.current = requestAnimationFrame(() => {
      const c = cy.current;
      setBadges(c ? badgesFor(c, view.current.path) : []);
    });
  };

  // Build and lay out the graph once the data arrives.
  useEffect(() => {
    if (!host.current || nodes.length === 0) return;
    const css = getComputedStyle(document.documentElement);
    const v = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback;
    const accent = v("--accent", "#2563eb");

    const instance = cytoscape({
      container: host.current,
      elements: [
        ...nodes.map((n) => ({ data: { id: n.id, label: n.label, type: n.type } })),
        ...edges.map((e, i) => ({ data: { id: `e${i}`, source: e.source, target: e.target, type: e.type } })),
      ],
      minZoom: 0.3,
      maxZoom: 1.6,
      // Label text, font size and font weight are the same in every state on purpose:
      // cytoscape caches label dimensions/textures, and changing them per state left
      // labels clipped at their old width. States differ only by colour, opacity and size.
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "font-size": 13,
            "font-weight": 600,
            color: v("--text", "#222"),
            "text-valign": "bottom",
            "text-margin-y": 5,
            "text-background-color": v("--card", "#fff"),
            "text-background-opacity": 0.85,
            "text-background-padding": "2px",
            "text-background-shape": "roundrectangle",
            "min-zoomed-font-size": 7,
            width: 16,
            height: 16,
            "background-color": v("--muted", "#888"),
          },
        },
        ...TYPES.map((t) => ({
          selector: `node[type = "${t}"]`,
          style: { "background-color": v(`--t-${t}`, "#888") },
        })),
        {
          selector: "edge",
          style: {
            width: 1.2,
            "line-color": v("--line", "#bbb"),
            "target-arrow-color": v("--line", "#bbb"),
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.8,
            "curve-style": "bezier",
          },
        },
        { selector: "node.near", style: { opacity: 0.6 } },
        { selector: "edge.near", style: { opacity: 0.35 } },
        { selector: "node.faded", style: { opacity: 0.15, "text-opacity": 0 } },
        { selector: "edge.faded", style: { opacity: 0.08 } },
        {
          selector: "node.onpath",
          style: {
            width: 30,
            height: 30,
            color: accent,
            "text-background-opacity": 1,
            "border-width": 3,
            "border-color": accent,
            "min-zoomed-font-size": 0,
          },
        },
        {
          selector: "edge.onpath",
          style: { width: 3.5, "line-color": accent, "target-arrow-color": accent, "arrow-scale": 1.1 },
        },
        { selector: "node.hover", style: { opacity: 1, "text-opacity": 1 } },
        { selector: "node.pulse", style: { width: 42, height: 42 } },
      ],
      layout: { name: "preset" },
    });
    instance
      .layout({
        name: "cose",
        animate: false,
        randomize: true,
        padding: 30,
        numIter: 1000,
        idealEdgeLength: () => 110,
        nodeRepulsion: () => 600000,
        nodeOverlap: 40,
        componentSpacing: 120,
      })
      .run();

    instance.on("mouseover", "node", (e) => {
      const n = e.target;
      const info = byId.get(n.id());
      if (!info) return;
      n.addClass("hover");
      const p = n.renderedPosition();
      setTip({ x: p.x, y: p.y, node: info });
    });
    instance.on("mouseout", "node", (e) => {
      e.target.removeClass("hover");
      setTip(null);
    });
    instance.on("viewport", () => {
      setTip(null);
      placeBadges();
    });

    cy.current = instance;
    highlight(instance, view.current.path, view.current.showAll);
    frame(instance, view.current.path, view.current.showAll, false);
    placeBadges();
    return () => {
      cancelAnimationFrame(raf.current);
      instance.destroy();
      cy.current = null;
    };
    // placeBadges only reads refs, so it is safe to leave out of the dependencies.
  }, [nodes, edges, byId]);

  // A new roadmap always starts focused on its path.
  useEffect(() => setShowAll(false), [pathKey]);

  // Re-highlight and re-frame when the path or the "show all" toggle changes.
  // Not animated: animating the viewport while elements change state left
  // cytoscape's texture caches holding half-updated labels.
  useEffect(() => {
    const c = cy.current;
    if (!c) return;
    highlight(c, view.current.path, showAll);
    frame(c, view.current.path, showAll, false);
    placeBadges();
  }, [pathKey, showAll]);

  // Keep the canvas sized to its box (expand/collapse, window resizes).
  useEffect(() => {
    const el = host.current;
    if (!el) return;
    let frameReq = 0;
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(frameReq);
      frameReq = requestAnimationFrame(() => {
        const c = cy.current;
        if (!c) return;
        c.resize();
        frame(c, view.current.path, view.current.showAll, false);
        placeBadges();
      });
    });
    ro.observe(el);
    return () => {
      cancelAnimationFrame(frameReq);
      ro.disconnect();
    };
  }, []);

  // Esc closes the expanded view.
  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setExpanded(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [expanded]);

  // Clicking a step centres the graph on it and pulses the node.
  useEffect(() => {
    const c = cy.current;
    if (!c || !focus) return;
    const n = c.getElementById(focus);
    c.animate({ center: { eles: n }, duration: 250 });
    n.flashClass("pulse", 600);
  }, [focus]);

  const hostW = host.current?.clientWidth ?? 0;
  const hostH = host.current?.clientHeight ?? 0;
  const tipStyle = tip
    ? {
        left: tip.x > hostW - 300 ? tip.x - 290 : tip.x + 16,
        top: tip.y > hostH - 160 ? tip.y - 140 : tip.y + 16,
      }
    : undefined;

  return (
    <>
      {expanded && <div className="graph-backdrop" onClick={() => setExpanded(false)} />}
      <section
        className={`card graph-card${expanded ? " expanded" : ""}`}
        aria-labelledby="graph-heading"
        role={expanded ? "dialog" : undefined}
        aria-modal={expanded ? true : undefined}
      >
        <div className="graph-head">
          <h2 id="graph-heading">The knowledge graph</h2>
          <div className="toolbar" role="toolbar" aria-label="Graph view controls">
            <button
              type="button"
              className="tool"
              disabled={path.length === 0}
              onClick={() => (showAll ? setShowAll(false) : cy.current && frame(cy.current, path, false, true))}
            >
              Fit path
            </button>
            <button type="button" className="tool" aria-pressed={showAll} onClick={() => setShowAll(true)}>
              Show all
            </button>
            <button type="button" className="tool" aria-pressed={expanded} onClick={() => setExpanded((x) => !x)}>
              {expanded ? "Close" : "Expand"}
            </button>
          </div>
        </div>
        <div className="graph-wrap">
          <div ref={host} className="graph" role="img" aria-label="Knowledge graph with the current roadmap highlighted" />
          {badges.map((b) => (
            <span key={b.id} className="graph-badge" style={{ left: b.x, top: b.y }} aria-hidden="true">
              {b.n}
            </span>
          ))}
          {tip && (
            <div className="graph-tip" style={tipStyle} role="tooltip">
              <div className="tip-title">
                {tip.node.label} <span className={`badge t-${tip.node.type}`}>{tip.node.type}</span>
              </div>
              <p>{tip.node.description}</p>
            </div>
          )}
        </div>
        <ul className="legend small">
          {TYPES.map((t) => (
            <li key={t}>
              <span className={`dot t-${t}`} /> {t}
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
