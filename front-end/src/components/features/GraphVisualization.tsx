import { useMemo, useRef, useState } from "react";
import { InteractiveNvlWrapper, type MouseEventCallbacks } from "@neo4j-nvl/react";
import NVL, { type Layout, type Node as NvlNode, type Relationship as NvlRelationship } from "@neo4j-nvl/base";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { ZoomIn, ZoomOut, Maximize2, AlertTriangle } from "lucide-react";
import type { GraphDataResponse, GraphNode } from "@/hooks/useGraphData";
import { useItemDetails } from "@/hooks/useItemDetails";

type LayoutMode = "force" | "hierarchical" | "circular" | "radial";
const ALL_RELATIONSHIPS_VALUE = "__all_relationships__";
type GraphSelectionCallbacks = Pick<MouseEventCallbacks, "onNodeClick" | "onNodeDoubleClick" | "onCanvasClick">;

export type GraphNavigationTarget = {
  id: string;
  label: string;
  type: "Title" | "Person";
};

type GraphVisualizationProps = {
  data: GraphDataResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  onRetry: () => void;
  hasRequested: boolean;
  onNavigateToNode: (target: GraphNavigationTarget) => void;
};

const LAYOUT_TO_NVL: Record<LayoutMode, Layout> = {
  force: "forceDirected",
  hierarchical: "hierarchical",
  circular: "circular",
  radial: "circular",
};

function buildGraphMouseEventCallbacks(selectionCallbacks: GraphSelectionCallbacks): MouseEventCallbacks {
  return {
    // Enable built-in NVL wheel zoom and click-drag panning interactions.
    onZoomAndPan: true,
    onPan: true,
    onDrag: true,
    ...selectionCallbacks,
  };
}

function formatErrorMessage(error: Error | null): string {
  if (!error) {
    return "Unable to load graph data.";
  }

  if (error.message.includes("(503)")) {
    return "Graph service is currently unavailable. Please try again.";
  }

  if (error.message.includes("(422)")) {
    return "Current filters are invalid for graph query. Adjust filters and retry.";
  }

  return "Unable to load graph data. Please try again.";
}

function getNodeTypeLabel(node: GraphNode): string {
  return node.type === "Title" ? "Title" : "Person";
}

function formatItemDetailsErrorMessage(error: Error | null): string {
  if (!error) {
    return "Unable to load description. Please try again.";
  }

  if (error.message.includes("(404)")) {
    return "Description not found.";
  }

  if (error.message.includes("(503)")) {
    return "Description service is temporarily unavailable.";
  }

  if (error.message.includes("(422)")) {
    return "Description is currently unavailable. Please try again.";
  }

  return "Unable to load description. Please try again.";
}

