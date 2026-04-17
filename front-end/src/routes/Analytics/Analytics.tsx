import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";
import { Separator } from "@/components/ui/separator";
import { Search } from "lucide-react";
import { GraphVisualization } from "@/components/features/GraphVisualization";
import { FilterPanel, type FilterState } from "@/components/features/FilterPanel";
import { QueryPanel } from "@/components/features/QueryPanel";
import { useImmer } from "use-immer";
import { useState } from "react";
import { useGraphData, type GraphFilters } from "@/hooks/useGraphData";

const INITIAL_FILTER_STATE: FilterState = {
  topRated: false,
  mostPopular: false,
  search: "",
  selectedSearchResult: null,
  genre: null,
  titleType: null,
  ratingRange: null,
  yearRange: null,
};

function toGraphFilters(filters: FilterState): GraphFilters {
  return {
    selectedSearchResult: filters.selectedSearchResult,
    titleType: filters.titleType,
    genre: filters.genre,
    ratingRange: filters.ratingRange,
    yearRange: filters.yearRange,
    topRated: filters.topRated,
    mostPopular: filters.mostPopular,
  };
}

export default function Analytics() {
  const [filters, setFilters] = useImmer<FilterState>(INITIAL_FILTER_STATE);
  const [graphRequestToken, setGraphRequestToken] = useState(0);
  const [submittedGraphFilters, setSubmittedGraphFilters] = useState<GraphFilters>(() => toGraphFilters(INITIAL_FILTER_STATE));

  const graphDataQuery = useGraphData(submittedGraphFilters, graphRequestToken);

  const handleShowGraph = () => {
    setSubmittedGraphFilters(toGraphFilters(filters));
    setGraphRequestToken((prev) => prev + 1);
  };

  return (
    <ResizablePanelGroup orientation="horizontal" className="size-full overflow-hidden">
        {/* Left Panel - Graph Visualization */}
        <ResizablePanel defaultSize={65} minSize={40}>
          <GraphVisualization
            data={graphDataQuery.data}
            isLoading={graphDataQuery.isLoading || graphDataQuery.isFetching}
            isError={graphDataQuery.isError}
            error={graphDataQuery.error}
            onRetry={() => {
              void graphDataQuery.refetch();
            }}
            hasRequested={graphRequestToken > 0}
          />
        </ResizablePanel>

        <ResizableHandle className="w-px bg-neutral-800" />

        {/* Right Panel - Filters & Queries */}
        <ResizablePanel defaultSize={35} minSize={25}>
          <div className="h-full flex flex-col overflow-auto">
            {/* Filters Section */}
            <div className="p-6">
              <FilterPanel
                filters={filters}
                setFilters={setFilters}
                onShowGraph={handleShowGraph}
                isGraphLoading={graphDataQuery.isLoading || graphDataQuery.isFetching}
                hasGraphRequested={graphRequestToken > 0}
              />
            </div>

            <Separator className="bg-neutral-800" />

            {/* Query Section */}
            <div className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <Search className="w-4 h-4 text-neutral-400" />
                <h2 className="text-sm tracking-tight text-neutral-300 m-0 font-normal">Instant Queries</h2>
              </div>
              <QueryPanel />
            </div>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
  );
}
