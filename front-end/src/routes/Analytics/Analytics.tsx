import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";
import { Separator } from "@/components/ui/separator";
import { Database, Filter, Search } from "lucide-react";
import { GraphVisualization } from "@/components/features/GraphVisualization";
import { FilterPanel } from "@/components/features/FilterPanel";
import { QueryPanel } from "@/components/features/QueryPanel";

export default function Analytics() {
  return (
    <div className="size-full flex flex-col bg-neutral-950 text-neutral-50">
      {/* Header */}
      <header className="h-14 border-b border-neutral-800 flex items-center px-6 shrink-0">
        <div className="flex items-center gap-3">
          <Database className="w-5 h-5 text-neutral-400" />
          <h1 className="text-lg tracking-tight m-0 font-normal">IMDB Analytics</h1>
        </div>
      </header>

      {/* Main Content */}
      <ResizablePanelGroup orientation="horizontal" className="flex-1 overflow-hidden">
        {/* Left Panel - Graph Visualization */}
        <ResizablePanel defaultSize={65} minSize={40}>
          <GraphVisualization />
        </ResizablePanel>

        <ResizableHandle className="w-px bg-neutral-800" />

        {/* Right Panel - Filters & Queries */}
        <ResizablePanel defaultSize={35} minSize={25}>
          <div className="h-full flex flex-col overflow-auto">
            {/* Filters Section */}
            <div className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <Filter className="w-4 h-4 text-neutral-400" />
                <h2 className="text-sm tracking-tight text-neutral-300 m-0 font-normal">Filters</h2>
              </div>
              <FilterPanel />
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
    </div>
  );
}