export function GraphVisualization({
  data,
  isLoading,
  isError,
  error,
  onRetry,
  hasRequested,
  onNavigateToNode,
}: GraphVisualizationProps) {
  const [layoutMode, setLayoutMode] = useState<LayoutMode>("force");
  const [relationshipFilter, setRelationshipFilter] = useState<string>(ALL_RELATIONSHIPS_VALUE);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const nvlRef = useRef<NVL | null>(null);

  const graphData = useMemo(
    () => ({
      nodes: data?.nodes ?? [],
      edges: data?.edges ?? [],
    }),
    [data],
  );

  const relationshipOptions = useMemo(() => {
    return Array.from(new Set(graphData.edges.map((edge) => edge.type))).sort((a, b) => a.localeCompare(b));
  }, [graphData.edges]);

  const effectiveRelationshipFilter =
    relationshipFilter !== ALL_RELATIONSHIPS_VALUE && relationshipOptions.includes(relationshipFilter)
      ? relationshipFilter
      : ALL_RELATIONSHIPS_VALUE;

  const visibleGraphData = useMemo(() => {
    if (effectiveRelationshipFilter === ALL_RELATIONSHIPS_VALUE) {
      return graphData;
    }

    const edges = graphData.edges.filter((edge) => edge.type === effectiveRelationshipFilter);
    const visibleNodeIds = new Set<string>();
    for (const edge of edges) {
      visibleNodeIds.add(edge.source);
      visibleNodeIds.add(edge.target);
    }

    const nodes = graphData.nodes.filter((node) => visibleNodeIds.has(node.id));
    return { nodes, edges };
  }, [effectiveRelationshipFilter, graphData]);

  const effectiveSelectedNodeId =
    selectedNodeId && visibleGraphData.nodes.some((node) => node.id === selectedNodeId) ? selectedNodeId : null;

  const selectedNode = useMemo(
    () => graphData.nodes.find((node) => node.id === effectiveSelectedNodeId) ?? null,
    [effectiveSelectedNodeId, graphData.nodes],
  );

  const selectedNodeItemDetailsParams = useMemo(
    () => ({
      titleId: selectedNode?.type === "Title" ? selectedNode.id : null,
      nameId: selectedNode?.type === "Person" ? selectedNode.id : null,
    }),
    [selectedNode],
  );

  const itemDetailsQuery = useItemDetails(selectedNodeItemDetailsParams);

  const nvlNodes = useMemo<NvlNode[]>(() => {
    return visibleGraphData.nodes.map((node) => ({
      id: node.id,
      caption: node.label,
      color: node.type === "Title" ? "#60A5FA" : "#22C55E",
      size: node.isAnchor ? 38 : 30,
      selected: node.id === effectiveSelectedNodeId,
    }));
  }, [effectiveSelectedNodeId, visibleGraphData.nodes]);

  const nvlRels = useMemo<NvlRelationship[]>(() => {
    return visibleGraphData.edges.map((edge) => ({
      id: edge.id,
      from: edge.source,
      to: edge.target,
      type: edge.type,
      caption: edge.type,
      color: "#52525B",
      selected: false,
    }));
  }, [visibleGraphData.edges]);

  const graphNodeIds = useMemo(() => nvlNodes.map((node) => node.id), [nvlNodes]);

  const mouseEventCallbacks = useMemo(
    () =>
      buildGraphMouseEventCallbacks({
        onNodeClick: (node) => {
          setSelectedNodeId(node.id);
        },
        onNodeDoubleClick: (node) => {
          const graphNode = graphData.nodes.find((n) => n.id === node.id);
          if (!graphNode) {
            return;
          }
          onNavigateToNode({ id: graphNode.id, label: graphNode.label, type: graphNode.type });
        },
        onCanvasClick: () => {
          setSelectedNodeId(null);
        },
      }),
    [graphData.nodes, onNavigateToNode],
  );

  const handleZoomIn = () => {
    if (!nvlRef.current) {
      return;
    }
    const currentScale = nvlRef.current.getScale();
    nvlRef.current.setZoom(currentScale * 1.2);
  };

  const handleZoomOut = () => {
    if (!nvlRef.current) {
      return;
    }
    const currentScale = nvlRef.current.getScale();
    nvlRef.current.setZoom(currentScale / 1.2);
  };

  const handleResetView = () => {
    if (!nvlRef.current) {
      return;
    }
    if (graphNodeIds.length > 0) {
      nvlRef.current.fit(graphNodeIds);
      return;
    }
    nvlRef.current.resetZoom();
  };

  const isEmptyData =
    !isLoading &&
    !isError &&
    hasRequested &&
    (visibleGraphData.nodes.length === 0 || visibleGraphData.edges.length === 0);
  const errorMessage = formatErrorMessage(error);

  return (
    <div className="h-full flex flex-col bg-neutral-950">
      <div className="h-12 border-b border-neutral-800 flex items-center justify-between px-4 gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <Select value={layoutMode} onValueChange={(value) => setLayoutMode(value as LayoutMode)}>
            <SelectTrigger className="w-40 h-8 bg-neutral-900 border-neutral-800" aria-label="Graph layout">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="force">Force Layout</SelectItem>
              <SelectItem value="hierarchical">Hierarchical</SelectItem>
              <SelectItem value="circular">Circular</SelectItem>
              <SelectItem value="radial">Radial</SelectItem>
            </SelectContent>
          </Select>

          <Select value={effectiveRelationshipFilter} onValueChange={setRelationshipFilter}>
            <SelectTrigger className="w-56 h-8 bg-neutral-900 border-neutral-800" aria-label="Relationship filter">
              <SelectValue placeholder="All relationships" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_RELATIONSHIPS_VALUE}>All relationships</SelectItem>
              {relationshipOptions.map((relationshipType) => (
                <SelectItem key={relationshipType} value={relationshipType}>
                  {relationshipType}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {data?.meta.truncated && (
            <span className="inline-flex items-center gap-1 rounded-md border border-amber-600/50 bg-amber-500/10 px-2 py-1 text-[10px] text-amber-300" role="status">
              <AlertTriangle className="h-3 w-3" />
              Truncated ({data.meta.returnedNodes} nodes / {data.meta.returnedEdges} edges)
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleZoomIn} aria-label="Zoom in">
            <ZoomIn className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleZoomOut} aria-label="Zoom out">
            <ZoomOut className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleResetView} aria-label="Reset graph view">
            <Maximize2 className="w-4 h-4" />
          </Button>
        </div>
      </div>

      <div className="flex-1 relative bg-neutral-900/50">
        {!hasRequested && (
          <div className="absolute inset-0 flex items-center justify-center p-6">
            <div className="text-center space-y-2">
              <p className="text-sm text-neutral-400">Adjust filters and click Show graph</p>
              <p className="text-xs text-neutral-600">The graph loads on demand to keep exploration fast.</p>
            </div>
          </div>
        )}

        {hasRequested && isLoading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-sm text-neutral-400">Loading graph...</div>
          </div>
        )}

        {hasRequested && isError && (
          <div className="absolute inset-0 flex items-center justify-center p-6">
            <div className="max-w-md rounded-lg border border-red-900/60 bg-red-950/30 p-4 text-center space-y-3">
              <p className="text-sm text-red-300">{errorMessage}</p>
              <Button size="sm" onClick={onRetry}>Retry</Button>
            </div>
          </div>
        )}

        {hasRequested && isEmptyData && (
          <div className="absolute inset-0 flex items-center justify-center p-6">
            <div className="text-center space-y-2">
              <p className="text-sm text-neutral-400">No graph data for current filters</p>
              <p className="text-xs text-neutral-600">Try broader filters or another search anchor.</p>
            </div>
          </div>
        )}

        {hasRequested && !isLoading && !isError && !isEmptyData && (
          <InteractiveNvlWrapper
            ref={nvlRef}
            className="absolute inset-0"
            layout={LAYOUT_TO_NVL[layoutMode]}
            nodes={nvlNodes}
            rels={nvlRels}
            nvlOptions={{
              disableTelemetry: true,
              renderer: "canvas",
              layout: LAYOUT_TO_NVL[layoutMode],
              allowDynamicMinZoom: true,
            }}
            interactionOptions={{
              selectOnClick: false,
            }}
            mouseEventCallbacks={mouseEventCallbacks}
          />
        )}

      </div>

      <div className="border-t border-neutral-800 px-4 py-2 text-xs text-neutral-500 space-y-2" role="status">
        <div className="flex gap-6 flex-wrap">
          <span>Nodes: <span className="text-neutral-300">{visibleGraphData.nodes.length}</span></span>
          <span>Edges: <span className="text-neutral-300">{visibleGraphData.edges.length}</span></span>
          <span>Total nodes: <span className="text-neutral-300">{graphData.nodes.length}</span></span>
          <span>Total edges: <span className="text-neutral-300">{graphData.edges.length}</span></span>
          <span>Selected: <span className="text-neutral-300">{selectedNode?.label ?? "None"}</span></span>
        </div>
        {selectedNode && (
          <div className="rounded-md border border-neutral-800 bg-neutral-900/60 px-3 py-2 text-[11px] text-neutral-300 grid grid-cols-1 md:grid-cols-2 gap-2">
            <span>ID: {selectedNode.id}</span>
            <span>Type: {getNodeTypeLabel(selectedNode)}</span>
            {typeof selectedNode.isAnchor === "boolean" && <span>Anchor: {selectedNode.isAnchor ? "Yes" : "No"}</span>}
            {selectedNode.titleType && <span>Title Type: {selectedNode.titleType}</span>}
            {selectedNode.genres && selectedNode.genres.length > 0 && <span>Genres: {selectedNode.genres.join(", ")}</span>}
            {typeof selectedNode.startYear === "number" && <span>Start Year: {selectedNode.startYear}</span>}
            {typeof selectedNode.averageRating === "number" && <span>Rating: {selectedNode.averageRating.toFixed(1)}</span>}
            {typeof selectedNode.numVotes === "number" && <span>Votes: {selectedNode.numVotes.toLocaleString()}</span>}
            {selectedNode.primaryProfession && selectedNode.primaryProfession.length > 0 && <span>Professions: {selectedNode.primaryProfession.join(", ")}</span>}
            {typeof selectedNode.birthYear === "number" && <span>Birth Year: {selectedNode.birthYear}</span>}
            {typeof selectedNode.deathYear === "number" && <span>Death Year: {selectedNode.deathYear}</span>}

            <div className="md:col-span-2 mt-1 border-t border-neutral-800 pt-2" aria-live="polite">
              <p className="text-neutral-400">Description</p>
              {itemDetailsQuery.isLoading && <p className="mt-1 text-neutral-300">Loading description...</p>}

              {!itemDetailsQuery.isLoading && itemDetailsQuery.data?.description && (
                <div className="mt-1 space-y-1">
                  <p className="text-neutral-200 leading-relaxed">{itemDetailsQuery.data.description}</p>
                  {itemDetailsQuery.isFetching && <p className="text-[10px] text-neutral-500">Refreshing...</p>}
                </div>
              )}

              {!itemDetailsQuery.isLoading && !itemDetailsQuery.data?.description && itemDetailsQuery.isError && (
                <p className="mt-1 text-amber-300">{formatItemDetailsErrorMessage(itemDetailsQuery.error)}</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
