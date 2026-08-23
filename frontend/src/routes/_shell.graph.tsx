import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Maximize2, Minus, Plus } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PageHeader } from "@/components/common/PageHeader";
import { CardSkeleton, ErrorState } from "@/components/common/States";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API_ROUTES, apiClient, getAccessToken } from "@/services/apiClient";
import { cn } from "@/lib/utils";
import type { GraphNode } from "@/types";

export const Route = createFileRoute("/_shell/graph")({
  head: () => ({
    meta: [
      { title: "Dependency Graph — Dependency Hub" },
      {
        name: "description",
        content: "Interactive transitive dependency graph with zoom, pan and risk colour coding.",
      },
      { property: "og:title", content: "Dependency Graph — Dependency Hub" },
      { property: "og:description", content: "Explore transitive dependency risk visually." },
    ],
  }),
  component: GraphPage,
});

const statusFill: Record<string, string> = {
  safe: "var(--success)",
  outdated: "var(--warning)",
  vulnerable: "var(--destructive)",
};

const MIN_ZOOM = 0.4;
const MAX_ZOOM = 3;
const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

interface GraphData {
  nodes: GraphNode[];
  edges: Array<{ from: string; to: string }>;
}

function GraphPage() {
  const token = getAccessToken();
  const {
    data,
    isLoading: loading,
    error,
    refetch: reload,
  } = useQuery<GraphData>({
    queryKey: ["graph", "first-project"],
    queryFn: async () => {
      // Fetch the first available project and load its graph
      const projectsRes = await apiClient.get(API_ROUTES.repositories);
      if (!projectsRes.data || projectsRes.data.length === 0) {
        return { nodes: [], edges: [] };
      }
      const projectId = projectsRes.data[0].id;
      const res = await apiClient.get(API_ROUTES.graph(projectId));
      return res.data;
    },
    // SSR-safe: only fires client-side after login
    enabled: !!token,
    staleTime: 60_000,
    retry: false,
  });
  const containerRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const [query, setQuery] = useState("");

  const stateRef = useRef({ zoom, offset });
  stateRef.current = { zoom, offset };

  const handleWheel = useCallback((event: WheelEvent) => {
    const container = containerRef.current;
    if (!container) return;
    const { zoom: currentZoom, offset: currentOffset } = stateRef.current;
    const dy = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? 100 : 1);
    const next = clamp(currentZoom * Math.exp(-dy * 0.0015), MIN_ZOOM, MAX_ZOOM);
    const rect = container.getBoundingClientRect();
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;
    const k = next / currentZoom;
    setOffset({
      x: px - (px - currentOffset.x) * k,
      y: py - (py - currentOffset.y) * k,
    });
    setZoom(next);
  }, []);

  const wheelRef = useRef(handleWheel);
  wheelRef.current = handleWheel;

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return undefined;
    const listener = (event: WheelEvent) => {
      event.preventDefault();
      wheelRef.current(event);
    };
    element.addEventListener("wheel", listener, { passive: false });
    return () => element.removeEventListener("wheel", listener);
  }, [loading]);

  const zoomAtCenter = (factor: number) => {
    const container = containerRef.current;
    const rect = container?.getBoundingClientRect();
    const px = (rect?.width ?? 600) / 2;
    const py = (rect?.height ?? 400) / 2;
    setZoom((prev) => {
      const next = clamp(prev * factor, MIN_ZOOM, MAX_ZOOM);
      const k = next / prev;
      setOffset((current) => ({
        x: px - (px - current.x) * k,
        y: py - (py - current.y) * k,
      }));
      return next;
    });
  };

  const matches = useMemo(() => {
    if (!query.trim() || !data) return new Set<string>();
    return new Set(
      data.nodes
        .filter((node) => node.label.toLowerCase().includes(query.toLowerCase()))
        .map((node) => node.id),
    );
  }, [query, data]);

  return (
    <>
      <PageHeader
        eyebrow="Analysis"
        title="Dependency graph"
        description="Direct and transitive dependencies, coloured by risk. Scroll to zoom, drag to pan."
        actions={
          <Button
            variant="outline"
            onClick={() => {
              setZoom(1);
              setOffset({ x: 0, y: 0 });
            }}
          >
            <Maximize2 className="size-4" /> Reset view
          </Button>
        }
      />

      {error ? (
        <ErrorState
          message={error instanceof Error ? error.message : "Failed to load dependency graph."}
          onRetry={() => reload()}
        />
      ) : null}

      {loading || !data ? (
        <CardSkeleton />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
          <section className="surface-card overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Highlight a package…"
                className="sm:max-w-xs"
                aria-label="Highlight a package"
              />
              <div className="flex items-center gap-2">
                <Button variant="outline" size="icon" onClick={() => zoomAtCenter(1 / 1.25)}>
                  <Minus className="size-4" />
                </Button>
                <span className="w-14 text-center text-sm tabular-nums text-muted-foreground">
                  {Math.round(zoom * 100)}%
                </span>
                <Button variant="outline" size="icon" onClick={() => zoomAtCenter(1.25)}>
                  <Plus className="size-4" />
                </Button>
              </div>
            </div>

            <div
              ref={containerRef}
              onPointerDown={(event) => {
                setDragging(true);
                dragStart.current = { x: event.clientX - offset.x, y: event.clientY - offset.y };
                event.currentTarget.setPointerCapture(event.pointerId);
              }}
              onPointerMove={(event) => {
                if (!dragging) return;
                setOffset({
                  x: event.clientX - dragStart.current.x,
                  y: event.clientY - dragStart.current.y,
                });
              }}
              onPointerUp={() => setDragging(false)}
              onPointerLeave={() => setDragging(false)}
              className={cn(
                "relative h-[520px] touch-none select-none bg-muted/30",
                dragging ? "cursor-grabbing" : "cursor-grab",
              )}
            >
              <svg width="100%" height="100%" role="img" aria-label="Dependency graph">
                <g transform={`translate(${offset.x} ${offset.y}) scale(${zoom})`}>
                  {data.edges.map((edge) => {
                    const from = data.nodes.find((node) => node.id === edge.from);
                    const to = data.nodes.find((node) => node.id === edge.to);
                    if (!from || !to) return null;
                    return (
                      <line
                        key={`${edge.from}-${edge.to}`}
                        x1={from.x}
                        y1={from.y}
                        x2={to.x}
                        y2={to.y}
                        stroke="var(--border)"
                        strokeWidth={1.5}
                      />
                    );
                  })}
                  {data.nodes.map((node) => {
                    const dimmed = matches.size > 0 && !matches.has(node.id);
                    return (
                      <g
                        key={node.id}
                        transform={`translate(${node.x} ${node.y})`}
                        opacity={dimmed ? 0.25 : 1}
                        onClick={() => setSelected(node)}
                        className="cursor-pointer"
                      >
                        <circle
                          r={node.depth === 0 ? 26 : 18}
                          fill={statusFill[node.status]}
                          fillOpacity={selected?.id === node.id ? 0.95 : 0.75}
                          stroke="var(--card)"
                          strokeWidth={3}
                        />
                        <text
                          y={node.depth === 0 ? 44 : 34}
                          textAnchor="middle"
                          fontSize={11}
                          fill="var(--foreground)"
                        >
                          {node.label}
                        </text>
                      </g>
                    );
                  })}
                </g>
              </svg>
            </div>
          </section>

          <aside className="surface-card h-fit space-y-5 p-5">
            <div>
              <h2 className="text-sm font-semibold">Legend</h2>
              <ul className="mt-3 space-y-2 text-sm">
                {(["safe", "outdated", "vulnerable"] as const).map((status) => (
                  <li key={status} className="flex items-center gap-2 capitalize">
                    <span
                      className="size-3 rounded-full"
                      style={{ backgroundColor: statusFill[status] }}
                    />
                    {status}
                  </li>
                ))}
              </ul>
            </div>

            <div className="border-t border-border pt-4">
              <h2 className="text-sm font-semibold">Selected node</h2>
              {selected ? (
                <dl className="mt-3 space-y-2 text-sm">
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-foreground">Package</dt>
                    <dd className="font-medium">{selected.label}</dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-foreground">Status</dt>
                    <dd className="font-medium capitalize">{selected.status}</dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-foreground">Depth</dt>
                    <dd className="font-medium">
                      {selected.depth === 0 ? "Root" : `Level ${selected.depth}`}
                    </dd>
                  </div>
                </dl>
              ) : (
                <p className="mt-3 text-sm text-muted-foreground">
                  Click any node to inspect its risk metadata.
                </p>
              )}
            </div>

            <div className="border-t border-border pt-4 text-sm text-muted-foreground">
              {data.nodes.length} nodes · {data.edges.length} edges resolved from the latest scan.
            </div>
          </aside>
        </div>
      )}
    </>
  );
}
